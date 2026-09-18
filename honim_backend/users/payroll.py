"""Superadmin uchun oyliklar tahlili.

Bu yerda ikki xil raqam bor va ular adashtirilmasligi kerak:
  · kelishilgan oylik — User.salary, ya'ni xodimga oyiga qancha to'lash kelishilgan;
  · to'langan oylik — SalaryPayment.amount, ya'ni haqiqatda qancha berilgan.
Farqi — qarzdorlik. Ikkalasi ham oy bo'yicha guruhlanadi: SalaryPayment.period
oyning birinchi kuniga qadalgan sana, paid_on esa pul berilgan kun.

Diqqat: oylik to'lovi «Ish haqi» kategoriyasida Expense ham yaratadi, shuning
uchun moliya hisobida oylik xarajatlarning ICHIDA turadi, ustiga qo'shilmaydi.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Count, Max, Min, Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from operations.models import SalaryPayment

from .models import User
from .permissions import OwnerOnly

MONTH_NAMES = [
    'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
    'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr',
]
METHOD_LABELS = {'cash': 'Naqd', 'card': 'Karta'}
TREND_MONTHS = 12
CENT = Decimal('0.01')


def money(value):
    """Pulni bir xil ko'rinishda qaytaradi.

    SQLite'da Sum() ba'zan kasrsiz Decimal beradi, shuning uchun frontend
    bir joyda «3000000», boshqa joyda «3000000.00» ko'rmasligi uchun tekislaymiz.
    """
    return str((value or Decimal('0')).quantize(CENT))


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


def last_months(final, count):
    """Oxirgi `count` oy, eskisidan yangisiga qarab."""
    months = [final.replace(day=1)]
    while len(months) < count:
        months.append(previous_month(months[-1]))
    return list(reversed(months))


def known_months(branch, today):
    """Birinchi to'lov yoki birinchi ishga olishdan bugungacha — yangisi birinchi."""
    first_payment = SalaryPayment.objects.filter(branch=branch).order_by('period').values_list('period', flat=True).first()
    first_hire = User.objects.filter(branch=branch, hired_at__isnull=False).order_by('hired_at').values_list('hired_at', flat=True).first()
    known = [item for item in (first_payment, first_hire) if item]
    cursor = min(known).replace(day=1) if known else today.replace(day=1)
    months = []
    while cursor <= today.replace(day=1):
        months.append(month_key(cursor))
        cursor = next_month(cursor)
    return list(reversed(months))


class PayrollFilters(serializers.Serializer):
    month = serializers.RegexField(r'^\d{4}-\d{2}$', required=False)

    def validate_month(self, value):
        year, month = value.split('-')
        if not 1 <= int(month) <= 12:
            raise serializers.ValidationError('Oy 01 dan 12 gacha bo‘lishi kerak.')
        return date(int(year), int(month), 1)


def month_breakdown(branch, period, staff):
    """Tanlangan oyda har bir xodim qancha olishi kerak va qancha olgan."""
    payments = {
        payment.employee_id: payment
        for payment in SalaryPayment.objects.filter(branch=branch, period=period)
    }
    rows = []
    agreed_total = paid_total = debt = Decimal('0')
    expected = covered = 0
    for person in staff:
        payment = payments.get(person.id)
        agreed = person.salary or Decimal('0')
        paid = payment.amount if payment else Decimal('0')
        # Ishdan bo'shagan xodim uchun kelishilgan summa hisoblanmaydi.
        if person.is_active:
            agreed_total += agreed
        paid_total += paid

        if not agreed:
            # Oylik summasi kiritilmagan: buni «to'lanmagan» deb ko'rsatish
            # noto'g'ri bo'lardi — qarz ham, qamrov ham hisoblanmaydi.
            status = 'no_agreement'
        elif payment:
            status = 'paid' if paid >= agreed else 'partial'
        else:
            status = 'unpaid'

        if person.is_active and agreed:
            expected += 1
            if payment:
                covered += 1
            # Qarz har xodim bo'yicha alohida hisoblanadi: ortiqcha to'langan
            # bir xodim boshqasining qarzini yopib yubormasligi kerak.
            debt += max(agreed - paid, Decimal('0'))

        rows.append({
            'id': person.id,
            'name': person.first_name or person.username,
            'username': person.username,
            'role': person.role,
            'role_label': person.get_role_display(),
            'active': person.is_active,
            'agreed': money(agreed),
            'paid': money(paid),
            'difference': money(max(agreed - paid, Decimal('0')) if agreed else Decimal('0')),
            'status': status,
            'paid_on': payment.paid_on if payment else None,
            'payment_method': payment.payment_method if payment else '',
            'payment_label': METHOD_LABELS.get(payment.payment_method, '') if payment else '',
            'note': payment.note if payment else '',
        })
    return {
        'rows': rows,
        'agreed': agreed_total,
        'paid': paid_total,
        'debt': debt,
        'payments': len(payments),
        'expected': expected,
        'covered': covered,
    }


def build_payroll(branch, period, today):
    """Bir oyning kesimi, 12 oylik tendensiya va umriy jamlanma."""
    staff = list(
        User.objects.filter(branch=branch)
        .exclude(role=User.Role.OWNER)
        .order_by('role', 'first_name', 'username')
    )
    breakdown = month_breakdown(branch, period, staff)

    # Har aggregatsiyada tartib aniq beriladi: modelning Meta.ordering'i
    # GROUP BY'ga qo'shilib jamini bo'lib yuborardi.
    by_method = [{
        'method': row['payment_method'],
        'label': METHOD_LABELS.get(row['payment_method'], row['payment_method']),
        'amount': money(row['total']),
        'count': row['count'],
    } for row in SalaryPayment.objects.filter(branch=branch, period=period)
        .values('payment_method').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')]

    months = last_months(today, TREND_MONTHS)
    by_period = {
        row['period']: row
        for row in SalaryPayment.objects.filter(branch=branch, period__gte=months[0])
        .values('period').annotate(total=Sum('amount'), count=Count('id')).order_by('period')
    }
    trend = [{
        'period': month_key(item),
        'label': short_label(item),
        'total': money(by_period.get(item, {}).get('total')),
        'count': by_period.get(item, {}).get('count', 0),
    } for item in months]

    names = {person.id: person.first_name or person.username for person in staff}
    lifetime = [{
        'id': row['employee_id'],
        'name': names.get(row['employee_id'], '—'),
        'total': money(row['total']),
        'months': row['count'],
        'first': month_key(row['first']),
        'last': month_key(row['last']),
    } for row in SalaryPayment.objects.filter(branch=branch)
        .values('employee_id')
        .annotate(total=Sum('amount'), count=Count('id'), first=Min('period'), last=Max('period'))
        .order_by('-total')]

    grand = SalaryPayment.objects.filter(branch=branch).aggregate(total=Sum('amount'), count=Count('id'))
    return {
        'month': month_key(period),
        'month_label': month_label(period),
        'months': known_months(branch, today),
        'summary': {
            'agreed': money(breakdown['agreed']),
            'paid': money(breakdown['paid']),
            'remaining': money(breakdown['debt']),
            'paid_count': breakdown['payments'],
            'staff_count': sum(1 for person in staff if person.is_active),
            # Oyligi kelishilgan nechta xodimdan nechtasiga to'langan.
            'expected': breakdown['expected'],
            'covered': breakdown['covered'],
            'without_agreement': sum(
                1 for row in breakdown['rows'] if row['status'] == 'no_agreement' and row['active']
            ),
            'by_method': by_method,
        },
        'employees': breakdown['rows'],
        'trend': trend,
        'lifetime': lifetime,
        'all_time': {'total': money(grand['total']), 'payments': grand['count']},
    }


class PayrollView(APIView):
    """Oyliklar bo'limi uchun yagona manba."""

    permission_classes = [OwnerOnly]

    def get(self, request):
        filters = PayrollFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        today = timezone.localdate()
        period = filters.validated_data.get('month') or today.replace(day=1)
        if period > today.replace(day=1):
            raise serializers.ValidationError('Kelajak oyi uchun oylik hisoboti tuzilmaydi.')
        return Response(build_payroll(request.user.branch, period, today))
