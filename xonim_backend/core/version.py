"""Qaysi versiya ishlayapti va unda nima o'zgargani.

Ikki xil narsa birga turadi va ularni aralashtirmaslik kerak:

  · MUHR — `build_stamp.py` dagi commit izi. Uni `git archive` yozadi,
    ya'ni har yangilanishda o'zi o'zgaradi va uni hech kim unuta olmaydi.
    Bu «serverda aynan qaysi kod turibdi» degan savolga javob.

  · IZOHLAR — `releases.py` dagi qo'lda yozilgan ro'yxat. Bu «nima
    o'zgardi» degan savolga javob va uni odam yozadi.

Ikkalasi bitta arxivda yuradi, shuning uchun ular hech qachon bir-biridan
ajralib qolmaydi: eski versiyaga qaytarilsa, eski izohlar ham qaytadi va
kelajakdagi yozuvlar o'z-o'zidan yo'qoladi.
"""
from django.utils.translation import get_language
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import BranchMember

from .build_stamp import COMMIT, COMMITTED_AT
from .releases import RELEASES

# Muhr almashtirilmagan bo'lsa qiymat shu bilan boshlanadi. Lokal ishlab
# chiqishda doim shunday: arxiv yasalmagan, demak git hech narsa yozmagan.
PLACEHOLDER = '$Format'

LANGUAGES = ('uz', 'ru', 'en')


def stamped():
    """Kod arxivdan kelganmi. Lokal ishlab chiqishda — yo'q."""
    return not COMMIT.startswith(PLACEHOLDER)


def build_info():
    """Ishlab turgan kodning izi.

    Muhr yo'q bo'lsa `commit` ham `committed_at` ham bo'sh qaytadi —
    `$Format:%h$` degan matnni ekranga chiqarish yolg'on bo'lardi.
    """
    if not stamped():
        return {'commit': '', 'committed_at': '', 'stamped': False}
    return {
        'commit': COMMIT,
        # Sana ISO 8601 ko'rinishida, commit qilingan joyning ofseti bilan
        # (+05:00). Frontend uni o'sha ofsetda emas, Asia/Tashkent bo'yicha
        # ko'rsatadi — loyihaning qolgan hamma sanasi ham shunday.
        'committed_at': COMMITTED_AT,
        'stamped': True,
    }


def pick(row, lang):
    """Yozuvdan tilga mos matnni oladi; yo'q bo'lsa o'zbekchasi."""
    return row.get(lang) or row['uz']


def release_payload(release, role, lang):
    changes = [
        {'kind': change['kind'], 'text': pick(change, lang)}
        for change in release['changes']
        # Kassirga moliya zanjiridagi o'zgarish kerak emas: u nima
        # qilishini bilmaydi va ro'yxatni uzaytirib, o'ziga tegishlisini
        # ko'rinmas qilib qo'yadi.
        if role in change['roles']
    ]
    return {
        'version': release['version'],
        'released': release['released'],
        'title': pick(release['title'], lang),
        'changes': changes,
    }


def releases_for(role, lang):
    """Rolga tegishli o'zgarishi bor versiyalar, yangisidan boshlab.

    O'zgarishi qolmagan versiya butunlay tushib qoladi: sarlavhasi bor,
    ichi bo'sh yozuv foydalanuvchini chalg'itadi.
    """
    rows = [release_payload(release, role, lang) for release in RELEASES]
    return [row for row in rows if row['changes']]


def current_version():
    """Hozirgi versiya raqami — ro'yxatning eng yuqorisi."""
    return RELEASES[0]['version'] if RELEASES else ''


class VersionView(APIView):
    """Ishlab turgan versiya va uning izohlari.

    Hamma rolga ochiq: oshxona xodimi ham nima o'zgarganini bilishi
    mumkin, garchi ro'yxatda unga tegishlisi kam bo'lsa ham.
    """

    permission_classes = [BranchMember]

    def get(self, request):
        lang = (get_language() or 'uz')[:2]
        if lang not in LANGUAGES:
            lang = 'uz'
        role = request.user.role
        return Response({
            'version': current_version(),
            'build': build_info(),
            'releases': releases_for(role, lang),
        })
