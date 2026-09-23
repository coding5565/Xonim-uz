"""Chop etish agentining yangilanish kanali.

Agent restoran kompyuterida turadi va uni qo'lda yangilash kerak bo'lsa,
amalda hech qachon yangilanmaydi: birov borib o'rnatishi kerak. Shuning
uchun agent o'zi soatiga bir marta serverdan so'raydi — «yangi versiya
bormi?» — va topsa o'zini almashtiradi.

Fayl serverdagi diskda yotadi (`AGENT_DIR`), yonida esa manifest: qaysi
versiya, qancha hajm va SHA-256 yig'indisi. Yig'indi majburiy: yarim
yuklangan yoki buzilgan fayl bilan o'zini almashtirgan agent boshqa
ishga tushmasdi va uni faqat qo'lda tiklash mumkin bo'lardi.

Yuklab olish ham, tekshirish ham agent tokeni bilan himoyalangan: bu
fayl restoran kompyuterida ishga tushadigan dastur, uni internetdan
hammaga ochiq qoldirib bo'lmaydi.
"""
import hashlib
import json
import logging
from pathlib import Path

from django.conf import settings
from django.http import FileResponse
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .print_queue import agent_allowed

logger = logging.getLogger(__name__)

MANIFEST = 'manifest.json'


def agent_dir():
    path = Path(getattr(settings, 'AGENT_DIR', '/var/lib/xonim/agent'))
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_manifest():
    """Joriy versiya haqidagi ma'lumot. Hali chiqarilmagan bo'lsa — None."""
    path = agent_dir() / MANIFEST
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (ValueError, OSError):
        logger.warning('Agent manifesti o‘qilmadi')
        return None
    if not (agent_dir() / data.get('file', '')).exists():
        # Manifest bor, fayl yo'q — agent yuklab ololmaydigan versiyani
        # ko'rsatib qo'ymaymiz.
        return None
    return data


def publish(source, version, notes=''):
    """Yangi versiyani chiqaradi: faylni ko'chiradi va manifest yozadi."""
    source = Path(source)
    data = source.read_bytes()
    target_name = f'xonim-agent-{version}.exe'
    (agent_dir() / target_name).write_bytes(data)
    manifest = {
        'version': version,
        'file': target_name,
        'size': len(data),
        'sha256': hashlib.sha256(data).hexdigest(),
        'notes': notes,
    }
    (agent_dir() / MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    # Eski nusxalar qoladi: yangi versiya yiqilsa, oldingisiga qaytish
    # uchun fayl serverda turishi kerak.
    return manifest


class AgentVersionView(APIView):
    """Agent soatiga bir marta shu yerga qaraydi."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        if not agent_allowed(request):
            return Response({'detail': 'Ruxsat yo‘q.'}, status=403)
        manifest = read_manifest()
        if not manifest:
            # Versiya chiqarilmagan — bu xato emas. Agent shunchaki
            # o'zidagini ishlatishda davom etadi.
            return Response({'version': None})
        return Response({
            'version': manifest['version'],
            'size': manifest['size'],
            'sha256': manifest['sha256'],
            'notes': manifest.get('notes', ''),
        })


class AgentDownloadView(APIView):
    """Yangi versiyani beradi. Faqat token bilan."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        if not agent_allowed(request):
            return Response({'detail': 'Ruxsat yo‘q.'}, status=403)
        manifest = read_manifest()
        if not manifest:
            return Response({'detail': 'Versiya chiqarilmagan.'}, status=404)
        path = agent_dir() / manifest['file']
        return FileResponse(
            path.open('rb'), as_attachment=True, filename=manifest['file'],
            content_type='application/octet-stream',
        )
