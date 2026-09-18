"""Masalliqlar sarfi tahlili: nima, qancha va qaysi kunlarda ketdi.

Qoldiq faqat StockMovement orqali o'zgaradi, shuning uchun har qanday sanadagi
qoldiqni harakatlardan qayta tiklash mumkin:

    yopilish(oxir) = hozirgi qoldiq - (oxirdan keyingi kirim) + (oxirdan keyingi chiqim)
    ochilish(bosh) = yopilish(oxir) - davrdagi kirim + davrdagi chiqim

Pul tomoni: narx harakat yozilgan paytda muzlatilgan (StockMovement.cost_total).
Narxsiz eski yozuvlar nolga teng bo'ladi — bu yashirilmaydi, aksincha
«narxsiz harakatlar» ko'rsatkichi bilan ochiq aytiladi.
"""
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, F, Q, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import ManagerOnly

from .models import Ingredient, StockMovement
from .money import money, quantity, share

OUT_KINDS = ['consumption', 'sale_consumption']
KIND_LABELS = {
    'receipt': 'Kirim',
    'consumption': 'Qo‘lda sarf',
    'sale_consumption': 'Sotuv sarfi',
}
class UsageFilters(serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    ingredient = serializers.IntegerField(min_value=1, required=False)
    group = serializers.ChoiceField(choices=['day', 'month', 'auto'], default='auto')

    def validate(self, attrs):
        today = timezone.localdate()
        attrs['end'] = attrs.get('end', today)
        attrs['start'] = attrs.get('start', attrs['end'].replace(day=1))
        if attrs['start'] > attrs['end']:
            raise serializers.ValidationError('Boshlanish sanasi tugash sanasidan keyin bo‘lishi mumkin emas.')
        if (attrs['end'] - attrs['start']).days > 1095:
            raise serializers.ValidationError('Bir hisobot oralig‘i ko‘pi bilan 3 yil.')
        if attrs.get('ingredient'):
            branch = self.context['request'].user.branch
            if not Ingredient.objects.filter(branch=branch, pk=attrs['ingredient']).exists():
                raise serializers.ValidationError({'ingredient': 'Mahsulot topilmadi.'})
        if attrs['group'] == 'auto':
            attrs['group'] = 'month' if (attrs['end'] - attrs['start']).days > 62 else 'day'
        return attrs


# Har aggregatsiyada .order_by() shart: StockMovement.Meta.ordering GROUP BY'ga
# qo'shilib jamini qatorlarga bo'lib yuborardi.
SPLIT = {
    'in_quantity': Sum('quantity', filter=Q(kind='receipt')),
    'in_value': Sum('cost_total', filter=Q(kind='receipt')),
    'out_quantity': Sum('quantity', filter=Q(kind__in=OUT_KINDS)),
    'out_value': Sum('cost_total', filter=Q(kind__in=OUT_KINDS)),
    'sale_quantity': Sum('quantity', filter=Q(kind='sale_consumption')),
    'sale_value': Sum('cost_total', filter=Q(kind='sale_consumption')),
    'manual_quantity': Sum('quantity', filter=Q(kind='consumption')),
    'manual_value': Sum('cost_total', filter=Q(kind='consumption')),
}


def fill_days(rows, start, end):
    """Harakatsiz kunlar nol bilan to'ldiriladi, grafikda bo'shliq qolmaydi."""
    known = {row['bucket']: row for row in rows}
    series, cursor = [], start
    while cursor <= end:
        series.append((cursor, known.get(cursor, {})))
        cursor += timedelta(days=1)
    return series


def fill_months(rows, start, end):
    known = {row['bucket']: row for row in rows}
    series, cursor = [], start.replace(day=1)
    final = end.replace(day=1)
    while cursor <= final:
        series.append((cursor, known.get(cursor, {})))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return series


def build_usage(user, filters):
    branch = user.branch
    start, end, group = filters['start'], filters['end'], filters['group']
    chosen = filters.get('ingredient')

    scope = StockMovement.objects.filter(branch=branch)
    if chosen:
        scope = scope.filter(ingredient_id=chosen)
    window = scope.filter(date__gte=start, date__lte=end)

    totals = window.aggregate(
        moves=Count('id'),
        unpriced=Count('id', filter=Q(cost_total=0)),
        **SPLIT,
    )

    # Kg, litr va donani qo'shib bo'lmaydi. Miqdor jamlari faqat davrda bitta
    # o'lchov birligi ishtirok etganda ma'noga ega.
    # .order_by() shart: Meta.ordering'dagi -created_at DISTINCT ichiga tushardi.
    moved_units = set(window.order_by().values_list('ingredient__unit', flat=True).distinct())
    common = moved_units.pop() if len(moved_units) == 1 else ''

    if group == 'day':
        rows = window.values(bucket=F('date')).annotate(**SPLIT).order_by('bucket')
        points = fill_days(list(rows), start, end)
    else:
        rows = window.values(bucket=TruncMonth('date')).annotate(**SPLIT).order_by('bucket')
        points = fill_months(list(rows), start, end)
    # Grafik qatorlari: miqdor faqat bitta mahsulot tanlanganda ma'noli,
    # aks holda aralash birliklar qo'shilib ketardi.
    series = [{
        'date': moment.isoformat(),
        'label': moment.strftime('%Y-%m') if group == 'month' else moment.strftime('%d.%m'),
        'received': quantity(row.get('in_quantity')) if common else '',
        'received_value': money(row.get('in_value')),
        'used': quantity(row.get('out_quantity')) if common else '',
        'used_value': money(row.get('out_value')),
    } for moment, row in points]

    per_item = {
        row['ingredient_id']: row
        for row in window.values('ingredient_id').annotate(**SPLIT, moves=Count('id')).order_by()
    }
    # Davrdan keyingi harakatlar qoldiqni orqaga qaytarish uchun kerak.
    per_item_after = {
        row['ingredient_id']: row
        for row in scope.filter(date__gt=end).values('ingredient_id').annotate(
            in_quantity=Sum('quantity', filter=Q(kind='receipt')),
            out_quantity=Sum('quantity', filter=Q(kind__in=OUT_KINDS)),
        ).order_by()
    }
    days = (end - start).days + 1
    stock = Ingredient.objects.filter(branch=branch)
    if chosen:
        stock = stock.filter(pk=chosen)
    items, idle = [], []
    total_out = totals.get('out_quantity') or Decimal('0')
    for item in stock:
        moved = per_item.get(item.id, {})
        later = per_item_after.get(item.id, {})
        received = moved.get('in_quantity') or Decimal('0')
        used = moved.get('out_quantity') or Decimal('0')
        closing = item.quantity - (later.get('in_quantity') or Decimal('0')) + (later.get('out_quantity') or Decimal('0'))
        opening = closing - received + used
        if not moved.get('moves'):
            idle.append({
                'id': item.id, 'name': item.name, 'unit': item.unit,
                'quantity': quantity(item.quantity), 'unit_cost': money(item.unit_cost),
                'stock_value': money(item.stock_value),
            })
            continue
        per_day = used / days if days else Decimal('0')
        items.append({
            'id': item.id,
            'name': item.name,
            'unit': item.unit,
            'opening': quantity(opening),
            'received': quantity(received),
            'received_value': money(moved.get('in_value')),
            'used': quantity(used),
            'used_value': money(moved.get('out_value')),
            'sold': quantity(moved.get('sale_quantity')),
            'sold_value': money(moved.get('sale_value')),
            'manual': quantity(moved.get('manual_quantity')),
            'manual_value': money(moved.get('manual_value')),
            'closing': quantity(closing),
            'per_day': quantity(per_day),
            # Joriy qoldiq shu sur'atda necha kunga yetadi.
            'days_left': str(int(item.quantity / per_day)) if per_day > 0 else '',
            'unit_cost': money(item.unit_cost),
            'stock_value': money(item.stock_value),
            'share': '',  # pastda pul bo'yicha qayta hisoblanadi
            'low': item.quantity <= item.minimum,
        })
    items.sort(key=lambda row: (Decimal(row['used_value']), Decimal(row['used'])), reverse=True)

    total_value = totals.get('out_value') or Decimal('0')
    for row in items:
        # Ulush pul bo'yicha hisoblanadi; narx yo'q bo'lsa taqqoslash mumkin emas.
        row['share'] = share(Decimal(row['used_value']), total_value)
    stock_value = sum((entry.stock_value for entry in stock), Decimal('0'))
    return {
        'filters': {'start': start, 'end': end, 'group': group, 'ingredient': chosen},
        'summary': {
            # Bitta o'lchov birligi bo'lgandagina miqdor jamlanadi.
            'unit': common,
            'received': quantity(totals.get('in_quantity')) if common else '',
            'received_value': money(totals.get('in_value')),
            'used': quantity(total_out) if common else '',
            'used_value': money(totals.get('out_value')),
            'sold_value': money(totals.get('sale_value')),
            'manual_value': money(totals.get('manual_value')),
            'moves': totals['moves'],
            'unpriced_moves': totals['unpriced'],
            'days': days,
            'per_day_value': money((totals.get('out_value') or Decimal('0')) / days if days else Decimal('0')),
            'stock_value': money(stock_value),
            'items_moved': len(items),
            'items_idle': len(idle),
        },
        'series': series,
        'ingredients': items,
        'idle': idle,
        'kinds': [{'kind': kind, 'label': label} for kind, label in KIND_LABELS.items()],
    }


class StockUsageView(APIView):
    """Masalliqlar sarfi: kunlik, oylik va ikki sana orasidagi kesim."""

    permission_classes = [ManagerOnly]

    def get(self, request):
        filters = UsageFilters(data=request.query_params, context={'request': request})
        filters.is_valid(raise_exception=True)
        return Response(build_usage(request.user, filters.validated_data))
