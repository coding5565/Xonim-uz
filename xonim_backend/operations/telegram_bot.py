"""Telegram bot buyruqlari: chatdan turib zaxira nusxa olish.

Nega webhook, so'rov halqasi emas: tizim allaqachon haqiqiy sertifikat
bilan HTTPS'da turibdi, shuning uchun Telegram o'zi xabar yuboradi.
Halqa bo'lganda yana bitta doimiy jarayonni kuzatib turish kerak bo'lardi.

Xavfsizlik uch qavat:
  · Telegram har so'rovda maxfiy sarlavha yuboradi (`setWebhook` da
    o'rnatiladi) — u mos kelmasa so'rov qaralmaydi;
  · buyruq faqat TELEGRAM_CHAT_ID ro'yxatidagi chatlardan qabul qilinadi;
  · yaqinda olingan nusxa qayta olinmaydi — Telegram javobni kutmay
    so'rovni takrorlashi mumkin, aks holda har takror yangi nusxa
    yasab, diskni va bazani behuda bosardi.
"""
import hmac
import logging
import time

from django.conf import settings
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .backups import (
    BackupError,
    backup_dir,
    chat_ids,
    human,
    latest_backups,
    run_backup,
    telegram_message,
)

logger = logging.getLogger(__name__)

# Shu vaqt ichida olingan nusxa qayta olinmaydi.
COOLDOWN_SECONDS = 90

HELP = (
    'Xonim CRM — zaxira nusxa boti\n\n'
    '/backup — hozir nusxa olish va shu yerga yuborish\n'
    '/status — oxirgi nusxalar ro‘yxati\n'
    '/help — shu ro‘yxat\n\n'
    'Nusxa har kuni 03:30 va 15:30 da o‘zi ham olinadi.'
)


def recent_backup():
    """Oxirgi nusxa hali «yangi» bo'lsa uni qaytaradi, aks holda None."""
    newest = max(
        (item for item in backup_dir().iterdir() if item.is_file()),
        key=lambda item: item.stat().st_mtime, default=None,
    )
    if newest and time.time() - newest.stat().st_mtime < COOLDOWN_SECONDS:
        return newest
    return None


class TelegramWebhookView(APIView):
    """Telegram yuboradigan xabarlarni qabul qiladi.

    Foydalanuvchi sessiyasi yo'q, shuning uchun autentifikatsiya
    o'chirilgan: kim yozgani Telegram bergan chat raqamidan aniqlanadi.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        secret = getattr(settings, 'TELEGRAM_WEBHOOK_SECRET', '')
        sent = request.headers.get('X-Telegram-Bot-Api-Secret-Token', '')
        # `compare_digest`: maxfiy so'zni belgima-belgi taqqoslash vaqtidan
        # topib bo'lmasin.
        if not secret or not hmac.compare_digest(secret, sent):
            logger.warning('Telegram webhook: maxfiy so‘z mos kelmadi')
            # Telegram 200 dan boshqa javobda so'rovni takrorlaydi, lekin
            # bu yerda takrorlashning ma'nosi yo'q.
            return Response({'ok': True})

        message = (request.data or {}).get('message') or {}
        chat = str((message.get('chat') or {}).get('id') or '')
        text = (message.get('text') or '').strip()
        if not chat or not text:
            return Response({'ok': True})

        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        allowed = chat_ids()

        if chat not in allowed:
            # Ro'yxatda yo'q odamga o'z raqamini aytamiz: uni qo'shish
            # uchun aynan shu kerak. Hech qanday ma'lumot berilmaydi.
            telegram_message(
                token, chat,
                f'Bu bot faqat ruxsat berilgan chatlar bilan ishlaydi.\n'
                f'Sizning raqamingiz: {chat}\n'
                f'Uni tizim egasiga bering.',
            )
            return Response({'ok': True})

        command = text.split()[0].lower().split('@')[0]
        if command in ('/start', '/help'):
            telegram_message(token, chat, HELP)
        elif command == '/status':
            rows = latest_backups(6)
            if rows:
                lines = '\n'.join(
                    f'· {item["created_at"]:%d.%m %H:%M} — {item["size"]}' for item in rows)
                telegram_message(token, chat, f'Oxirgi nusxalar:\n{lines}')
            else:
                telegram_message(token, chat, 'Hali nusxa olinmagan.')
        elif command == '/backup':
            self.make_backup(token, chat)
        else:
            telegram_message(token, chat, f'Noma’lum buyruq. {HELP}')
        return Response({'ok': True})

    def make_backup(self, token, chat):
        fresh = recent_backup()
        if fresh:
            telegram_message(
                token, chat,
                f'Nusxa hozirgina olingan ({human(fresh.stat().st_size)}, '
                f'{COOLDOWN_SECONDS} soniya ichida). Qaytadan olinmadi.',
            )
            return
        telegram_message(token, chat, 'Nusxa olinmoqda…')
        try:
            result = run_backup(actor='Telegram', source='manual')
        except BackupError as failure:
            telegram_message(token, chat, f'Nusxa olinmadi: {failure}')
            return
        if result['note']:
            telegram_message(token, chat, result['note'])
