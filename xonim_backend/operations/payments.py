"""Hisob bir necha usul bilan to'langanda pulni qanday yozish.

130 000 so'mlik hisobning 100 mingi kartadan, 30 mingi naqd bo'lishi
mumkin. Kassir ASOSIY usulni tanlaydi, so'ng bitta katakka ikkinchi
usuldan qancha kelganini yozadi. Hammasi bitta usul bilan bo'lsa u katak
nol bo'lib turaveradi va hech narsa o'zgarmaydi.

Butun mantiq shu yerda turadi, chunki uni ikki yo'l ishlatadi: hisob
darhol to'langanda va ochiq hisob keyin yopilganda. Ikki nusxa bo'lsa
ular sekin-asta ajralib ketardi va ajralgani aynan kassadagi naqdda
ko'rinardi.
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from rest_framework.exceptions import ValidationError

from core.i18n import _

from .models import (
    DELIVERY_CHANNELS,
    SALE_PAYMENT_LABELS,
    SALE_PAYMENT_METHODS,
    OrderPayment,
)

ZERO = Decimal('0')
PENNY = Decimal('0.01')

# Yetkazib berish platformalari bo'linmaydi: pul mijozdan emas,
# platformadan keladi va u bitta o'tkazma bo'lib tushadi.
SPLITTABLE = tuple(
    key for key, _label in SALE_PAYMENT_METHODS if key not in DELIVERY_CHANNELS
)


def label(method):
    return _(SALE_PAYMENT_LABELS.get(method, method))


def check_split(order, method, split_method, split_amount):
    """Bo'linish qoidalarini tekshiradi. Bo'linish yo'q bo'lsa jim o'tadi."""
    if not split_method and not split_amount:
        return ZERO
    if order.channel in DELIVERY_CHANNELS:
        raise ValidationError({'split_method': _(
            'Yetkazib berish buyurtmasi bo‘lib to‘lanmaydi — pul platformadan keladi.')})
    if not split_method:
        raise ValidationError({'split_method': _('Ikkinchi to‘lov usulini tanlang.')})
    if split_method == method:
        raise ValidationError({'split_method': _(
            'Ikkinchi usul birinchisidan boshqa bo‘lishi kerak.')})
    if split_method not in SPLITTABLE:
        raise ValidationError({'split_method': _('Bu usul bilan bo‘lib to‘lab bo‘lmaydi.')})
    if method not in SPLITTABLE:
        raise ValidationError({'payment_method': _('Bu usul bilan bo‘lib to‘lab bo‘lmaydi.')})

    amount = Decimal(split_amount or 0).quantize(PENNY, rounding=ROUND_HALF_UP)
    if amount <= ZERO:
        raise ValidationError({'split_amount': _('Ikkinchi usuldagi summa noldan katta bo‘lsin.')})
    if amount >= order.payable:
        # Teng bo'lsa bu bo'linish emas — shunchaki boshqa usul tanlangan.
        raise ValidationError({'split_amount': _(
            'Ikkinchi usuldagi summa hisobdan kichik bo‘lishi kerak. '
            'Hammasi shu usul bilan bo‘lsa, uni asosiy qilib tanlang.')})
    return amount


def split_shares(order, amount):
    """Berilgan summaning tushum va xizmat haqi ulushini hisoblaydi.

    Hisobning ichida ikki xil pul bor: taom puli (restoranniki) va
    ofitsiant xizmat haqi (ofitsiantniki). Bo'lib to'langanda har bir
    qismga ikkalasidan ham nisbatan tushadi — aks holda «kartadan qancha
    tushum keldi» degan savol javobsiz qolardi.

    Xizmat haqi bo'lmasa hammasi tushum bo'ladi va hech qanday yaxlitlash
    yuz bermaydi — kundalik holat aynan shu.
    """
    if not order.service_charge:
        return amount, ZERO
    sales = (amount * order.total / order.payable).quantize(PENNY, rounding=ROUND_HALF_UP)
    return sales, amount - sales


def record_payments(order, method, split_method='', split_amount=None):
    """Hisobning to'lov qatorlarini yozadi.

    Qaytaradi: yozilgan qatorlar. Bo'linish bo'lmasa bitta qator.

    Qoldiq ASOSIY qatorga qoladi: ikkinchi qismni kassir o'z qo'li bilan
    yozgan, ya'ni u aniq raqam. Yaxlitlashdan qolgan tiyin esa asosiy
    tomonga tushishi kerak, aks holda kassir yozgan raqam o'zgarib
    ketardi.
    """
    OrderPayment.objects.filter(order=order).delete()
    payable = order.payable
    second = check_split(order, method, split_method, split_amount)

    rows = []
    if second:
        sales, service = split_shares(order, second)
        rows.append(OrderPayment(
            order=order, method=split_method, amount=second, sales=sales, service=service))
        first = payable - second
        rows.append(OrderPayment(
            order=order, method=method, amount=first,
            sales=order.total - sales, service=order.service_charge - service))
    elif payable > ZERO:
        rows.append(OrderPayment(
            order=order, method=method, amount=payable,
            sales=order.total, service=order.service_charge))
    OrderPayment.objects.bulk_create(rows)
    return rows


def payment_text(order):
    """Jurnal va chek uchun: «Naqd 100 000 + Karta 30 000»."""
    rows = list(order.payments.all())
    if len(rows) < 2:
        return label(order.payment_method)
    return ' + '.join(f'{label(row.method)} {row.amount}' for row in rows)


def method_totals(orders):
    """Har bir usul bo'yicha kassaga tushgan summa, tushum va xizmat haqi.

    Buyurtma emas, TO'LOV qatorlari yig'iladi — shuning uchun bo'lingan
    hisob o'z-o'zidan ikkala usulga to'g'ri tarqaladi va hech qayerda
    qo'shimcha arifmetika kerak emas.
    """
    return {
        row['method']: row
        for row in OrderPayment.objects.filter(order__in=orders).values('method').annotate(
            amount=Coalesce(Sum('amount'), ZERO),
            sales=Coalesce(Sum('sales'), ZERO),
            service=Coalesce(Sum('service'), ZERO),
            count=Count('order_id', distinct=True),
        )
    }
