"""Kunlik haqiqiy sarf va uni tizim hisobi bilan solishtirish.

Ikki xil raqam bor va ular hech qachon aralashmaydi:

  · NAZARIY sarf — tizim hisoblaydi. Taom sotilganda retsept bo'yicha
    ombordan avtomatik ayriladi (StockMovement.kind='sale_consumption').
  · HAQIQIY sarf — admin kechqurun qo'lda kiritadi (DailyUsage). Ombordan
    HECH NARSA ayirmaydi, chunki sotuv allaqachon ayirgan — aks holda bitta
    mahsulot ikki marta chiqib ketardi.

Farqi nazorat signali: ortiqcha solinyaptimi, isrof bo'lyaptimi yoki
yo'qolyaptimi. Farq qanchalik kichik bo'lsa, retsept shunchalik to'g'ri.
"""
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.i18n import _
from users.permissions import OwnerOnly, SalesOnly

from .models import DailyUsage, Ingredient, StockMovement
from .money import CENT, money, quantity, share
from .services import audit, audit_many, quantity_text, safely

# Shu foizdan katta farq e'tibor talab qiladi.
ALERT_SHARE = Decimal('15')
# Eng ko'pi bilan shuncha kun orqaga kirita olinadi: kechagi hisobotni
# tuzatish mumkin, lekin bir oy oldingisini qayta yozish nazoratni buzardi.
BACKDATE_DAYS = 7


class UsageLineInput(serializers.Serializer):
    ingredient = serializers.IntegerField(min_value=1)
    # Nol yuborilsa o'sha kungi yozuv o'chiriladi — admin xato kiritganini
    # shu yo'l bilan qaytaradi.
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal('0'))
    note = serializers.CharField(max_length=250, allow_blank=True, default='')


class DailyUsageInput(serializers.Serializer):
    date = serializers.DateField()
    lines = UsageLineInput(many=True, allow_empty=False)

    def validate_date(self, value):
        today = timezone.localdate()
        if value > today:
            raise serializers.ValidationError(_('Kelajakdagi kun uchun sarf kiritilmaydi.'))
        if (today - value).days > BACKDATE_DAYS:
            raise serializers.ValidationError(
                _('Faqat oxirgi {days} kun uchun kiritish mumkin.').format(days=BACKDATE_DAYS))
        return value

    def validate_lines(self, lines):
        if len({line['ingredient'] for line in lines}) != len(lines):
            raise serializers.ValidationError(_('Bir mahsulotni faqat bir marta kiriting.'))
        if len(lines) > 200:
            raise serializers.ValidationError(_('Bir kunda ko‘pi bilan 200 qator.'))
        return lines


class DailyUsageFilters(serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    date = serializers.DateField(required=False)

    def validate(self, attrs):
        today = timezone.localdate()
        if attrs.get('date'):
            attrs['start'] = attrs['end'] = attrs['date']
            return attrs
        attrs['end'] = attrs.get('end', today)
        attrs['start'] = attrs.get('start', attrs['end'] - timedelta(days=13))
        if attrs['start'] > attrs['end']:
            raise serializers.ValidationError(_('Boshlanish sanasi tugash sanasidan keyin bo‘lishi mumkin emas.'))
        if (attrs['end'] - attrs['start']).days > 366:
            raise serializers.ValidationError(_('Bir oraliq ko‘pi bilan bir yil.'))
        return attrs


@transaction.atomic
def save_daily_usage(user, data):
    """Bir kunning hisobotini yozadi. Qayta yuborilsa ustiga yoziladi."""
    day = data['date']
    wanted = {line['ingredient']: line for line in data['lines']}
    stock = {
        item.id: item
        for item in Ingredient.objects.filter(branch=user.branch, id__in=wanted)
    }
    if len(stock) != len(wanted):
        raise serializers.ValidationError({'lines': _('Ayrim mahsulotlar topilmadi.')})
    for ingredient_id, line in wanted.items():
        item = stock[ingredient_id]
        if item.unit == 'dona' and line['quantity'] != line['quantity'].to_integral_value():
            raise serializers.ValidationError({'lines': _('{name}: dona butun son bo‘lishi kerak.').format(name=item.name)})

    existing = {
        row.ingredient_id: row
        for row in DailyUsage.objects.select_for_update().filter(branch=user.branch, date=day, ingredient_id__in=wanted)
    }
    written, removed, events = 0, 0, []
    for ingredient_id, line in wanted.items():
        item = stock[ingredient_id]
        row = existing.get(ingredient_id)
        if not line['quantity']:
            if row:
                row.delete()
                removed += 1
                events.append(('usage.remove', f'{day} · {item.name} · yozuv o‘chirildi'))
            continue
        if row:
            was = row.quantity
            row.quantity = line['quantity']
            row.note = line['note']
            row.actor = user
            row.save(update_fields=['quantity', 'note', 'actor', 'updated_at'])
            if was != row.quantity:
                events.append((
                    'usage.update',
                    f'{day} · {item.name} · {quantity_text(was)} → {quantity_text(row.quantity)} {item.unit}',
                ))
        else:
            DailyUsage.objects.create(
                branch=user.branch, actor=user, ingredient=item, date=day,
                quantity=line['quantity'], note=line['note'],
            )
            events.append(('usage.create', f'{day} · {item.name} · {quantity_text(line["quantity"])} {item.unit}'))
        written += 1

    audit_many(user, events)
    if not events:
        audit(user, 'usage.create', f'{day} · o‘zgarish bo‘lmadi')
    return {'date': day, 'saved': written, 'removed': removed}


def day_rows(branch, start, end):
    """Kiritilgan hisobotlar, kun bo'yicha guruhlangan."""
    rows = DailyUsage.objects.filter(
        branch=branch, date__gte=start, date__lte=end,
    ).select_related('ingredient', 'actor')
    days = {}
    for row in rows:
        day = days.setdefault(row.date, {'date': row.date, 'lines': [], 'value': Decimal('0'), 'actors': set()})
        value = (row.quantity * row.ingredient.unit_cost).quantize(CENT)
        day['value'] += value
        day['actors'].add(row.actor.first_name or row.actor.username)
        day['lines'].append({
            'id': row.id,
            'ingredient': row.ingredient_id,
            'name': row.ingredient.name,
            'unit': row.ingredient.unit,
            'quantity': quantity(row.quantity),
            'value': money(value),
            'note': row.note,
            'actor': row.actor.first_name or row.actor.username,
            'updated_at': row.updated_at,
        })
    return [{
        'date': day['date'].isoformat(),
        'lines': sorted(day['lines'], key=lambda line: line['name']),
        'items': len(day['lines']),
        'value': money(day['value']),
        'actors': sorted(day['actors']),
    } for day in sorted(days.values(), key=lambda item: item['date'], reverse=True)]


def build_comparison(branch, start, end):
    """Tizim hisoblagan sarf bilan admin kiritgan sarfni yonma-yon qo'yadi."""
    system = {
        row['ingredient_id']: row
        for row in StockMovement.objects.filter(
            branch=branch, kind='sale_consumption', date__gte=start, date__lte=end,
        ).values('ingredient_id').annotate(
            quantity=Sum('quantity'), value=Sum('cost_total'), moves=Count('id'),
        ).order_by()
    }
    actual = {
        row['ingredient_id']: row
        for row in DailyUsage.objects.filter(
            branch=branch, date__gte=start, date__lte=end,
        ).values('ingredient_id').annotate(quantity=Sum('quantity'), days=Count('id')).order_by()
    }
    touched = set(system) | set(actual)
    stock = {item.id: item for item in Ingredient.objects.filter(branch=branch, id__in=touched)}

    rows, alerts = [], 0
    system_value = actual_value = Decimal('0')
    for ingredient_id in touched:
        item = stock.get(ingredient_id)
        if not item:
            continue
        expected = system.get(ingredient_id, {}).get('quantity') or Decimal('0')
        counted = actual.get(ingredient_id, {}).get('quantity') or Decimal('0')
        gap = counted - expected
        expected_value = system.get(ingredient_id, {}).get('value') or Decimal('0')
        # Ikkala tomon BIR XIL narxda baholanadi. Tizim hisobi sotuv
        # paytidagi muzlatilgan narxda yozilgan, admin kiritgani esa faqat
        # miqdor. Uni bugungi narxda baholasak, mahsulot podorojasa yo'qdan
        # farq paydo bo'lardi. Shuning uchun davrning o'rtacha sotuv narxi
        # olinadi; u yo'q bo'lsagina joriy narxga tushiladi.
        price = (expected_value / expected) if expected else item.unit_cost
        counted_value = (counted * price).quantize(CENT)
        system_value += expected_value
        actual_value += counted_value
        gap_share = share(abs(gap), expected)
        # Faqat ikkala tomonda ham ma'lumot bo'lganda ogohlantiramiz: bir
        # tomoni bo'sh bo'lsa bu farq emas, hisobot to'liq emas.
        flagged = bool(expected and counted and gap_share and Decimal(gap_share) > ALERT_SHARE)
        if flagged:
            alerts += 1
        rows.append({
            'id': item.id,
            'name': item.name,
            'unit': item.unit,
            'expected': quantity(expected),
            'counted': quantity(counted),
            'gap': quantity(gap),
            'gap_value': money((gap * price).quantize(CENT)),
            'share': gap_share,
            'expected_value': money(expected_value),
            'counted_value': money(counted_value),
            'status': (
                'missing' if expected and not counted
                else 'extra' if counted and not expected
                else 'alert' if flagged
                else 'ok'
            ),
            'unit_cost': money(item.unit_cost),
        })
    # Eng katta pul farqi yuqorida tursin.
    rows.sort(key=lambda row: abs(Decimal(row['gap_value'])), reverse=True)

    days = (end - start).days + 1
    reported = DailyUsage.objects.filter(
        branch=branch, date__gte=start, date__lte=end,
    ).order_by().values('date').distinct().count()
    return {
        'filters': {'start': start, 'end': end, 'days': days},
        'summary': {
            'system_value': money(system_value),
            'actual_value': money(actual_value),
            'gap_value': money(actual_value - system_value),
            'gap_share': share(abs(actual_value - system_value), system_value),
            'alerts': alerts,
            'items': len(rows),
            'reported_days': reported,
            'missing_days': max(days - reported, 0),
            'alert_threshold': str(ALERT_SHARE),
        },
        'rows': rows,
    }


class DailyUsageView(APIView):
    """Admin kunlik haqiqiy sarfni kiritadi va o‘z tarixini ko‘radi."""

    permission_classes = [SalesOnly]

    def get(self, request):
        filters = DailyUsageFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        data = filters.validated_data
        return Response({
            'filters': {'start': data['start'], 'end': data['end'], 'backdate_days': BACKDATE_DAYS},
            'days': day_rows(request.user.branch, data['start'], data['end']),
        })

    def post(self, request):
        serializer = DailyUsageInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Bir kun + bir mahsulot uchun bitta qator. Ikki admin bir vaqtda
        # yuborsa ikkinchisi unique cheklovga urilardi — endi 409.
        return Response(safely(save_daily_usage, request.user, serializer.validated_data), status=201)


class UsageComparisonView(APIView):
    """Superadmin: tizim hisobi va admin hisobi yonma-yon."""

    permission_classes = [OwnerOnly]

    def get(self, request):
        filters = DailyUsageFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        data = filters.validated_data
        return Response(build_comparison(request.user.branch, data['start'], data['end']))
