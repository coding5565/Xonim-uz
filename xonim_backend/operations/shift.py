"""Kun yakuni: kassadagi naqd pulni tizim hisobi bilan solishtirish.

Kutilgan naqd = o'sha kundagi naqd savdo − o'sha kunda naqd to'langan xarajat.
Karta, Click, Uzum va Yandex kassada pul qoldirmaydi, shuning uchun kutilgan
naqdga kirmaydi — lekin kun manzarasi to'liq bo'lishi uchun ko'rsatiladi.

Yopilgandan keyin raqamlar muzlatiladi: o'sha kunga tegishli yozuv keyin
o'zgarsa ham yopilgan kun hisoboti o'zgarmaydi.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.i18n import _
from users.permissions import OwnerOnly, SalesOnly

from .models import (
    SALE_PAYMENT_METHODS,
    Expense,
    Order,
    PartnerDelivery,
    PartnerSettlement,
    ShiftClose,
    WaiterPayment,
)
from .money import day_window, money, platform_fee, takings
from .services import audit, safely

# Shu summadan katta farq e'tibor talab qiladi.
ALERT_SOM = Decimal('20000')
# Eng ko'pi bilan shuncha kun orqaga yopish mumkin.
BACKDATE_DAYS = 7


def day_figures(branch, day):
    """Bir kunning savdo va naqd manzarasi. Yopilmagan kun uchun jonli hisob."""
    since, until = day_window(day)
    paid = Order.objects.filter(branch=branch, status='paid', paid_at__gte=since, paid_at__lt=until)
    totals = paid.aggregate(
        revenue=Coalesce(Sum('total'), Decimal('0')),
        # Ofitsiantlar uchun yig'ilgan pul: kassada yotadi, lekin restoranniki emas.
        service=Coalesce(Sum('service_charge'), Decimal('0')),
        orders=Count('id'),
    )
    # Nom ataylab «amount»: `total=Sum('total')` maydonni yopib qo'yadi va
    # ushlanma ifodasidagi F('total') agregatga tushib ketardi.
    by_method = {
        row['payment_method']: row
        for row in paid.values('payment_method')
        .annotate(
            fee=platform_fee(), amount=takings(), count=Count('id'),
            sales=Coalesce(Sum('total'), Decimal('0')),
            tips=Coalesce(Sum('service_charge'), Decimal('0')),
        )
        .order_by('-amount')
    }
    cash_in = by_method.get('cash', {}).get('amount') or Decimal('0')
    # Maktab kechqurun naqd olib kelsa, u pul kassada yotadi. Hisobga
    # qo'shilmasa kassir har kuni sababsiz «ortiqcha» farq ko'rib yurardi.
    partner_rows = PartnerSettlement.objects.filter(
        branch=branch, paid_on=day, voided_at__isnull=True,
    ).aggregate(
        total=Coalesce(Sum('amount'), Decimal('0')),
        cash=Coalesce(Sum('amount', filter=Q(payment_method='cash')), Decimal('0')),
        count=Count('id'),
    )
    cash_in += partner_rows['cash']
    # Bugun jo'natilgan, lekin hisoboti kelmagan taom. Kunni yopish uni
    # yo'qotmaydi — qarz bo'lib qolaveradi — lekin kassir buni bilib
    # yopsin: kechqurun maktabga qo'ng'iroq qilish shu yerda eslanadi.
    unreported = PartnerDelivery.objects.filter(
        branch=branch, date=day, status='sent',
    ).aggregate(value=Coalesce(Sum('total'), Decimal('0')), count=Count('id'))
    # Kassadan naqd chiqqan xarajatlar va ofitsiantlarga naqd berilgan ulush.
    cash_out = Expense.objects.filter(
        branch=branch, date=day, payment_method='cash',
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    cash_out += WaiterPayment.objects.filter(
        branch=branch, paid_on=day, payment_method='cash',
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']

    # Har bir to'lov usuli doim ro'yxatda turadi, sotuvsizi ham nol bo'lib:
    # yo'q qator «tekshirilmagan» degani emasligini kassir ko'rib tursin.
    breakdown = []
    for method, label in SALE_PAYMENT_METHODS:
        row = by_method.get(method, {})
        amount = row.get('amount') or Decimal('0')
        # Uzum va Yandex savdo summasining bir qismini o'zida ushlab qoladi:
        # hisobga to'liq summa emas, qolgani tushadi. Kassir kun oxirida
        # platformadan qancha kutishini aniq bilishi kerak.
        fee = row.get('fee') or Decimal('0')
        breakdown.append({
            'method': method,
            'label': label,
            # `amount` — kassaga tushgan pul: hisob + ofitsiant xizmat haqi.
            # Ular alohida ham beriladi, chunki qatorlar yig'indisi
            # sahifadagi «tushum» bilan teng bo'lmaydi: xizmat haqi
            # tushum emas. Ilgari faqat `amount` bor edi va kassir
            # qatorlarni qo'shganda jami tushumdan katta chiqib qolardi.
            'amount': money(amount),
            'sales': money(row.get('sales') or Decimal('0')),
            'service': money(row.get('tips') or Decimal('0')),
            'count': row.get('count', 0),
            # Faqat naqd kassada qoladi.
            'in_drawer': method == 'cash',
            'fee': money(fee),
            'net': money(amount - fee),
        })
    return {
        'revenue': totals['revenue'],
        'service': totals['service'],
        # Hamkorlardan tushgan pul: savdo emas, lekin kassada yotadi.
        'partners': partner_rows['total'],
        'partners_cash': partner_rows['cash'],
        'partner_payments': partner_rows['count'],
        'partners_unreported': unreported['count'],
        'partners_unreported_value': unreported['value'],
        'orders': totals['orders'],
        'cash_in': cash_in,
        'cash_out': cash_out,
        'expected_cash': cash_in - cash_out,
        'breakdown': breakdown,
    }


class ShiftFilters(serializers.Serializer):
    date = serializers.DateField(required=False)

    def validate_date(self, value):
        today = timezone.localdate()
        if value > today:
            raise serializers.ValidationError(_('Kelajakdagi kunni yopib bo‘lmaydi.'))
        if (today - value).days > BACKDATE_DAYS:
            raise serializers.ValidationError(
                _('Faqat oxirgi {days} kunni yopish mumkin.').format(days=BACKDATE_DAYS))
        return value


class ShiftCloseInput(ShiftFilters):
    counted_cash = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'))
    note = serializers.CharField(max_length=250, allow_blank=True, default='')

    def validate(self, attrs):
        attrs.setdefault('date', timezone.localdate())
        return attrs


def close_payload(record):
    return {
        'date': record.date,
        'closed': True,
        'actor': record.actor.first_name or record.actor.username,
        'closed_at': record.created_at,
        'expected_cash': money(record.expected_cash),
        'counted_cash': money(record.counted_cash),
        'difference': money(record.difference),
        'revenue': money(record.revenue),
        'orders': record.orders,
        'breakdown': record.breakdown,
        'note': record.note,
        'alert': abs(record.difference) > ALERT_SOM,
    }


@transaction.atomic
def close_shift(user, data):
    day = data['date']
    if ShiftClose.objects.select_for_update().filter(branch=user.branch, date=day).exists():
        raise serializers.ValidationError({'date': _('Bu kun allaqachon yopilgan.')})
    figures = day_figures(user.branch, day)
    counted = data['counted_cash']
    difference = counted - figures['expected_cash']
    record = ShiftClose.objects.create(
        branch=user.branch, actor=user, date=day,
        expected_cash=figures['expected_cash'], counted_cash=counted, difference=difference,
        revenue=figures['revenue'], orders=figures['orders'],
        breakdown=figures['breakdown'], note=data['note'],
    )
    sign = '+' if difference > 0 else ''
    audit(
        user, 'shift.close',
        f'{day} · kutilgan {figures["expected_cash"]} · sanalgan {counted} · farq {sign}{difference} so‘m',
    )
    return record


class ShiftView(APIView):
    """Kassir kunni yopadi; ochiq kun uchun jonli hisob ko‘rsatiladi."""

    permission_classes = [SalesOnly]

    def get(self, request):
        filters = ShiftFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        day = filters.validated_data.get('date') or timezone.localdate()
        record = ShiftClose.objects.filter(branch=request.user.branch, date=day).select_related('actor').first()
        if record:
            return Response({**close_payload(record), 'backdate_days': BACKDATE_DAYS, 'alert_som': str(ALERT_SOM)})
        figures = day_figures(request.user.branch, day)
        # Ochiq hisoblar kassaga hali tushmagan — kassirni ogohlantiramiz.
        still_open = Order.objects.filter(branch=request.user.branch, status='open').count()
        return Response({
            'date': day,
            'closed': False,
            'expected_cash': money(figures['expected_cash']),
            'cash_in': money(figures['cash_in']),
            'cash_out': money(figures['cash_out']),
            'revenue': money(figures['revenue']),
            'service': money(figures['service']),
            'partners': money(figures['partners']),
            'partners_cash': money(figures['partners_cash']),
            'partner_payments': figures['partner_payments'],
            'partners_unreported': figures['partners_unreported'],
            'partners_unreported_value': money(figures['partners_unreported_value']),
            'orders': figures['orders'],
            'breakdown': figures['breakdown'],
            'open_orders': still_open,
            'backdate_days': BACKDATE_DAYS,
            'alert_som': str(ALERT_SOM),
        })

    def post(self, request):
        data = ShiftCloseInput(data=request.data)
        data.is_valid(raise_exception=True)
        # Ikkinchi kassir shu kunni tekshiruv bilan yozuv orasida yopib
        # ulgursa, unique cheklov ishlaydi. Bu 409, 500 emas.
        return Response(close_payload(safely(close_shift, request.user, data.validated_data)), status=201)


class ShiftHistoryView(APIView):
    """Yopilgan kunlar tarixi — farq qayerda paydo bo‘lganini ko‘rish uchun."""

    permission_classes = [OwnerOnly]

    def get(self, request):
        rows = ShiftClose.objects.filter(branch=request.user.branch).select_related('actor')[:60]
        records = [close_payload(row) for row in rows]
        gap = sum((Decimal(row['difference']) for row in records), Decimal('0'))
        return Response({
            'days': records,
            'summary': {
                'closed_days': len(records),
                'total_difference': money(gap),
                'alerts': sum(1 for row in records if row['alert']),
                'alert_som': str(ALERT_SOM),
            },
        })
