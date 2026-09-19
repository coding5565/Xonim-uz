"""Kun yakuni: kassadagi naqd pulni tizim hisobi bilan solishtirish.

Kutilgan naqd = o'sha kundagi naqd savdo − o'sha kunda naqd to'langan xarajat.
Karta, Click, Uzum va Yandex kassada pul qoldirmaydi, shuning uchun kutilgan
naqdga kirmaydi — lekin kun manzarasi to'liq bo'lishi uchun ko'rsatiladi.

Yopilgandan keyin raqamlar muzlatiladi: o'sha kunga tegishli yozuv keyin
o'zgarsa ham yopilgan kun hisoboti o'zgarmaydi.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.i18n import _
from users.permissions import OwnerOnly, SalesOnly

from .models import SALE_PAYMENT_METHODS, Expense, Order, ShiftClose
from .money import day_window, money
from .services import audit

# Shu summadan katta farq e'tibor talab qiladi.
ALERT_SOM = Decimal('20000')
# Eng ko'pi bilan shuncha kun orqaga yopish mumkin.
BACKDATE_DAYS = 7


def day_figures(branch, day):
    """Bir kunning savdo va naqd manzarasi. Yopilmagan kun uchun jonli hisob."""
    since, until = day_window(day)
    paid = Order.objects.filter(branch=branch, status='paid', paid_at__gte=since, paid_at__lt=until)
    totals = paid.aggregate(revenue=Coalesce(Sum('total'), Decimal('0')), orders=Count('id'))
    by_method = {
        row['payment_method']: row
        for row in paid.values('payment_method').annotate(total=Sum('total'), count=Count('id')).order_by('-total')
    }
    cash_in = by_method.get('cash', {}).get('total') or Decimal('0')
    # Kassadan naqd chiqqan xarajatlar.
    cash_out = Expense.objects.filter(
        branch=branch, date=day, payment_method='cash',
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']

    # Har bir to'lov usuli doim ro'yxatda turadi, sotuvsizi ham nol bo'lib:
    # yo'q qator «tekshirilmagan» degani emasligini kassir ko'rib tursin.
    breakdown = [{
        'method': method,
        'label': label,
        'amount': money(by_method.get(method, {}).get('total')),
        'count': by_method.get(method, {}).get('count', 0),
        # Faqat naqd kassada qoladi.
        'in_drawer': method == 'cash',
    } for method, label in SALE_PAYMENT_METHODS]
    return {
        'revenue': totals['revenue'],
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
            raise serializers.ValidationError(f'Faqat oxirgi {BACKDATE_DAYS} kunni yopish mumkin.')
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
            'orders': figures['orders'],
            'breakdown': figures['breakdown'],
            'open_orders': still_open,
            'backdate_days': BACKDATE_DAYS,
            'alert_som': str(ALERT_SOM),
        })

    def post(self, request):
        data = ShiftCloseInput(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(close_payload(close_shift(request.user, data.validated_data)), status=201)


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
