"""Chop etish navbati va restorandagi agent bilan aloqa.

Bulutdagi server restoran ichidagi USB printerga yeta olmaydi. Shuning
uchun u talonni ESC/POS baytlariga aylantirib navbatga qo'yadi, restoran
kompyuterida turgan agent esa navbatni o'zi so'rab oladi va printerga
yuboradi.

Yo'nalish muhim: aloqani HAR DOIM agent boshlaydi. Shu sababli restoranda
na oq IP, na ochiq port, na VPN kerak — faqat oddiy chiquvchi internet.

Ishonchlilik shundan kelib chiqadi: internet uzilsa talon navbatda turadi
va aloqa tiklangach chiqadi. Agent talonni olib, lekin chop eta olmasa,
ijara muddati tugagach u navbatga o'zi qaytadi — «olindi-yu yo'qoldi»
degan holat bo'lmaydi.
"""
import base64
import hmac
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import PrintJob

logger = logging.getLogger(__name__)

# Agent bir martada shuncha topshiriq oladi.
BATCH = 10
# Shuncha urinishdan keyin topshiriq «chiqmadi» deb belgilanadi va
# navbatni tiqilib qolishdan saqlaydi.
MAX_ATTEMPTS = 5


def queue_mode():
    """Talon navbatga qo'yiladimi yoki to'g'ridan-to'g'ri printerga ketadimi.

    Restoran ichidagi o'rnatishda `direct` qoladi: u yerda printer shu
    kompyuterga ulangan va navbatning hojati yo'q.
    """
    return getattr(settings, 'PRINT_MODE', 'direct') == 'agent'


def enqueue(branch, station, data, *, kind='', order=None):
    PrintJob.objects.create(
        branch=branch, station=station, kind=kind, payload=bytes(data), order=order,
    )


def reclaim_expired():
    """Agent olib ketgan-u, javob bermagan topshiriqlarni qaytaradi.

    Agent yiqilsa yoki kompyuter o'chsa, topshiriq «printing» holatida
    muzlab qolardi va hech qachon chiqmasdi.
    """
    lease = int(getattr(settings, 'PRINT_LEASE_SECONDS', 120))
    cutoff = timezone.now() - timezone.timedelta(seconds=lease)
    return PrintJob.objects.filter(status='printing', claimed_at__lt=cutoff).update(
        status='queued', agent='', claimed_at=None,
    )


class AgentAuth(AllowAny):
    """Agent foydalanuvchi emas — u umumiy maxfiy so'z bilan taniladi."""


def agent_allowed(request):
    token = getattr(settings, 'PRINT_AGENT_TOKEN', '')
    sent = request.headers.get('X-Print-Agent-Token', '')
    return bool(token) and hmac.compare_digest(token, sent)


class ClaimInput(serializers.Serializer):
    agent = serializers.CharField(max_length=60)
    stations = serializers.ListField(
        child=serializers.CharField(max_length=10), allow_empty=False, max_length=5,
    )
    branch = serializers.SlugField(max_length=50)


class PrintClaimView(APIView):
    """Agent o'ziga tegishli topshiriqlarni oladi."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not agent_allowed(request):
            return Response({'detail': 'Ruxsat yo‘q.'}, status=403)
        data = ClaimInput(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data

        reclaim_expired()
        now = timezone.now()
        with transaction.atomic():
            # `select_for_update(skip_locked=True)`: ikkita agent bir vaqtda
            # so'rasa bir xil talonni ikki marta chop etmasin.
            rows = list(
                PrintJob.objects.select_for_update(skip_locked=True)
                .filter(
                    branch__slug=fields['branch'],
                    status='queued',
                    station__in=fields['stations'],
                    attempts__lt=MAX_ATTEMPTS,
                )
                .order_by('id')[:BATCH]
            )
            if rows:
                PrintJob.objects.filter(id__in=[row.id for row in rows]).update(
                    status='printing', agent=fields['agent'], claimed_at=now,
                )
        return Response({'jobs': [{
            'id': row.id,
            'station': row.station,
            'kind': row.kind,
            'order': row.order_id,
            # Baytlar JSON'da yuborilmaydi, shuning uchun base64.
            'payload': base64.b64encode(bytes(row.payload)).decode(),
        } for row in rows]})


class AckInput(serializers.Serializer):
    id = serializers.IntegerField(min_value=1)
    ok = serializers.BooleanField()
    error = serializers.CharField(max_length=300, allow_blank=True, default='')


class PrintAckView(APIView):
    """Agent natijani xabar qiladi: chiqdi yoki chiqmadi."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        if not agent_allowed(request):
            return Response({'detail': 'Ruxsat yo‘q.'}, status=403)
        data = AckInput(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data

        job = PrintJob.objects.filter(pk=fields['id']).first()
        if not job:
            return Response({'ok': True})
        if fields['ok']:
            job.status = 'done'
            job.done_at = timezone.now()
            job.error = ''
        else:
            job.attempts += 1
            job.error = fields['error'][:300]
            # Urinishlar tugasa to'xtaymiz: aks holda nosoz printer
            # navbatni cheksiz aylantirib turardi.
            job.status = 'failed' if job.attempts >= MAX_ATTEMPTS else 'queued'
            job.agent = ''
            job.claimed_at = None
            logger.warning('Talon chiqmadi: #%s %s', job.id, job.error)
        job.save(update_fields=['status', 'attempts', 'error', 'agent', 'claimed_at', 'done_at'])
        return Response({'ok': True})
