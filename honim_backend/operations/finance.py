"""Umumiy moliya: bitta davr uchun yagona foyda zanjiri.

Zanjir shunday o'qiladi va har bir qatori bosiladigan qilib chiqariladi:

    Tushum − Tannarx = Yalpi foyda
    Yalpi foyda − Operatsion xarajatlar = Sof foyda

Ikki marta sanashning oldini olish qoidalari:
  · Oylik to'lovi «Ish haqi» kategoriyasida Expense yaratadi, shuning uchun
    oylik xarajatlarning ICHIDA turadi — ustiga qo'shilmaydi.
  · Ombor xaridi (StockMovement.kind='receipt') foyda zanjiriga KIRMAYDI:
    u tovarga aylanadi va sotilganda tannarx sifatida hisobga olinadi.
    U faqat pul oqimida ko'rinadi.

Foyda bilan pul oqimi farqi algebraik aniq:
    sof_pul = sof_foyda + tannarx + to'lanmagan_xarajat − ombor_xaridi
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Dish
from users.permissions import OwnerOnly

from .models import SALE_CHANNEL_LABELS, SALE_PAYMENT_LABELS, Expense, Ingredient, Order, OrderLine, SalaryPayment, StockMovement
from .money import MONEY, day_window, money, month_key, month_label, next_month, percent, short_label
from core.i18n import _

SALARY_CATEGORY = 'Ish haqi'
TREND_MONTHS = 12


class FinanceFilters(serializers.Serializer):
    month = serializers.RegexField(r'^\d{4}-\d{2}$', required=False)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)

    def validate(self, attrs):
        today = timezone.localdate()
        if attrs.get('month'):
            year, month = attrs['month'].split('-')
            if not 1 <= int(month) <= 12:
                raise serializers.ValidationError({'month': _('Oy 01 dan 12 gacha bo‘lishi kerak.')})
            first = timezone.datetime(int(year), int(month), 1).date()
            if first > today.replace(day=1):
                raise serializers.ValidationError({'month': _('Kelajak oyi uchun hisobot tuzilmaydi.')})
            attrs['start'] = first
            attrs['end'] = min(next_month(first) - timedelta(days=1), today)
            return attrs
        attrs['end'] = attrs.get('end', today)
        attrs['start'] = attrs.get('start', attrs['end'].replace(day=1))
        if attrs['start'] > attrs['end']:
            raise serializers.ValidationError(_('Boshlanish sanasi tugash sanasidan keyin bo‘lishi mumkin emas.'))
        if (attrs['end'] - attrs['start']).days > 1095:
            raise serializers.ValidationError(_('Bir hisobot oralig‘i ko‘pi bilan 3 yil.'))
        return attrs


def known_months(branch, today):
    """Birinchi savdo yoki xarajatdan bugungacha — yangisi birinchi."""
    first_sale = Order.objects.filter(branch=branch, status='paid').order_by('paid_at').values_list('paid_at', flat=True).first()
    first_spend = Expense.objects.filter(branch=branch).order_by('date').values_list('date', flat=True).first()
    known = []
    if first_sale:
        known.append(timezone.localtime(first_sale).date())
    if first_spend:
        known.append(first_spend)
    cursor = min(known).replace(day=1) if known else today.replace(day=1)
    months = []
    while cursor <= today.replace(day=1):
        months.append(month_key(cursor))
        cursor = next_month(cursor)
    return list(reversed(months))


def cost_coverage(lines, revenue, branch):
    """Tannarx qancha tushumni qamrab olgani — soxta marjani fosh qiladi.

    Retsepti yo'q taomning tannarxi nol bo'lib yoziladi, shuning uchun umumiy
    marja haqiqatdan yuqori ko'rinadi. Shu qamrov ko'rsatkichisiz raqamga
    ishonib bo'lmaydi.
    """
    covered = lines.filter(cost_per_unit__gt=0).aggregate(
        revenue=Coalesce(Sum(F('price') * F('quantity'), output_field=MONEY), Decimal('0')),
        cost=Coalesce(Sum('cost_total'), Decimal('0')),
    )
    uncovered = [{
        'dish_id': row['dish_id'],
        'dish': row['name'],
        'revenue': money(row['revenue']),
    } for row in lines.filter(cost_per_unit=0).values('dish_id', 'name').annotate(
        revenue=Sum(F('price') * F('quantity'), output_field=MONEY),
    ).order_by('-revenue')[:5]]
    dishes = Dish.objects.filter(branch=branch, archived=False)
    # Sotilgan taomlar orasida tannarxsizlari: bitta taomda ham narxli, ham
    # narxsiz qator bo'lishi mumkin, shuning uchun distinct sanaladi.
    sold_uncovered = lines.filter(cost_per_unit=0).values('dish_id').distinct().count()
    return {
        'covered_revenue': money(covered['revenue']),
        'share': percent(covered['revenue'], revenue),
        'covered_margin': percent(covered['revenue'] - covered['cost'], covered['revenue']),
        'dishes_total': dishes.count(),
        # Arxivlanmagan taomlardan nechtasida umuman retsept yo'q.
        'menu_without_recipe': dishes.filter(recipe__isnull=True).count(),
        'dishes_with_recipe': dishes.filter(recipe__isnull=False, recipe__active=True).count(),
        'sold_uncovered': sold_uncovered,
        'top_uncovered': uncovered,
    }


def monthly_trend(branch, today):
    """Oxirgi 12 oy: tushum, tannarx, xarajat va sof foyda."""
    months, cursor = [], today.replace(day=1)
    for _ in range(TREND_MONTHS):
        months.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    months.reverse()
    since, _ = day_window(months[0], today)

    paid = Order.objects.filter(branch=branch, status='paid', paid_at__gte=since)
    revenue_by = {
        row['bucket'].date() if hasattr(row['bucket'], 'date') else row['bucket']: row['total']
        for row in paid.values(bucket=TruncMonth('paid_at')).annotate(total=Sum('total')).order_by('bucket')
    }
    cost_by = {
        row['bucket'].date() if hasattr(row['bucket'], 'date') else row['bucket']: row['total']
        for row in OrderLine.objects.filter(order__in=paid)
        .values(bucket=TruncMonth('order__paid_at')).annotate(total=Sum('cost_total')).order_by('bucket')
    }
    spend_by = {
        row['bucket']: row['total']
        for row in Expense.objects.filter(branch=branch, date__gte=months[0])
        .values(bucket=TruncMonth('date')).annotate(total=Sum('amount')).order_by('bucket')
    }
    trend = []
    for item in months:
        revenue = revenue_by.get(item) or Decimal('0')
        cost = cost_by.get(item) or Decimal('0')
        spend = spend_by.get(item) or Decimal('0')
        trend.append({
            'period': month_key(item),
            'label': short_label(item),
            'revenue': money(revenue),
            'cogs': money(cost),
            'expenses': money(spend),
            'gross_profit': money(revenue - cost),
            'net_profit': money(revenue - cost - spend),
        })
    return trend


def build_finance(branch, start, end, today):
    since, until = day_window(start, end)
    paid = Order.objects.filter(branch=branch, status='paid', paid_at__gte=since, paid_at__lt=until)
    lines = OrderLine.objects.filter(order__in=paid)
    spend = Expense.objects.filter(branch=branch, date__gte=start, date__lte=end)

    sales = paid.aggregate(
        revenue=Coalesce(Sum('total'), Decimal('0')),
        # Chegirma tushumdan allaqachon ayirilgan (total — to'langan summa),
        # bu yerda faqat qancha berilgani ko'rsatiladi.
        discounts=Coalesce(Sum('discount'), Decimal('0')),
        orders=Count('id'),
    )
    revenue = sales['revenue']
    cogs = lines.aggregate(total=Coalesce(Sum('cost_total'), Decimal('0')))['total']
    items = lines.aggregate(total=Coalesce(Sum('quantity'), 0))['total']

    expense_total = spend.aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    unpaid = spend.filter(payment_method='unpaid').aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
    settled = expense_total - unpaid
    moves = StockMovement.objects.filter(branch=branch, date__gte=start, date__lte=end).aggregate(
        purchases=Coalesce(Sum('cost_total', filter=Q(kind='receipt')), Decimal('0')),
        # Qo'lda yozilgan sarf sotuvda ayrilmagan va hech qanday xarajat yozuvi
        # yo'q — lekin bu haqiqiy yo'qotish, shuning uchun foydadan ayiriladi.
        waste=Coalesce(Sum('cost_total', filter=Q(kind='consumption')), Decimal('0')),
        sold=Coalesce(Sum('cost_total', filter=Q(kind='sale_consumption')), Decimal('0')),
    )
    purchases, waste = moves['purchases'], moves['waste']

    gross_profit = revenue - cogs
    net_profit = gross_profit - expense_total - waste
    cash_out = settled + purchases

    categories = [{
        'category': row['category'],
        'amount': money(row['total']),
        'share': percent(row['total'], expense_total),
        'count': row['count'],
        'salary': row['category'] == SALARY_CATEGORY,
    } for row in spend.values('category').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')]

    methods = [{
        'method': row['payment_method'],
        'label': SALE_PAYMENT_LABELS.get(row['payment_method'], row['payment_method'] or '—'),
        'revenue': money(row['total']),
        'orders': row['count'],
        'share': percent(row['total'], revenue),
    } for row in paid.values('payment_method').annotate(total=Sum('total'), count=Count('id')).order_by('-total')]

    # Oylik ulushi SalaryPayment bilan bog'langan Expense qatorlaridan olinadi.
    # Expense.category erkin matn, shuning uchun 'Ish haqi' deb qo'lda yozilgan
    # qator oylik hisobiga kirib ketmasligi kerak — u alohida anomaliya sifatida
    # ko'rsatiladi.
    # Kanal kesimi: zal, olib ketish, Uzum, Yandex — alohida va jami.
    channels = [{
        'channel': row['channel'],
        'label': SALE_CHANNEL_LABELS.get(row['channel'], row['channel']),
        'revenue': money(row['total']),
        'orders': row['count'],
        'share': percent(row['total'], revenue),
        'delivery': row['channel'] in ('uzum', 'yandex'),
    } for row in paid.values('channel').annotate(total=Sum('total'), count=Count('id')).order_by('-total')]

    salary_spend = spend.filter(salary_payment__isnull=False).aggregate(
        total=Coalesce(Sum('amount'), Decimal('0')), count=Count('id'),
    )
    manual_salary = spend.filter(
        salary_payment__isnull=True, category__iexact=SALARY_CATEGORY,
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')), count=Count('id'))
    # .order_by() shart: Meta.ordering'dagi -id DISTINCT ichiga tushib,
    # har bir oyni takroran qaytarardi.
    salary_periods = SalaryPayment.objects.filter(
        branch=branch, paid_on__gte=start, paid_on__lte=end,
    ).order_by().values_list('period', flat=True).distinct()
    stock_value = sum((item.stock_value for item in Ingredient.objects.filter(branch=branch)), Decimal('0'))
    consumed = moves['sold'] + waste

    return {
        'filters': {
            'start': start, 'end': end,
            'month': month_key(start) if start.day == 1 and next_month(start) - timedelta(days=1) >= end else None,
            'label': month_label(start) if start.day == 1 and next_month(start) - timedelta(days=1) >= end
            else f'{start:%d.%m.%Y} — {end:%d.%m.%Y}',
            'days': (end - start).days + 1,
        },
        'months': known_months(branch, today),
        # Foyda zanjiri: har bir qatori sahifaga olib boradi.
        'profit': {
            'revenue': money(revenue),
            'cogs': money(cogs),
            'gross_profit': money(gross_profit),
            'gross_margin': percent(gross_profit, revenue),
            'expenses': money(expense_total),
            'waste': money(waste),
            'net_profit': money(net_profit),
            'net_margin': percent(net_profit, revenue),
            'orders': sales['orders'],
            'items': items,
            'average_check': money(revenue / sales['orders'] if sales['orders'] else Decimal('0')),
            'discounts': money(sales['discounts']),
            'discount_share': percent(sales['discounts'], revenue + sales['discounts']),
        },
        'coverage': cost_coverage(lines, revenue, branch),
        # Pul oqimi foydadan farq qiladi: tannarx pul emas, ombor xaridi esa foyda emas.
        'cash': {
            'in': money(revenue),
            'out': money(cash_out),
            'net': money(revenue - cash_out),
            'settled_expenses': money(settled),
            'stock_purchases': money(purchases),
            'unpaid': money(unpaid),
            'bridge': money(net_profit + cogs + waste + unpaid - purchases),
        },
        'expenses': categories,
        'methods': methods,
        'channels': channels,
        'salary': {
            'total': money(salary_spend['total']),
            'payments': salary_spend['count'],
            'periods': sorted({month_key(item) for item in salary_periods}, reverse=True),
            'share': percent(salary_spend['total'], expense_total),
            # «Ish haqi» deb qo'lda kiritilgan, lekin oylik to'loviga bog'lanmagan
            # xarajatlar. Jamiga qo'shilmaydi — allaqachon xarajatlar ichida.
            'manual_total': money(manual_salary['total']),
            'manual_count': manual_salary['count'],
        },
        # Ikki mustaqil tannarx signali: retsept (OrderLine.cost_total) va ombor
        # (StockMovement.cost_total). Ular bir-biriga yaqin turishi kerak; katta
        # farq retseptdagi batch_cost eskirganini bildiradi.
        'stock': {
            'value': money(stock_value),
            'purchases': money(purchases),
            'consumed': money(consumed),
            'gap': money(cogs - consumed),
            'gap_share': percent(abs(cogs - consumed), consumed) if consumed else '',
        },
        'trend': monthly_trend(branch, today),
        'basis': (
            'Sof foyda = tushum − tannarx − xarajatlar. Oylik «Ish haqi» kategoriyasida '
            'xarajatlar ichida turadi. Ombor xaridi foydaga emas, pul oqimiga kiradi — '
            'u sotilganda tannarx bo‘lib hisobga olinadi.'
        ),
    }


class FinanceView(APIView):
    """Umumiy moliya: bitta davrning to‘liq moliyaviy manzarasi."""

    permission_classes = [OwnerOnly]

    def get(self, request):
        filters = FinanceFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        data = filters.validated_data
        today = timezone.localdate()
        return Response(build_finance(request.user.branch, data['start'], data['end'], today))
