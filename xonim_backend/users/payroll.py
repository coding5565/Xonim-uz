"""Ish haqi: kunlik yig'ilib boradigan balans.

Butun bo'lim bitta qoidaga tayanadi:

    balans = kelgan kunlar uchun yozilgan haq − berilgan pul

Haq har kuni davomatdan yig'iladi: xodim kelgan kun uchun uning kunlik
summasi balansiga qo'shiladi va o'sha summa qatorga muzlatiladi. Hafta olti
kun — yakshanbaga haq hisoblanmaydi.

Pul esa istalgan kuni, istalgan summada beriladi: hafta oxirida to'liq,
yoki o'rtasida qisman. Har bir to'lov balansdan ayriladi. Balansdan ko'p
berilsa u manfiyga tushadi — bu avans va keyingi ish kunlari bilan o'zi
yopiladi.

Diqqat: har bir to'lov «Ish haqi» kategoriyasida Expense ham yaratadi,
shuning uchun moliya hisobida u xarajatlarning ICHIDA turadi — ustiga
qo'shilmaydi.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Max, Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.i18n import _
from operations.models import REST_WEEKDAY, WORK_DAYS_PER_WEEK, Attendance, SalaryPayment
from operations.money import (
    last_months,
    money,
    month_key,
    month_label,
    next_month,
    parse_month,
    short_label,
)
from operations.services import audit

from .models import User
from .permissions import OwnerOnly, SalesOnly

METHOD_LABELS = {'cash': 'Naqd', 'card': 'Karta'}
TREND_MONTHS = 12
# Davomatni shuncha kun orqaga belgilash mumkin: kecha unutilgan kun
# tuzatilsin, lekin o'tgan oy qayta yozilmasin.
BACKDATE_DAYS = 14
WEEKDAY_NAMES = ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba']
SHORT_WEEKDAYS = ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya']


def week_start(day):
    """Haftaning dushanbasi."""
    return day - timedelta(days=day.weekday())


def week_days(start):
    """Dushanbadan yakshanbagacha ettita kun. Yakshanba dam olish kuni."""
    return [start + timedelta(days=offset) for offset in range(7)]


def is_rest(day):
    return day.weekday() == REST_WEEKDAY


def staff_of(branch):
    """Ish haqi yuritiladigan xodimlar. Superadmin bu ro'yxatda yo'q."""
    return list(
        User.objects.filter(branch=branch)
        .exclude(role=User.Role.OWNER)
        .order_by('-is_active', 'first_name', 'username')
    )


def known_months(branch, today):
    """Birinchi to'lov yoki birinchi ishga olishdan bugungacha — yangisi birinchi."""
    first_payment = SalaryPayment.objects.filter(branch=branch).order_by('paid_on').values_list('paid_on', flat=True).first()
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
    week = serializers.DateField(required=False)

    def validate_month(self, value):
        return parse_month(value)


def build_payroll(branch, today, period, week_of=None):
    """Bo'limning butun manzarasi: hafta, balanslar va to'lovlar tarixi."""
    staff = staff_of(branch)
    start = week_start(week_of or today)
    days = week_days(start)

    # --- Shu haftaning davomati ---
    marks = {
        (row.employee_id, row.date): row
        for row in Attendance.objects.filter(branch=branch, date__gte=days[0], date__lte=days[-1])
    }
    # --- Butun davr bo'yicha yig'ilgan haq va berilgan pul ---
    earned = {
        row['employee_id']: row
        for row in Attendance.objects.filter(branch=branch, present=True)
        .values('employee_id').annotate(total=Sum('daily_wage'), days=Count('id')).order_by()
    }
    paid = {
        row['employee_id']: row
        for row in SalaryPayment.objects.filter(branch=branch)
        .values('employee_id').annotate(total=Sum('amount'), count=Count('id'), last=Max('paid_on')).order_by()
    }

    rows = []
    daily_total = week_earned_total = earned_total = paid_total = balance_total = Decimal('0')
    present_today = marked_today = 0
    for person in staff:
        person_earned = earned.get(person.id, {})
        person_paid = paid.get(person.id, {})
        accrued = person_earned.get('total') or Decimal('0')
        given = person_paid.get('total') or Decimal('0')
        balance = accrued - given

        week_row = []
        week_earned = Decimal('0')
        week_present = 0
        for day in days:
            mark = marks.get((person.id, day))
            if mark and mark.present:
                week_earned += mark.daily_wage
                week_present += 1
            week_row.append({
                'date': day,
                'weekday': SHORT_WEEKDAYS[day.weekday()],
                'rest': is_rest(day),
                # None — hali belgilanmagan. False — kelmagan. Ikkalasi bir xil emas.
                'present': None if not mark else mark.present,
                'future': day > today,
            })

        today_mark = marks.get((person.id, today))
        if person.is_active and today_mark:
            marked_today += 1
            if today_mark.present:
                present_today += 1
        if person.is_active:
            daily_total += person.daily_wage
        week_earned_total += week_earned
        earned_total += accrued
        paid_total += given
        balance_total += balance

        rows.append({
            'id': person.id,
            'name': person.first_name or person.username,
            'username': person.username,
            'role': person.role,
            'role_label': person.get_role_display(),
            'active': person.is_active,
            'daily_wage': money(person.daily_wage),
            # Olti kun to'liq ishlansa haftada shuncha bo'ladi.
            'week_wage': money(person.daily_wage * WORK_DAYS_PER_WEEK),
            'week': week_row,
            'week_days': week_present,
            'week_earned': money(week_earned),
            'today': None if not today_mark else ('present' if today_mark.present else 'absent'),
            'days_worked': person_earned.get('days', 0),
            'earned': money(accrued),
            'paid': money(given),
            'balance': money(balance),
            # Manfiy balans — avans: pul ishlab berilgandan oldin berilgan.
            'advance': balance < 0,
            'payments': person_paid.get('count', 0),
            'last_paid_on': person_paid.get('last'),
        })

    active = [person for person in staff if person.is_active]
    month_payments = SalaryPayment.objects.filter(
        branch=branch, paid_on__gte=period, paid_on__lt=next_month(period),
    ).select_related('employee', 'actor')

    by_method = [{
        'method': row['payment_method'],
        'label': METHOD_LABELS.get(row['payment_method'], row['payment_method']),
        'amount': money(row['total']),
        'count': row['count'],
    } for row in month_payments.values('payment_method')
        .annotate(total=Sum('amount'), count=Count('id')).order_by('-total')]

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

    grand = SalaryPayment.objects.filter(branch=branch).aggregate(total=Sum('amount'), count=Count('id'))
    return {
        'today': today,
        'rest_day': is_rest(today),
        'week': {
            'start': days[0],
            'end': days[-1],
            'label': f'{days[0]:%d.%m} — {days[-1]:%d.%m}',
            'current': start == week_start(today),
            'days': [{
                'date': day,
                'weekday': SHORT_WEEKDAYS[day.weekday()],
                'name': WEEKDAY_NAMES[day.weekday()],
                'rest': is_rest(day),
                'today': day == today,
                'future': day > today,
                'marked': sum(1 for person in active if (person.id, day) in marks),
                'present': sum(
                    1 for person in active
                    if marks.get((person.id, day)) and marks[(person.id, day)].present
                ),
            } for day in days],
        },
        'month': month_key(period),
        'month_label': month_label(period),
        'months': known_months(branch, today),
        'summary': {
            'staff_count': len(active),
            # Hamma kelgan kunning bir kunlik narxi va olti kunlik hafta narxi.
            'daily_total': money(daily_total),
            'week_wage': money(daily_total * WORK_DAYS_PER_WEEK),
            'week_earned': money(week_earned_total),
            'earned': money(earned_total),
            'paid': money(paid_total),
            'balance': money(balance_total),
            'marked_today': marked_today,
            'present_today': present_today,
            'unmarked_today': len(active) - marked_today,
            'month_paid': money(month_payments.aggregate(total=Sum('amount'))['total']),
            'month_count': month_payments.count(),
            'by_method': by_method,
            'work_days': WORK_DAYS_PER_WEEK,
            'without_wage': sum(1 for person in active if not person.daily_wage),
        },
        'employees': rows,
        'payments': [{
            'id': item.id,
            'employee': item.employee_id,
            'employee_name': item.employee.first_name or item.employee.username,
            'amount': money(item.amount),
            'payment_method': item.payment_method,
            'payment_label': METHOD_LABELS.get(item.payment_method, item.payment_method),
            'paid_on': item.paid_on,
            'note': item.note,
            'actor_name': item.actor.first_name or item.actor.username,
        } for item in month_payments[:60]],
        'trend': trend,
        'all_time': {'total': money(grand['total']), 'payments': grand['count']},
    }


class PayrollView(APIView):
    """Ish haqi bo'limi uchun yagona manba.

    Kassir ham ochadi: davomatni u belgilaydi va pulni ko'pincha u beradi.
    """

    permission_classes = [SalesOnly]

    def get(self, request):
        filters = PayrollFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        today = timezone.localdate()
        period = filters.validated_data.get('month') or today.replace(day=1)
        if period > today.replace(day=1):
            raise serializers.ValidationError(_('Kelajak oyi uchun hisobot tuzilmaydi.'))
        week = filters.validated_data.get('week')
        if week and week > today:
            raise serializers.ValidationError(_('Kelajakdagi hafta uchun davomat yuritilmaydi.'))
        return Response(build_payroll(request.user.branch, today, period, week))


class AttendanceRow(serializers.Serializer):
    employee = serializers.IntegerField(min_value=1)
    present = serializers.BooleanField()
    note = serializers.CharField(max_length=200, allow_blank=True, default='')


class AttendanceInput(serializers.Serializer):
    date = serializers.DateField(required=False)
    rows = AttendanceRow(many=True, allow_empty=False)

    def validate_rows(self, value):
        if len(value) > 50:
            raise serializers.ValidationError(_('Bir martada ko‘pi bilan 50 ta xodim.'))
        seen = {row['employee'] for row in value}
        if len(seen) != len(value):
            raise serializers.ValidationError(_('Bir xodim ro‘yxatda ikki marta.'))
        return value

    def validate_date(self, value):
        today = timezone.localdate()
        if value > today:
            raise serializers.ValidationError(_('Kelajakdagi kun uchun davomat belgilanmaydi.'))
        if (today - value).days > BACKDATE_DAYS:
            raise serializers.ValidationError(
                _('Faqat oxirgi {days} kunni belgilash mumkin.').format(days=BACKDATE_DAYS))
        if is_rest(value):
            # Yakshanba dam olish kuni: unga haq hisoblanmaydi, shuning uchun
            # davomat ham yuritilmaydi.
            raise serializers.ValidationError(_('Yakshanba — dam olish kuni, unga haq hisoblanmaydi.'))
        return value

    def validate(self, attrs):
        attrs.setdefault('date', timezone.localdate())
        if is_rest(attrs['date']):
            raise serializers.ValidationError(_('Yakshanba — dam olish kuni, unga haq hisoblanmaydi.'))
        return attrs


@transaction.atomic
def mark_attendance(user, data):
    """Kunni belgilaydi va o'sha kundagi kunlik haqni qatorga muzlatadi."""
    day = data['date']
    wanted = {row['employee']: row for row in data['rows']}
    people = {
        person.id: person
        for person in User.objects.filter(branch=user.branch, pk__in=wanted, is_active=True)
        .exclude(role=User.Role.OWNER)
    }
    missing = sorted(set(wanted) - set(people))
    if missing:
        raise serializers.ValidationError(_('Xodim topilmadi.'))

    existing = {
        row.employee_id: row
        for row in Attendance.objects.select_for_update().filter(
            branch=user.branch, date=day, employee_id__in=people)
    }
    created, updated = [], []
    for employee_id, row in wanted.items():
        person = people[employee_id]
        # Kelmagan kunga haq yozilmaydi.
        wage = person.daily_wage if row['present'] else Decimal('0')
        record = existing.get(employee_id)
        if record:
            record.present = row['present']
            record.daily_wage = wage
            record.note = row['note']
            record.actor = user
            updated.append(record)
        else:
            created.append(Attendance(
                branch=user.branch, employee=person, actor=user, date=day,
                present=row['present'], daily_wage=wage, note=row['note'],
            ))
    if created:
        Attendance.objects.bulk_create(created)
    if updated:
        Attendance.objects.bulk_update(updated, ['present', 'daily_wage', 'note', 'actor'])

    came = sum(1 for row in wanted.values() if row['present'])
    audit(
        user, 'attendance.mark',
        f'{day:%d.%m.%Y} · {came} keldi · {len(wanted) - came} kelmadi',
    )
    return day


class AttendanceView(APIView):
    """Kunlik davomat: kim keldi, kim kelmadi.

    Har bir belgilangan kelgan kun xodimning balansiga kunlik haqini
    qo'shadi. Belgilanmagan kun hech narsa yozmaydi — «so'ralmagan savol»
    bilan «kelmadi» javobi bir xil emas.
    """

    permission_classes = [SalesOnly]

    def post(self, request):
        data = AttendanceInput(data=request.data)
        data.is_valid(raise_exception=True)
        day = mark_attendance(request.user, data.validated_data)
        today = timezone.localdate()
        return Response(
            build_payroll(request.user.branch, today, today.replace(day=1), day),
            status=201,
        )


class AttendanceHistoryView(APIView):
    """Bir xodimning davomat tarixi — superadmin nazorati uchun."""

    permission_classes = [OwnerOnly]

    def get(self, request, pk):
        rows = Attendance.objects.filter(branch=request.user.branch, employee_id=pk).select_related('actor')[:120]
        return Response([{
            'id': row.id,
            'date': row.date,
            'weekday': WEEKDAY_NAMES[row.date.weekday()],
            'present': row.present,
            'daily_wage': money(row.daily_wage),
            'note': row.note,
            'actor_name': row.actor.first_name or row.actor.username,
        } for row in rows])
