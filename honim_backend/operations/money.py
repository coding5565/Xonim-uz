"""Pul, miqdor va sana bilan ishlashning yagona qoidalari.

Bu modul hech qanday modelni import qilmaydi, shuning uchun uni istalgan
joydan chaqirish mumkin va aylanma bog'liqlik hosil bo'lmaydi.

Nega bitta joyda: ilgari `money()` beshta modulda alohida yozilgan edi va
ular sekin-asta bir-biridan uzoqlashdi — `/sales/summary/` «0» qaytarsa,
`/finance/` «0.00» qaytarardi. Bir xil raqamning ikki xil ko'rinishi
hisobotlarni solishtirishni buzadi.

Diqqat: chekdagi pul boshqacha ko'rinadi (`40 000`, tiyinsiz, probel bilan)
— u `operations/printing.py` dagi `som_text()` ning ishi, bu yerdagi
`money()` esa API javoblari uchun.
"""
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import DecimalField
from django.utils import timezone
from rest_framework import serializers

from core.i18n import _

ZERO = Decimal('0')
CENT = Decimal('0.01')
MILLI = Decimal('0.001')
# Aggregatsiyalarda F() ifodalari uchun aniq tur — aks holda Django
# natijaning turini taxmin qiladi.
MONEY = DecimalField(max_digits=18, decimal_places=2)
QUANTITY = DecimalField(max_digits=18, decimal_places=3)

MONTH_NAMES = [
    'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
    'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr',
]


def money(value):
    """Pulni API uchun bir xil ko'rinishda qaytaradi: doim ikki kasr.

    Nol qo'shilishi manfiy nolni («-0.00») oddiy nolga aylantiradi —
    ayirmalar yaxlitlanganda shunday chiqib qolishi mumkin.
    """
    return str((value if value is not None else ZERO).quantize(CENT) + ZERO)


def quantity(value):
    """Miqdor uchun uch kasr: kg va litr grammgacha aniq bo'lishi kerak."""
    return str((value if value is not None else ZERO).quantize(MILLI) + ZERO)


def percent(part, whole):
    """Ulush foizda. Bo'luvchi nol bo'lsa nol qaytadi."""
    return str((part / whole * 100).quantize(CENT)) if whole else '0.00'


def share(part, whole):
    """Ulush foizda, lekin bo'luvchi nol bo'lsa BO'SH qaytadi.

    «Nol ulush» bilan «noma'lum» bir xil narsa emas: masalliq narxi
    kiritilmagan bo'lsa uning ulushini hisoblab bo'lmaydi, nol deb
    ko'rsatish esa yolg'on bo'lardi.
    """
    return str((part / whole * 100).quantize(CENT)) if whole else ''


def day_window(start, end=None):
    """Mahalliy kun(lar)ni aniq vaqt oralig'iga aylantiradi.

    `__date` lookup o'rniga oraliq ishlatiladi: chegara Asia/Tashkent
    bo'yicha aniq bo'ladi va indeksdan foydalanish mumkin qoladi.
    """
    final = end if end is not None else start
    return (
        timezone.make_aware(datetime.combine(start, time.min)),
        timezone.make_aware(datetime.combine(final + timedelta(days=1), time.min)),
    )


def parse_month(value):
    """«YYYY-MM» matnini oyning birinchi kuniga aylantiradi.

    Oy tekshiruvi uch joyda alohida yozilgan edi va har birida boshqa teshik
    qolgan: 0000-01 kabi qiymat `year 0 is out of range` bilan 500 berardi.
    Shuning uchun tekshiruv bitta joyga yig'ildi.
    """
    try:
        year, month = value.split('-')
        first = date(int(year), int(month), 1)
    except (TypeError, ValueError):
        raise serializers.ValidationError(_('Oy noto‘g‘ri. Format: YYYY-MM.')) from None
    if not 2000 <= first.year <= 2100:
        raise serializers.ValidationError(_('Oy noto‘g‘ri. Format: YYYY-MM.'))
    return first


def month_key(period):
    return period.strftime('%Y-%m')


def month_label(period):
    return f'{period.year}-yil {MONTH_NAMES[period.month - 1]}'


def short_label(period):
    return f'{MONTH_NAMES[period.month - 1][:3]} {period.year}'


def next_month(period):
    return (period.replace(day=28) + timedelta(days=4)).replace(day=1)


def previous_month(period):
    return (period.replace(day=1) - timedelta(days=1)).replace(day=1)


def month_end(period):
    return next_month(period) - timedelta(days=1)


def last_months(final, count):
    """Oxirgi `count` oy, eskisidan yangisiga qarab."""
    months = [final.replace(day=1)]
    while len(months) < count:
        months.append(previous_month(months[-1]))
    return list(reversed(months))
