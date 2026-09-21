"""Zaxira nusxa: baza + yuklangan rasmlar, Telegramga yuboriladi.

Nega ilovaning ichida, alohida skript emas: nusxani ikki joydan olish
kerak — jadval bo'yicha (cron) va egasi tugma bosganda. Ikki nusxa kod
muqarrar ravishda bir-biridan uzoqlashadi, shuning uchun mantiq bitta
joyda turadi: `manage.py backup` ham, sahifadagi tugma ham shu yerni
chaqiradi.

Fayl ikkita: `pg_dump` natijasi va media papkasining arxivi. Ikkalasi
ham kerak — bazada rasmlarning faqat NOMI saqlanadi, fayllarning o'zi
diskda yotadi. Bittasini tiklab, ikkinchisini unutish menyuni rasmsiz
qoldiradi.
"""
import os
import re
import shutil
import subprocess
import tarfile
import time
from datetime import datetime
from pathlib import Path
from urllib import request as urlrequest

from django.conf import settings
from django.utils import timezone

# Telegram bot API bitta faylni 50 MB gacha qabul qiladi. Undan kattasi
# jim yo'qolmasligi kerak — ogohlantirish yuboriladi va fayl diskda qoladi.
TELEGRAM_LIMIT = 50 * 1024 * 1024
# Buyruq shuncha kutadi: katta baza sekin yig'iladi, lekin cheksiz emas.
DUMP_TIMEOUT = 600


class BackupError(Exception):
    """Nusxa olinmadi. Sabab xabarda — egasi uni ekranda ko'radi."""


def chat_ids():
    """Nusxa yuboriladigan Telegram chatlari.

    Bir nechta bo'lishi mumkin, vergul bilan ajratiladi: egasi va
    hamkori bir vaqtda olishi kerak bo'lsa, nusxa ikkalasiga ham ketadi.
    Bittasi xato bo'lsa qolganlariga yuborish davom etadi — bitta
    noto'g'ri raqam butun zaxirani to'xtatib qo'ymasin.
    """
    raw = str(getattr(settings, 'TELEGRAM_CHAT_ID', '') or '')
    return [item.strip() for item in raw.split(',') if item.strip()]


def backup_dir():
    path = Path(getattr(settings, 'BACKUP_DIR', '/var/lib/xonim/backups'))
    path.mkdir(parents=True, exist_ok=True)
    return path


def human(size):
    for unit in ('B', 'KB', 'MB', 'GB'):
        if size < 1024 or unit == 'GB':
            return f'{size:.0f} {unit}' if unit == 'B' else f'{size:.1f} {unit}'
        size /= 1024
    return f'{size:.1f} GB'


def dump_database(target):
    """`pg_dump` ni chaqiradi. Parol muhit o'zgaruvchisida — buyruq
    qatorida emas, aks holda u serverdagi jarayonlar ro'yxatida ko'rinardi."""
    database = settings.DATABASES['default']
    if 'sqlite' in database['ENGINE']:
        # Mahalliy ishlab chiqishda baza bitta fayl — uni nusxalash yetadi.
        shutil.copyfile(database['NAME'], target)
        return

    environment = {**os.environ, 'PGPASSWORD': database['PASSWORD'] or ''}
    command = [
        'pg_dump',
        '--host', database['HOST'] or 'db',
        '--port', str(database['PORT'] or 5432),
        '--username', database['USER'],
        '--dbname', database['NAME'],
        '--no-owner', '--no-privileges',
        '--format', 'custom',
        '--file', str(target),
    ]
    try:
        done = subprocess.run(
            command, env=environment, timeout=DUMP_TIMEOUT,
            capture_output=True, text=True, check=False,
        )
    except FileNotFoundError:
        raise BackupError('pg_dump topilmadi: tasvir eskirgan bo‘lishi mumkin.') from None
    except subprocess.TimeoutExpired:
        raise BackupError(f'Baza nusxasi {DUMP_TIMEOUT} soniyada tugamadi.') from None
    if done.returncode != 0:
        # Xato matnida parol bo'lmaydi, lekin baribir qisqartiramiz.
        raise BackupError(f'pg_dump xato qaytardi: {done.stderr.strip()[:200]}')


def archive_media(target):
    """Yuklangan rasmlarni bitta arxivga yig'adi. Bo'sh bo'lsa ham arxiv
    yaratiladi: «fayl yo'q» bilan «nusxa olinmadi» bir xil emas."""
    media = Path(settings.MEDIA_ROOT)
    with tarfile.open(target, 'w:gz') as archive:
        if media.exists():
            archive.add(media, arcname='media')


def telegram_send(token, chat_id, path, caption):
    """Faylni Telegramga yuboradi. multipart qo'lda yig'iladi: loyihada
    tashqi HTTP kutubxonasi yo'q va shuning uchun qo'shilmaydi ham."""
    size = path.stat().st_size
    if size > TELEGRAM_LIMIT:
        telegram_message(
            token, chat_id,
            f'⚠️ {path.name} ({human(size)}) Telegram chegarasidan katta — '
            f'yuborilmadi. Fayl serverda: {path}',
        )
        return False

    boundary = f'----xonim{int(time.time() * 1000)}'
    body = bytearray()
    for name, value in (('chat_id', str(chat_id)), ('caption', caption)):
        body += f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
        body += f'{value}\r\n'.encode()
    body += f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{path.name}"\r\n'.encode()
    body += b'Content-Type: application/octet-stream\r\n\r\n'
    body += path.read_bytes()
    body += f'\r\n--{boundary}--\r\n'.encode()

    call = urlrequest.Request(
        f'https://api.telegram.org/bot{token}/sendDocument',
        data=bytes(body),
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'},
    )
    try:
        with urlrequest.urlopen(call, timeout=120) as response:
            return b'"ok":true' in response.read()
    except Exception as failure:  # noqa: BLE001 - tarmoq xatosi turlicha bo'ladi
        raise BackupError(f'Telegramga yuborilmadi: {str(failure)[:160]}') from None


def telegram_message(token, chat_id, text):
    data = f'chat_id={chat_id}&text={urlrequest.quote(text)}'.encode()
    call = urlrequest.Request(f'https://api.telegram.org/bot{token}/sendMessage', data=data)
    try:
        with urlrequest.urlopen(call, timeout=30):
            return True
    except Exception:  # noqa: BLE001 - xabar yuborilmasa ham nusxa olingan
        return False


def prune(keep_days):
    """Eski nusxalar o'chiriladi: 50GB disk to'lib qolmasligi kerak."""
    if keep_days <= 0:
        return 0
    cutoff = time.time() - keep_days * 86400
    removed = 0
    for item in backup_dir().iterdir():
        if item.is_file() and item.stat().st_mtime < cutoff:
            item.unlink()
            removed += 1
    return removed


def run_backup(actor=None, source='cron'):
    """Nusxa oladi, Telegramga yuboradi va xulosani qaytaradi.

    Telegram sozlanmagan bo'lsa ham nusxa olinadi va diskda qoladi —
    yuborishning ishlamasligi zaxirani to'xtatish uchun sabab emas.
    """
    stamp = timezone.localtime().strftime('%Y-%m-%d_%H-%M')
    folder = backup_dir()
    database = folder / f'xonim-db-{stamp}.dump'
    media = folder / f'xonim-media-{stamp}.tar.gz'

    dump_database(database)
    archive_media(media)

    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    chats = chat_ids()
    delivered, failed = 0, []
    note = ''
    if token and chats:
        who = f' · {actor}' if actor else ''
        label = 'qo‘lda' if source == 'manual' else 'jadval bo‘yicha'
        moment = timezone.localtime().strftime('%d.%m.%Y %H:%M')
        for chat in chats:
            try:
                for path, what in ((database, 'Baza'), (media, 'Rasmlar')):
                    caption = f'Xonim · {what} · {moment} ({label}{who}) · {human(path.stat().st_size)}'
                    telegram_send(token, chat, path, caption)
                delivered += 1
            except BackupError as failure:
                # Bitta qabul qiluvchi xato bo'lsa — masalan botga hali
                # yozmagan bo'lsa — qolganlari nusxani baribir oladi.
                failed.append(f'{mask(chat)}: {failure}')
    else:
        note = 'Telegram sozlanmagan: nusxa faqat serverda saqlandi.'
    if failed:
        note = 'Yuborilmadi — ' + '; '.join(failed)

    removed = prune(int(getattr(settings, 'BACKUP_KEEP_DAYS', 14)))
    return {
        'created_at': timezone.now(),
        'files': [
            {'name': database.name, 'size': human(database.stat().st_size)},
            {'name': media.name, 'size': human(media.stat().st_size)},
        ],
        'sent_to_telegram': bool(chats) and delivered == len(chats),
        'delivered': delivered,
        'recipients': len(chats),
        'removed_old': removed,
        'note': note,
    }


def latest_backups(limit=10):
    """Oxirgi nusxalar ro'yxati — sahifada ko'rsatish uchun."""
    rows = sorted(
        (item for item in backup_dir().iterdir() if item.is_file()),
        key=lambda item: item.stat().st_mtime, reverse=True,
    )
    result = []
    for item in rows[:limit]:
        moment = datetime.fromtimestamp(item.stat().st_mtime, tz=timezone.get_current_timezone())
        result.append({
            'name': item.name,
            'size': human(item.stat().st_size),
            'created_at': moment,
            'kind': 'media' if 'media' in item.name else 'db',
        })
    return result


def mask(chat):
    """Faqat oxirgi raqamlar: qaysi chat ekanini ajratish uchun yetarli,
    lekin butun raqam ekranda turmaydi."""
    return re.sub(r'^.*(\d{4})$', r'…\1', str(chat))


def telegram_status():
    """Sozlangan-sozlanmagani. Token ekranga CHIQMAYDI."""
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    chats = chat_ids()
    return {
        'configured': bool(token and chats),
        'chat': ', '.join(mask(item) for item in chats),
        'recipients': len(chats),
    }
