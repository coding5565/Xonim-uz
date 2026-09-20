"""Server xabarlarini foydalanuvchi tiliga o'girish.

Nega gettext emas: .po fayllarni .mo ga kompilyatsiya qilish uchun GNU
gettext kerak, u Windowsda har doim ham bo'lmaydi. Bu yerda oddiy lug'at
ishlatiladi — hech qanday qo'shimcha dastur talab qilmaydi va loyihaning
boshqa qismlari kabi bog'liqliksiz qoladi.

Kalit — o'zbekcha matnning O'ZI. Shuning uchun:
  · tarjima topilmasa o'zbekcha ko'rinadi, bo'sh joy chiqmaydi;
  · mavjud kodni qayta yozish shart emas, `_()` bilan o'rash yetadi.

Tilni Django'ning LocaleMiddleware'i Accept-Language sarlavhasidan aniqlaydi.
"""
from django.utils.translation import get_language

from .translations import EN, RU

CATALOGUES = {'ru': RU, 'en': EN}


def translate(text, lang=None):
    """Matnni joriy tilga o'giradi; tarjima yo'q bo'lsa o'zini qaytaradi."""
    code = (lang or get_language() or 'uz')[:2]
    return CATALOGUES.get(code, {}).get(text, text)


# Kodda qisqa yozilishi uchun: _('Buyurtma topilmadi.')
_ = translate


def translate_all(rows, lang=None):
    """Ro'yxatdagi matnlarni birdaniga o'giradi."""
    return [translate(row, lang) for row in rows]
