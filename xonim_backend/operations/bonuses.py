"""Aksiya bonusi: buyurtmada shu taom bo'lsa, ustiga tekin qo'shiladi.

Uzum bilan shartnoma bo'yicha mijoz «Bozor honim» buyurtma qilsa, nechta
olganidan qat'i nazar ustiga bittasi tekin ketadi — 1 ta olsa 2 ta, 10 ta
olsa 11 ta chiqadi. Buyurtmada u taom bo'lmasa bonus ham yo'q, boshqa
taomlar esa bonusni uyg'otmaydi.

Bonus ODDIY BUYURTMA QATORI bo'lib yoziladi, narxi nol va `bonus` belgisi
bilan. Shu tanlov tufayli hech bir mavjud hisob o'zgartirilmadi: tushum
`Order.total` dan, tannarx esa qatorlarning `cost_total` yig'indisidan
olinadi, ya'ni nol narxli qator tushumga tegmaydi, lekin tannarxga ham,
ombor sarfiga ham, oshxona taloniga ham o'z-o'zidan tushadi. Ombor farqi
ham shuning uchun ochilmaydi.

Qoida kodda emas, bazada turadi va superadmin tahrirlaydi: aksiya tugashi,
taom qayta nomlanishi yoki boshqa kanalga ko'chishi mumkin. O'zgartirish
faqat keyingi sotuvlarga tegadi — o'tgan buyurtmadagi bonus qator bo'lib
yozilib qolgan.
"""
from decimal import Decimal

from django.db.models import Count, DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Dish
from core.i18n import _
from users.permissions import OwnerOnly, SalesOnly

from .models import SALE_CHANNEL_LABELS, SALE_CHANNELS, BonusRule, Order, OrderLine
from .money import day_window, money, period
from .services import audit

ZERO = Decimal('0')


def bonus_plan(branch, channel, dish_ids):
    """Qaysi taomdan nechtasi tekin ketishi. Bo'sh lug'at — bonus yo'q.

    Mijoz nechta olgani muhim emas: qoida «bor bo'lsa ustiga shuncha»
    deydi, shuning uchun bu yerda miqdor umuman o'qilmaydi.
    """
    if not dish_ids:
        return {}
    rows = BonusRule.objects.filter(
        branch=branch, channel=channel, active=True, dish_id__in=dish_ids,
    ).select_related('dish')
    return {rule.dish_id: rule.free_quantity for rule in rows if not rule.dish.archived}


def add_bonus_lines(order, plan, dishes, unit_cost_of, *, batch_key=None, added_at=None):
    """Bonus qatorlarini yozadi va nechta porsiya tekin ketganini qaytaradi.

    `unit_cost_of` — taom bo'yicha bir porsiyaning tannarxini beradigan
    funksiya; chaqiruvchi tomonda retseptlar allaqachon o'qilgan bo'ladi.

    `batch_key` ochiq hisobga qo'shilganda beriladi: qo'shimcha taloni aynan
    shu kalit bo'yicha yig'iladi, kalitsiz bonus oshxonaga yetib bormasdi.
    """
    written = 0
    for dish_id, free in plan.items():
        dish = dishes.get(dish_id)
        if not dish:
            continue
        unit_cost = unit_cost_of(dish)
        OrderLine.objects.create(
            order=order, dish=dish, name=dish.name,
            # Narx nol: mijoz bu porsiya uchun pul to'lamaydi.
            price=ZERO, menu_price=dish.price, quantity=free,
            note='', bonus=True,
            # Tannarx esa haqiqiy: masalliq ombordan chiqadi va foydadan
            # ayriladi. Aks holda tekin ovqat bepul bo'lib ko'rinardi.
            cost_per_unit=unit_cost, cost_total=unit_cost * free,
            batch_key=batch_key, added_at=added_at,
        )
        written += free
    return written


def already_bonused(order):
    """Shu hisobda allaqachon bonus olgan taomlar.

    Ochiq hisobga taom qo'shilganda kerak: bitta buyurtmaga bitta bonus,
    qo'shgan sayin yangisi tug'ilmaydi.
    """
    return set(
        OrderLine.objects.filter(order=order, bonus=True).values_list('dish_id', flat=True)
    )


# --- Qoidani boshqarish ---------------------------------------------------

class BonusRuleInput(serializers.Serializer):
    channel = serializers.ChoiceField(choices=[key for key, _label in SALE_CHANNELS])
    dish = serializers.IntegerField(min_value=1)
    free_quantity = serializers.IntegerField(min_value=1, max_value=99, default=1)
    active = serializers.BooleanField(default=True)


def rule_rows(branch):
    return [{
        'id': rule.id,
        'channel': rule.channel,
        'channel_label': SALE_CHANNEL_LABELS.get(rule.channel, rule.channel),
        'dish': rule.dish_id,
        'dish_name': rule.dish.name,
        'menu_price': money(rule.dish.price),
        'free_quantity': rule.free_quantity,
        'active': rule.active,
        'archived': rule.dish.archived,
        'updated_at': rule.updated_at,
    } for rule in BonusRule.objects.filter(branch=branch).select_related('dish')]


class BonusRuleView(APIView):
    """Superadmin aksiyani yoqadi, o'chiradi va nechta tekin ketishini belgilaydi."""

    permission_classes = [OwnerOnly]

    def get(self, request):
        return Response({'rows': rule_rows(request.user.branch)})

    def put(self, request):
        data = BonusRuleInput(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data
        dish = Dish.objects.filter(branch=request.user.branch, pk=fields['dish']).first()
        if not dish:
            raise serializers.ValidationError({'dish': _('Taom topilmadi.')})
        if dish.archived:
            raise serializers.ValidationError({'dish': _('Arxivlangan taomga bonus belgilab bo‘lmaydi.')})
        rule, created = BonusRule.objects.update_or_create(
            branch=request.user.branch, channel=fields['channel'], dish=dish,
            defaults={'free_quantity': fields['free_quantity'], 'active': fields['active']},
        )
        audit(
            request.user, 'bonus.rule',
            f'{SALE_CHANNEL_LABELS.get(rule.channel, rule.channel)} · {dish.name} · '
            f'ustiga {rule.free_quantity} ta tekin · {"yoqilgan" if rule.active else "o‘chirilgan"}',
        )
        return Response({
            'rows': rule_rows(request.user.branch),
            'detail': _('Saqlandi. Yangi qoida shu paytdan keyingi buyurtmalarga qo‘llanadi.'),
        }, status=201 if created else 200)

    def delete(self, request):
        rule = BonusRule.objects.filter(
            branch=request.user.branch, pk=request.query_params.get('id'),
        ).select_related('dish').first()
        if not rule:
            raise serializers.ValidationError(_('Bonus qoidasi topilmadi.'))
        name = rule.dish.name
        rule.delete()
        audit(request.user, 'bonus.rule', f'{name} · qoida o‘chirildi')
        return Response({'rows': rule_rows(request.user.branch), 'detail': _('Qoida o‘chirildi.')})


# --- Hisobot --------------------------------------------------------------

def bonus_figures(branch, start, end):
    """Davrda nechta porsiya tekin ketgani va u qancha turgani.

    «Qiymat» — menyu narxi: mijozga qancha pullik sovg'a qilinganini
    ko'rsatadi. «Tannarx» esa bizga aslida nechchiga tushgani va aynan u
    foydadan chiqib ketgan raqam. Ikkalasi ham kerak: birinchisi aksiyaning
    kattaligi, ikkinchisi uning narxi.
    """
    since, until = day_window(start, end)
    lines = OrderLine.objects.filter(
        order__branch=branch, order__status='paid', bonus=True,
        order__paid_at__gte=since, order__paid_at__lt=until,
    )
    # Qiymat bazada hisoblanadi: qator bo'yicha menyu narxi × miqdor.
    # Narx qatorda muzlatilgan, shuning uchun bugun menyu qimmatlashsa ham
    # o'tgan oyning bonus hisoboti o'zgarmaydi.
    value = Sum(F('menu_price') * F('quantity'), output_field=DecimalField(max_digits=16, decimal_places=2))
    totals = lines.aggregate(
        portions=Coalesce(Sum('quantity'), 0),
        value=Coalesce(value, ZERO),
        cost=Coalesce(Sum('cost_total'), ZERO),
        orders=Count('order_id', distinct=True),
    )
    rows = [{
        'dish': row['dish_id'],
        'name': row['name'],
        'portions': row['portions'],
        'orders': row['orders'],
        'value': money(row['value']),
        'cost': money(row['cost']),
    } for row in lines.values('dish_id', 'name').annotate(
        portions=Coalesce(Sum('quantity'), 0),
        value=Coalesce(value, ZERO),
        cost=Coalesce(Sum('cost_total'), ZERO),
        orders=Count('order_id', distinct=True),
    ).order_by('-portions')]
    return {
        'portions': totals['portions'],
        'value': money(totals['value']),
        'cost': money(totals['cost']),
        'orders': totals['orders'],
        'dishes': rows,
    }


class BonusReportView(APIView):
    """Bonuslar bo'limi: nechta porsiya tekin ketdi va qancha turdi."""

    permission_classes = [SalesOnly]

    def get(self, request):
        window = period(request.query_params)
        branch = request.user.branch
        figures = bonus_figures(branch, window['start'], window['end'])
        since, until = day_window(window['start'], window['end'])
        recent = OrderLine.objects.filter(
            order__branch=branch, order__status='paid', bonus=True,
            order__paid_at__gte=since, order__paid_at__lt=until,
        ).select_related('order')[:100]
        return Response({
            'filters': {'start': window['start'], 'end': window['end']},
            'summary': {
                'portions': figures['portions'],
                'value': figures['value'],
                'cost': figures['cost'],
                'orders': figures['orders'],
            },
            'dishes': figures['dishes'],
            'rows': [{
                'id': line.id,
                'order': line.order_id,
                'name': line.name,
                'quantity': line.quantity,
                'value': money(line.menu_price * line.quantity),
                'cost': money(line.cost_total),
                'channel': line.order.channel,
                'channel_label': SALE_CHANNEL_LABELS.get(line.order.channel, line.order.channel),
                'paid_at': line.order.paid_at,
            } for line in recent],
            'rules': rule_rows(branch) if request.user.role == 'owner' else [],
        })


def bonus_orders(branch, start, end):
    """Bonus tekkan hisoblar soni — «Sotuv» sahifasidagi qisqa ko'rsatkich."""
    since, until = day_window(start, end)
    return Order.objects.filter(
        branch=branch, status='paid', paid_at__gte=since, paid_at__lt=until,
    ).filter(Q(lines__bonus=True)).distinct().count()
