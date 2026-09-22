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
from core.i18n import _
from users.permissions import OwnerOnly

from .models import (
    DELIVERY_CHANNELS,
    SALE_CHANNEL_LABELS,
    SALE_PAYMENT_METHODS,
    Expense,
    Ingredient,
    Order,
    OrderLine,
    PartnerDelivery,
    PartnerSettlement,
    SalaryPayment,
    StockMovement,
    WaiterPayment,
)
from .money import (
    MONEY,
    day_window,
    money,
    month_key,
    month_label,
    next_month,
    parse_month,
    percent,
    platform_fee,
    short_label,
)
from .reports import discount_cuts

SALARY_CATEGORY = 'Ish haqi'
# Masalliq xaridi ikki xil joyga yozilishi mumkin: omborga kirim va xarajat.
# Ikkalasi ham pul oqimidan chiqadi, ya'ni bitta xarid ikki marta sanalishi
# mumkin. Tizim buni o'zi ajrata olmaydi — kirim masalliq bo'yicha, xarajat
# esa erkin matn bilan yoziladi — shuning uchun faqat ogohlantiradi.
PRODUCE_CATEGORY = 'Masalliq'
TREND_MONTHS = 12


class FinanceFilters(serializers.Serializer):
    month = serializers.RegexField(r'^\d{4}-\d{2}$', required=False)
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)

    def validate(self, attrs):
        today = timezone.localdate()
        if attrs.get('month'):
            first = parse_month(attrs['month'])
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
    # Qamrov ulushi tushumga bo'linadi, tushum esa chegirma ayrilgan summa.
    # Agar surat menyu narxida qolsa, ulush 100% dan oshib ketadi va aynan
    # shu ogohlantirish — «tannarx qamrovi past» — o'chib qoladi.
    covered_lines = lines.filter(cost_per_unit__gt=0)
    covered = covered_lines.aggregate(
        revenue=Coalesce(Sum(F('price') * F('quantity'), output_field=MONEY), Decimal('0')),
        cost=Coalesce(Sum('cost_total'), Decimal('0')),
    )
    covered_cut = discount_cuts(covered_lines)
    covered_revenue = covered['revenue'] - (covered_cut['total'] if covered_cut else Decimal('0'))

    bare_lines = lines.filter(cost_per_unit=0)
    bare_cut = discount_cuts(bare_lines)
    uncovered = [{
        'dish_id': row['dish_id'],
        'dish': row['name'],
        'revenue': money(row['revenue'] - (bare_cut['dish'][row['dish_id']] if bare_cut else Decimal('0'))),
    } for row in bare_lines.values('dish_id', 'name').annotate(
        revenue=Sum(F('price') * F('quantity'), output_field=MONEY),
    ).order_by('-revenue')[:5]]
    dishes = Dish.objects.filter(branch=branch, archived=False)
    # Sotilgan taomlar orasida tannarxsizlari: bitta taomda ham narxli, ham
    # narxsiz qator bo'lishi mumkin, shuning uchun distinct sanaladi.
    sold_uncovered = lines.filter(cost_per_unit=0).values('dish_id').distinct().count()
    return {
        'covered_revenue': money(covered_revenue),
        'share': percent(covered_revenue, revenue),
        'covered_margin': percent(covered_revenue - covered['cost'], covered_revenue),
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
    # `_` nomi bu modulda tarjima funksiyasi, shuning uchun bo'sh o'zgaruvchi
    # sifatida ishlatilmaydi — aks holda u shu funksiya ichida bosilib ketadi.
    for _step in range(TREND_MONTHS):
        months.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    months.reverse()
    since, _until = day_window(months[0], today)

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
    # Platforma ushlanmasi oylik grafikda ham ayriladi: aks holda grafikdagi
    # sof foyda sahifaning boshidagi raqamdan katta bo'lib ko'rinardi.
    fee_by = {
        row['bucket'].date() if hasattr(row['bucket'], 'date') else row['bucket']: row['fee']
        for row in paid.values(bucket=TruncMonth('paid_at')).annotate(fee=platform_fee()).order_by('bucket')
    }
    # Qo'lda yozilgan chiqim ham ayriladi. Bu ilgari unutilgan edi va
    # grafikdagi sof foyda sarlavhadagi raqamdan aynan isrof miqdoricha
    # katta bo'lib ko'rinardi — bir sahifada ikkita «sof foyda».
    waste_by = {
        row['bucket']: row['total']
        for row in StockMovement.objects.filter(branch=branch, kind='consumption', date__gte=months[0])
        .values(bucket=TruncMonth('date')).annotate(total=Sum('cost_total')).order_by('bucket')
    }
    trend = []
    for item in months:
        revenue = revenue_by.get(item) or Decimal('0')
        cost = cost_by.get(item) or Decimal('0')
        spend = spend_by.get(item) or Decimal('0')
        fee = fee_by.get(item) or Decimal('0')
        waste = waste_by.get(item) or Decimal('0')
        trend.append({
            'period': month_key(item),
            'label': short_label(item),
            'revenue': money(revenue),
            'cogs': money(cost),
            'expenses': money(spend),
            'waste': money(waste),
            'platform_fee': money(fee),
            'gross_profit': money(revenue - cost),
            # Formula `build_finance` dagi sof foyda bilan bir xil bo'lishi SHART.
            'net_profit': money(revenue - cost - spend - waste - fee),
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
        # Qaytarilgan buyurtma masallig'i omborga qaytdi, ya'ni u sotilgan
        # tannarx bo'lib qolmaydi va «sarflangan»dan ayirilishi kerak.
        returned=Coalesce(Sum('cost_total', filter=Q(kind='refund')), Decimal('0')),
        # Hamkorga ketgan masalliq: ombordan jo'natish kuni chiqadi.
        partner=Coalesce(Sum('cost_total', filter=Q(kind='partner_sale')), Decimal('0')),
    )
    purchases, waste = moves['purchases'], moves['waste']

    # --- Hamkorlar: maktab va universitetga jo'natilgan taomlar ---
    #
    # Tannarx JO'NATISH kuniga yoziladi, chunki masalliq o'sha kuni ombordan
    # chiqqan va StockMovement ham o'sha kunga yozilgan. Ikkalasi bir kunda
    # turmasa ombor farqi har kuni sababsiz ochilib ketardi.
    #
    # Tushum esa HISOBOT bilan tug'iladi, lekin u ham jo'natma kuniga
    # yoziladi: ovqat dushanba chiqqan bo'lsa foyda ham dushanbaniki. Aks
    # holda dushanba sof xarajat, payshanba sof foyda bo'lib ko'rinardi.
    deliveries = PartnerDelivery.objects.filter(branch=branch, date__gte=start, date__lte=end)
    live = deliveries.exclude(status='cancelled')
    partner_cogs = live.aggregate(total=Coalesce(Sum('cost_total'), Decimal('0')))['total']
    partner_revenue = live.filter(status__in=['reported', 'settled']).aggregate(
        total=Coalesce(Sum('due_total'), Decimal('0')))['total']
    # Hali hisobot berilmagani: tannarxi bor, tushumi yo'q. Hech qanday
    # jamiga kirmaydi — faqat ekranda farqni tushuntirib turadi.
    partner_pending = live.filter(status='sent').aggregate(
        value=Coalesce(Sum('total'), Decimal('0')),
        cost=Coalesce(Sum('cost_total'), Decimal('0')),
        count=Count('id'),
    )
    partner_cash = PartnerSettlement.objects.filter(
        branch=branch, voided_at__isnull=True, paid_on__gte=start, paid_on__lte=end,
    ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')), count=Count('id'))
    # Umumiy qarz butun vaqt bo'yicha: o'tgan oyning qarzi bu oy ko'rinmay
    # qolmasligi kerak.
    partner_debt = (
        PartnerDelivery.objects.filter(branch=branch).exclude(status='cancelled').aggregate(
            total=Coalesce(Sum('due_total'), Decimal('0')))['total']
        - PartnerSettlement.objects.filter(branch=branch, voided_at__isnull=True).aggregate(
            total=Coalesce(Sum('amount'), Decimal('0')))['total']
    )
    partner_profit = partner_revenue - partner_cogs

    # Ofitsiant xizmat haqi: mijozdan yig'iladi, lekin restoranning puli
    # emas. Shuning uchun tushumga ham, foydaga ham kirmaydi — faqat pul
    # oqimida ko'rinadi va ofitsiantga berilguncha kassada turadi.
    service_collected = paid.aggregate(total=Coalesce(Sum('service_charge'), Decimal('0')))['total']
    handed = WaiterPayment.objects.filter(branch=branch, paid_on__gte=start, paid_on__lte=end).aggregate(
        total=Coalesce(Sum('amount'), Decimal('0')), count=Count('id'),
    )
    # Qarz butun davr bo'yicha hisoblanadi: o'tgan oyning ulushi shu oyda
    # berilsa ham balans to'g'ri qolsin.
    owed = (
        Order.objects.filter(branch=branch, status='paid').aggregate(
            total=Coalesce(Sum('service_charge'), Decimal('0')))['total']
        - WaiterPayment.objects.filter(branch=branch).aggregate(
            total=Coalesce(Sum('amount'), Decimal('0')))['total']
    )

    gross_profit = revenue - cogs
    cash_out = settled + purchases + handed['total']

    categories = [{
        'category': row['category'],
        'amount': money(row['total']),
        'share': percent(row['total'], expense_total),
        'count': row['count'],
        'salary': row['category'] == SALARY_CATEGORY,
    } for row in spend.values('category').annotate(total=Sum('amount'), count=Count('id')).order_by('-total')]

    # Har bir to'lov turi doim ro'yxatda turadi, savdosi bo'lmagani ham nol
    # bo'lib: yo'q qator «tekshirilmagan» degani emasligi ko'rinib tursin va
    # egasi qaysi yo'l umuman ishlatilmayotganini bilsin.
    method_rows = {
        row['payment_method']: row
        for row in paid.values('payment_method').annotate(total=Sum('total'), count=Count('id'))
    }
    methods = sorted(({
        'method': method,
        'label': label,
        'revenue': money(method_rows.get(method, {}).get('total')),
        'orders': method_rows.get(method, {}).get('count', 0),
        'share': percent(method_rows.get(method, {}).get('total') or Decimal('0'), revenue),
    } for method, label in SALE_PAYMENT_METHODS), key=lambda row: Decimal(row['revenue']), reverse=True)

    # Oylik ulushi SalaryPayment bilan bog'langan Expense qatorlaridan olinadi.
    # Expense.category erkin matn, shuning uchun 'Ish haqi' deb qo'lda yozilgan
    # qator oylik hisobiga kirib ketmasligi kerak — u alohida anomaliya sifatida
    # ko'rsatiladi.
    # Kanal kesimi: zal, olib ketish, Uzum, Yandex — alohida va jami.
    # Nom ataylab «amount»: `total=Sum('total')` maydon nomini yopib qo'yadi va
    # keyingi ifodadagi F('total') agregatga tushib, xato beradi.
    channel_rows = list(
        paid.values('channel')
        .annotate(fee=platform_fee(), amount=Sum('total'), count=Count('id'))
        .order_by('-amount')
    )
    channels = [{
        'channel': row['channel'],
        'label': SALE_CHANNEL_LABELS.get(row['channel'], row['channel']),
        'revenue': money(row['amount']),
        'orders': row['count'],
        'share': percent(row['amount'], revenue),
        'delivery': row['channel'] in DELIVERY_CHANNELS,
        # Platforma ushlagani va shu kanaldan haqiqatda qo'lga tegadigani.
        'fee': money(row['fee']),
        'fee_share': percent(row['fee'], row['amount']),
        'net': money(row['amount'] - row['fee']),
    } for row in channel_rows]
    # Jami ushlanma kanallar yig'indisidan olinadi: sahifadagi qatorlar bilan
    # jami doim bir xil chiqsin.
    platform_total = sum((row['fee'] for row in channel_rows), Decimal('0'))

    # Platforma ushlagan ulush hech qachon hisobga tushmaydi, shuning uchun u
    # ham xuddi xarajat kabi foydadan ayiriladi. Tushum esa to'liq qoladi:
    # mijoz to'lagan summa o'zgarmaydi, faqat bizga yetib kelgani kamayadi.
    # Hamkor savdosi alohida juftlik bo'lib kiradi: tushumi ham, tannarxi
    # ham o'ziniki. `revenue` ga qo'shilmaydi, chunki u yettita nisbatning
    # maxraji — o'rtacha chek ham, kanal ulushi ham undan hisoblanadi.
    net_profit = gross_profit + partner_profit - expense_total - waste - platform_total
    total_revenue = revenue + partner_revenue

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
    produce_spend = spend.filter(category__iexact=PRODUCE_CATEGORY).aggregate(
        total=Coalesce(Sum('amount'), Decimal('0')), count=Count('id'),
    )
    stock_value = sum((item.stock_value for item in Ingredient.objects.filter(branch=branch)), Decimal('0'))
    consumed = moves['sold'] + waste + moves['partner'] - moves['returned']

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
            'platform_fee': money(platform_total),
            'platform_share': percent(platform_total, revenue),
            # Hamkor savdosi: kassa savdosidan alohida turadi.
            'partner_revenue': money(partner_revenue),
            'partner_cogs': money(partner_cogs),
            'partner_profit': money(partner_profit),
            'partner_margin': percent(partner_profit, partner_revenue),
            'total_revenue': money(total_revenue),
            'net_profit': money(net_profit),
            # Maxraj — ikkala tushum: numerator hamkor foydasini oldi,
            # maxraj esa o'zgarmasa marja soxta ko'tarilib ketardi.
            'net_margin': percent(net_profit, total_revenue),
            'orders': sales['orders'],
            'items': items,
            'average_check': money(revenue / sales['orders'] if sales['orders'] else Decimal('0')),
            'discounts': money(sales['discounts']),
            'discount_share': percent(sales['discounts'], revenue + sales['discounts']),
        },
        'coverage': cost_coverage(lines, revenue, branch),
        # Pul oqimi foydadan farq qiladi: tannarx pul emas, ombor xaridi esa foyda emas.
        'cash': {
            'in': money(revenue + service_collected + partner_cash['total']),
            'out': money(cash_out),
            # Platforma ushlagani hech qachon qo'lga tegmaydi — kirimdan ayriladi.
            'platform_fee': money(platform_total),
            'partner_in': money(partner_cash['total']),
            'net': money(revenue + service_collected + partner_cash['total'] - platform_total - cash_out),
            'settled_expenses': money(settled),
            'stock_purchases': money(purchases),
            'service_collected': money(service_collected),
            'service_paid': money(handed['total']),
            'unpaid': money(unpaid),
            # Ko'prik: foydadan pulga o'tish. Ofitsiant ulushi foydada yo'q,
            # lekin kassada bor — shuning uchun farqi shu yerda qo'shiladi.
            # Ko'prik foydadan pulga olib boradi. Hamkor ikkita had qo'shdi va
            # ikkalasi ham mavjud naqshning aynan o'zi: tannarx pul emas
            # (xuddi `cogs` kabi), qarz harakati esa `unpaid` ning teskarisi —
            # u yerda biz qarzdor edik, bu yerda bizga qarzdor.
            'bridge': money(
                net_profit + cogs + partner_cogs + waste + unpaid - purchases
                + service_collected - handed['total']
                + (partner_cash['total'] - partner_revenue)),
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
        # Hamkorlar: maktab va universitetdan tushgan pul va qolgan qarz.
        'partners': {
            'revenue': money(partner_revenue),
            'cogs': money(partner_cogs),
            'profit': money(partner_profit),
            'received': money(partner_cash['total']),
            'settlements': partner_cash['count'],
            'pending_value': money(partner_pending['value']),
            'pending_cost': money(partner_pending['cost']),
            'pending_count': partner_pending['count'],
            'debt': money(partner_debt),
            'share': percent(partner_revenue, total_revenue),
        },
        # Ofitsiantlar hisobi: yig'ilgan, berilgan va qolgan.
        'service': {
            'collected': money(service_collected),
            'paid': money(handed['total']),
            'payments': handed['count'],
            'owed': money(owed),
            'share': percent(service_collected, revenue),
        },
        'stock': {
            'value': money(stock_value),
            'purchases': money(purchases),
            'consumed': money(consumed),
            # Farq ikkala tomondan bir xil hodisada o'lchanadi: hamkor tannarxi
            # ham retsept tomonida, ham ombor tomonida turadi.
            'gap': money(cogs + partner_cogs - consumed),
            'gap_share': percent(abs(cogs + partner_cogs - consumed), consumed) if consumed else '',
            # «Masalliq» xarajati ombor kirimi bilan yonma-yon turadi: ikkalasi
            # ham nolga teng bo'lmasa, bitta xarid ikki marta yozilgan bo'lishi
            # mumkin va buni faqat egasi bilib ayta oladi.
            'produce_expense': money(produce_spend['total']),
            'produce_count': produce_spend['count'],
        },
        'trend': monthly_trend(branch, today),
        'basis': (
            'Sof foyda = tushum − tannarx − xarajatlar − platforma ushlanmasi. '
            'Oylik «Ish haqi» kategoriyasida '
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
