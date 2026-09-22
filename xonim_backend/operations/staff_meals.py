"""Hodimlar ovqati: o'z oshxonamizdan yegan taom.

Pul olinmaydi va bu hech kimning oyligiga ta'sir qilmaydi — yozuvning
butun maqsadi «oyiga qancha ketyapti» degan savolga javob berish. Shuning
uchun bu yerda na qarz bor, na to'lov: faqat taom, miqdor va kim yegani.

Kim yegani ro'yxatdan tanlanmaydi, izohda yoziladi. Sababi oddiy: mehmon
ham kelishi mumkin, bir kishi ikkinchisi uchun olishi ham mumkin, va
ro'yxat bu ikkalasini ham ushlay olmasdi.

Ovqat esa haqiqatda chiqadi. Demak masalliq ombordan ayirilishi va
tannarx foydadan chiqishi shart — aks holda ombor qoldig'i har kuni
sababsiz haqiqatdan ajralib ketardi va sabab hech qayerda ko'rinmasdi.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, DecimalField, F, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Dish
from core.i18n import _
from users.permissions import OwnerOnly, SalesOnly

from .models import StaffMeal
from .money import money, period
from .services import (
    Conflict,
    _recipes_for_dishes,
    audit,
    consume_recipe_stock,
    existing,
    fingerprint,
    recipe_cost,
    restore_stock_for,
    safely,
)

ZERO = Decimal('0')
# Bir yozuvda ko'pi bilan shuncha porsiya: bundan kattasi deyarli doim
# terish xatosi, va u jim turib ombordan katta miqdor ayirib yuborardi.
MAX_PORTIONS = 99


class StaffMealInput(serializers.Serializer):
    key = serializers.UUIDField()
    dish = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_PORTIONS)
    # Kim yegani — yozuvning butun ma'nosi. Bo'sh qoldirib bo'lmaydi.
    note = serializers.CharField(max_length=200, min_length=2)
    date = serializers.DateField(required=False)

    def validate_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError(_('Kelajakdagi sana mumkin emas.'))
        return value


def meal_payload(meal):
    return {
        'id': meal.id,
        'dish': meal.dish_id,
        'name': meal.name,
        'quantity': meal.quantity,
        'menu_price': money(meal.menu_price),
        'value': money(meal.menu_price * meal.quantity),
        'cost_total': money(meal.cost_total),
        'note': meal.note,
        'date': meal.date,
        'actor_name': meal.actor.first_name or meal.actor.username,
        'created_at': meal.created_at,
    }


def consume_meal_stock(user, meal):
    """Yegan ovqat masallig'ini ombordan ayiradi.

    Prefiks «O#» ataylab boshqacha: buyurtma qatorlarining «#12 buyurtma»
    qidiruvi va hamkorning «H#» qatorlari bu yozuvlarni tutib olmasligi
    kerak.
    """
    consume_recipe_stock(
        user, [meal],
        kind='staff_meal',
        tag=f'O#{meal.id} hodim ovqati',
        source={'staff_meal': meal.id},
        key_prefix=f'xonim-staff-meal-stock:{meal.id}',
    )


@transaction.atomic
def record_meal(user, data):
    """Yozuvni yozadi va masalliqni ombordan ayiradi."""
    dish = Dish.objects.filter(branch=user.branch, pk=data['dish']).first()
    if not dish:
        raise serializers.ValidationError({'dish': _('Taom topilmadi.')})

    recipe = _recipes_for_dishes(user.branch, [dish.id]).get(dish.id)
    unit_cost = (
        (recipe_cost(recipe) / recipe.yield_quantity).quantize(Decimal('0.01')) if recipe else ZERO
    )
    meal = StaffMeal.objects.create(
        branch=user.branch, actor=user, key=data['key'],
        request_hash=fingerprint(data),
        dish=dish, name=dish.name, quantity=data['quantity'],
        # Narx va tannarx yozuv paytida muzlatiladi: taom keyin qimmatlashsa
        # ham o'tgan oyning hisoboti o'zgarmaydi.
        menu_price=dish.price, cost_per_unit=unit_cost, cost_total=unit_cost * data['quantity'],
        note=data['note'], date=data.get('date') or timezone.localdate(),
    )
    # `meal` retsept yo'liga buyurtma qatori qiyofasida beriladi: unda ham
    # `dish_id`, `quantity`, `name` va `id` bor, boshqasi kerak emas.
    consume_meal_stock(user, meal)
    audit(
        user, 'staff.meal',
        f'{meal.name} · {meal.quantity} porsiya · {meal.note} · {money(meal.cost_total)} so‘m tannarx',
    )
    return meal


@transaction.atomic
def remove_meal(user, meal_id):
    """Xato yozilgan qatorni o'chiradi va masalliqni omborga qaytaradi."""
    meal = StaffMeal.objects.select_for_update().filter(
        branch=user.branch, pk=meal_id).select_related('dish').first()
    if not meal:
        raise serializers.ValidationError(_('Yozuv topilmadi.'))
    if meal.date != timezone.localdate():
        raise Conflict(_('Faqat bugungi yozuvni o‘chirish mumkin.'))

    restore_stock_for(
        user,
        kind='staff_meal',
        note_prefix=f'O#{meal.id} hodim ovqati · ',
        key_prefix=f'xonim-staff-meal-undo:{meal.id}',
        note=f'O#{meal.id} hodim ovqati o‘chirildi',
        label=f'O#{meal.id} o‘chirildi',
    )
    audit(user, 'staff.meal.delete', f'{meal.name} · {meal.quantity} porsiya · {meal.note}')
    meal.delete()


def staff_meal_figures(branch, start, end):
    """Davrda hodimlar qancha yegani: porsiya, menyu qiymati va tannarx.

    Tannarx — foydadan chiqib ketgan haqiqiy raqam. Menyu qiymati esa
    «agar sotilganda qancha bo'lardi» degan taqqoslash uchun; u hech qanday
    jamiga kirmaydi, chunki bu pul hech qachon mavjud bo'lmagan.
    """
    rows = StaffMeal.objects.filter(branch=branch, date__gte=start, date__lte=end)
    # Qiymat bazada hisoblanadi: ekrandagi ro'yxat 300 qator bilan
    # cheklangan va undan yig'ilsa jim turib kam chiqardi.
    return rows.aggregate(
        portions=Coalesce(Sum('quantity'), 0),
        cost=Coalesce(Sum('cost_total'), ZERO),
        value=Coalesce(
            Sum(F('menu_price') * F('quantity'),
                output_field=DecimalField(max_digits=16, decimal_places=2)),
            ZERO,
        ),
        records=Count('id'),
    )


class StaffMealView(APIView):
    """Hodimlar ovqati: yozish, ro'yxat va bugungisini o'chirish."""

    permission_classes = [SalesOnly]

    def get(self, request):
        window = period(request.query_params)
        branch = request.user.branch
        rows = list(
            StaffMeal.objects.filter(branch=branch, date__gte=window['start'], date__lte=window['end'])
            .select_related('actor', 'dish')[:300]
        )
        figures = staff_meal_figures(branch, window['start'], window['end'])
        by_dish = (
            StaffMeal.objects.filter(branch=branch, date__gte=window['start'], date__lte=window['end'])
            .values('dish_id', 'name')
            .annotate(portions=Coalesce(Sum('quantity'), 0), cost=Coalesce(Sum('cost_total'), ZERO))
            .order_by('-portions')
        )
        return Response({
            'filters': {'start': window['start'], 'end': window['end']},
            'summary': {
                'portions': figures['portions'],
                'cost': money(figures['cost']),
                'records': figures['records'],
                'value': money(figures['value']),
            },
            'dishes': [{
                'dish': row['dish_id'],
                'name': row['name'],
                'portions': row['portions'],
                'cost': money(row['cost']),
            } for row in by_dish],
            'rows': [meal_payload(row) for row in rows],
        })

    def post(self, request):
        data = StaffMealInput(data=request.data)
        data.is_valid(raise_exception=True)
        previous = existing(StaffMeal, request.user, data.validated_data)
        if previous:
            return Response(meal_payload(previous), status=200)
        meal = safely(record_meal, request.user, data.validated_data)
        return Response(meal_payload(meal), status=201)


class StaffMealRowView(APIView):
    """Xato yozilgan qatorni o'chirish — faqat superadmin va faqat bugungisi."""

    permission_classes = [OwnerOnly]

    def delete(self, request, pk):
        remove_meal(request.user, pk)
        return Response({'detail': _('Yozuv o‘chirildi va masalliq omborga qaytarildi.')})
