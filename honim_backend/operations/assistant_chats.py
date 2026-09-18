"""Saqlanadigan AI suhbatlari.

Har bir foydalanuvchi faqat o'zining suhbatlarini ko'radi — bu shaxsiy
ish daftari, umumiy jurnal emas. Sarlavha birinchi savoldan olinadi,
shuning uchun foydalanuvchi hech narsa nomlashi shart emas.
"""
from django.db import transaction
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.i18n import _
from users.permissions import OwnerOnly

from .models import AssistantChat, AssistantMessage

TITLE_LENGTH = 60
# Bir suhbatda shuncha gapdan keyin eskisi ko'rsatilmaydi; hammasi
# bazada qoladi, faqat ochilish tez bo'lishi uchun cheklanadi.
HISTORY_LIMIT = 200


def make_title(question):
    text = ' '.join(question.split())
    return text[:TITLE_LENGTH - 1] + '…' if len(text) > TITLE_LENGTH else text


def chat_row(chat, preview=''):
    return {
        'id': chat.id,
        'title': chat.title,
        'created_at': chat.created_at,
        'updated_at': chat.updated_at,
        'preview': preview,
    }


def message_row(message):
    return {
        'id': message.id,
        'role': message.role,
        'text': message.text,
        'charts': message.charts or [],
        'created_at': message.created_at,
    }


def own_chats(user):
    """Faqat shu foydalanuvchining suhbatlari — boshqa superadminniki emas."""
    return AssistantChat.objects.filter(branch=user.branch, actor=user)


@transaction.atomic
def remember(user, chat_id, question, answer, charts):
    """Savol va javobni suhbatga yozadi; suhbat bo'lmasa yangisini ochadi."""
    chat = None
    if chat_id:
        chat = own_chats(user).filter(pk=chat_id).first()
        if not chat:
            raise serializers.ValidationError({'chat': _('Suhbat topilmadi.')})
    if not chat:
        chat = AssistantChat.objects.create(branch=user.branch, actor=user, title=make_title(question))
    AssistantMessage.objects.bulk_create([
        AssistantMessage(chat=chat, role='user', text=question),
        AssistantMessage(chat=chat, role='assistant', text=answer, charts=charts or []),
    ])
    # updated_at yangilanishi uchun: ro'yxat oxirgi faol suhbatdan boshlanadi.
    chat.save(update_fields=['updated_at'])
    return chat


class ChatRename(serializers.Serializer):
    title = serializers.CharField(max_length=TITLE_LENGTH, trim_whitespace=True)

    def validate_title(self, value):
        if not value.strip():
            raise serializers.ValidationError(_('Nom bo‘sh bo‘lishi mumkin emas.'))
        return value.strip()


class AssistantChatListView(APIView):
    """Suhbatlar ro'yxati."""

    permission_classes = [OwnerOnly]

    def get(self, request):
        chats = own_chats(request.user).prefetch_related('messages')[:60]
        rows = []
        for chat in chats:
            first = next((item for item in chat.messages.all() if item.role == 'user'), None)
            rows.append(chat_row(chat, first.text[:90] if first else ''))
        return Response({'chats': rows})


class AssistantChatDetailView(APIView):
    """Bitta suhbat: barcha gaplar yoki o'chirish."""

    permission_classes = [OwnerOnly]

    def get(self, request, pk):
        chat = own_chats(request.user).filter(pk=pk).first()
        if not chat:
            raise serializers.ValidationError(_('Suhbat topilmadi.'))
        messages = chat.messages.all()[:HISTORY_LIMIT]
        return Response({**chat_row(chat), 'messages': [message_row(item) for item in messages]})

    def patch(self, request, pk):
        """Suhbat nomini o'zgartiradi."""
        chat = own_chats(request.user).filter(pk=pk).first()
        if not chat:
            raise serializers.ValidationError(_('Suhbat topilmadi.'))
        data = ChatRename(data=request.data)
        data.is_valid(raise_exception=True)
        chat.title = data.validated_data['title']
        chat.save(update_fields=['title', 'updated_at'])
        return Response(chat_row(chat))

    def delete(self, request, pk):
        chat = own_chats(request.user).filter(pk=pk).first()
        if not chat:
            raise serializers.ValidationError(_('Suhbat topilmadi.'))
        chat.delete()
        return Response({'detail': _('Suhbat o‘chirildi.')}, status=200)
