"""Moliyaviy kalkulyator uchun bir oylik faktlar.

Kalkulyator (`xonim_planner`, `/planner/` manzilida) «agar … bo'lsa nima
bo'ladi» degan savollarni hisoblaydi: yana bitta oshpaz olinsa, masalliq
qimmatlasa, narx oshirilsa. Unga boshlang'ich nuqta kerak — tanlangan oyda
haqiqatda nima bo'lgani. Bu modul aynan shu faktlarni beradi.

Asosiy raqamlar `build_finance` dan olinadi, qayta hisoblanmaydi:
kalkulyatordagi boshlang'ich holat «Umumiy moliya» sahifasidagi raqamlar
bilan bir xil bo'lishi shart. Bu yerda faqat moliya sahifasida yo'q kesimlar
qo'shiladi: taom bo'yicha sotuv, davomat bo'yicha hisoblangan ish haqi va
savdo bo'lgan kunlar soni.

Modelni qurish — qaysi xarajat doimiy, qaysi biri savdoga qarab o'zgaradi —
kalkulyator tomonida. Server faqat o'zi aniq biladigan narsani aytadi.
"""
from decimal import Decimal

from django.db.models import Case, Count, F, Q, Sum, When
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Dish
from core.i18n import _
from users.models import Employee
from users.permissions import OwnerOnly

from .finance import PRODUCE_CATEGORY, SALARY_CATEGORY, build_finance, known_months
from .models import Attendance, Order, OrderLine, Recipe, Table
from .money import (
    CENT,
    MONEY,
    ZERO,
    day_window,
    money,
    month_end,
    month_key,
    parse_month,
    previous_month,
)
from .services import recipe_cost

# Javob tuzilishi o'zgarsa oshiriladi: kalkulyator eski yoki yangi formatni
# taniy olishi kerak, aks holda jim noto'g'ri raqam ko'rsatardi.
PLANNER_VERSION = 1


class PlannerFilters(serializers.Serializer):
    month = serializers.RegexField(r'^\d{4}-\d{2}$', required=False)

    def validate_month(self, value):
        first = parse_month(value)
        if first > timezone.localdate().replace(day=1):
            raise serializers.ValidationError(_('Kelajak oyi uchun hisobot tuzilmaydi.'))
        return first


def default_month(branch, today):
    """Oxirgi TO'LIQ oy. Restoran shu oy ochilgan bo'lsa — joriy oy.

    Tugamagan oy reja uchun yomon boshlang'ich nuqta: ijara oyning boshida
    to'liq yoziladi, savdo esa hali yarim. Shuning uchun sukut bo'yicha
    o'tgan oy olinadi, joriy oyni esa faqat ataylab tanlash mumkin.
    """
    current = today.replace(day=1)
    return previous_month(current) if len(known_months(branch, today)) > 1 else current


def expense_kind(category):
    """Xarajat turini kalkulyator uchun belgilaydi.

    «Ish haqi» alohida, chunki kalkulyator maoshni davomatdan oladi — ikkinchi
    marta xarajat bo'lib kirsa, oylik ikki marta sanalardi. «Masalliq»
    alohida, chunki u savdo bilan birga o'sadi va ijaradek doimiy emas.
    """
    name = category.strip().lower()
    if name == SALARY_CATEGORY.lower():
        return 'salary'
    if name == PRODUCE_CATEGORY.lower():
        return 'produce'
    return 'other'


def dish_sales(lines):
    """Har bir taom bo'yicha: necha porsiya, menyu narxida qancha, tannarx.

    Menyu qiymati sotuv paytidagi narxdan olinadi (`menu_price`). Bonus
    qatorida `price` nol, lekin `menu_price` bor — aynan shu farq «tekin
    berilgan» pulni ko'rsatadi. Eski qatorlarda `menu_price` yo'q (nol), u
    yerda to'langan narxning o'zi menyu narxi.
    """
    each = Case(When(menu_price__gt=0, then=F('menu_price')), default=F('price'), output_field=MONEY)
    # .order_by() shart: Meta.ordering'dagi id guruhlashga tushib, har bir
    # qatorni alohida guruh qilib yuborardi. Nom ataylab «portions»:
    # `quantity=Sum('quantity')` maydonni yopib qo'yadi va keyingi ifodadagi
    # F('quantity') agregatga tushib, xato beradi.
    rows = lines.values('dish_id').annotate(
        portions=Coalesce(Sum('quantity'), 0),
        menu_value=Coalesce(Sum(each * F('quantity'), output_field=MONEY), ZERO, output_field=MONEY),
        cost=Coalesce(Sum('cost_total'), ZERO, output_field=MONEY),
    ).order_by()
    return {row['dish_id']: row for row in rows}


def recipe_unit_costs(branch, dish_ids):
    """Bugungi retsept bo'yicha bir porsiya tannarxi.

    Shu oy sotilmagan taom uchun kerak: unda muzlatilgan tannarx yo'q, lekin
    kalkulyatorda «shu taomni sotsak-chi?» deb sinab ko'rish mumkin bo'lsin.
    """
    recipes = Recipe.objects.filter(
        branch=branch, active=True, dish_id__in=dish_ids).prefetch_related('lines')
    return {
        recipe.dish_id: (recipe_cost(recipe) / recipe.yield_quantity).quantize(CENT)
        for recipe in recipes
    }


def payroll_facts(branch, start, end):
    """Davomat bo'yicha hisoblangan ish haqi: kim necha kun keldi, qancha yozildi.

    To'langan pul emas, HISOBLANGAN haq olinadi. Oylik keyingi oyning
    boshida berilsa, to'lov bo'yicha bu oy deyarli maoshsiz ko'rinardi —
    rejalashtirish uchun esa oyning haqiqiy mehnat xarajati kerak.
    """
    marks = {
        row['employee_id']: row
        for row in Attendance.objects.filter(
            branch=branch, present=True, date__gte=start, date__lte=end,
        ).values('employee_id').annotate(
            days=Count('id'), accrued=Coalesce(Sum('daily_wage'), ZERO, output_field=MONEY),
        ).order_by()
    }
    # Shu oy kelmagan, lekin hozir ishlayotgan xodim ham ro'yxatda turadi:
    # kalkulyatorda uni yoqib, «to'liq oy ishlasa-chi?» deb ko'rish mumkin.
    people = Employee.objects.filter(branch=branch).filter(Q(active=True) | Q(id__in=list(marks)))
    return [{
        'id': person.id,
        'name': person.name,
        'position': person.position,
        'active': person.active,
        'daily_wage': money(person.daily_wage),
        'days': marks[person.id]['days'] if person.id in marks else 0,
        'accrued': money(marks[person.id]['accrued'] if person.id in marks else ZERO),
    } for person in people]


def build_planner(branch, start, end, today):
    finance = build_finance(branch, start, end, today)
    profit = finance['profit']

    since, until = day_window(start, end)
    paid = Order.objects.filter(branch=branch, status='paid', paid_at__gte=since, paid_at__lt=until)
    lines = OrderLine.objects.filter(order__in=paid)
    sold = dish_sales(lines)

    # Savdo bo'lgan kunlar: kalkulyator kunlik raqamlarni (kuniga necha
    # buyurtma kerak) shu kunlar soniga bo'lib chiqaradi.
    open_days = paid.annotate(day=TruncDate('paid_at')).order_by().values('day').distinct().count()

    # Arxivdagi taom ham kerak, agar shu oy sotilgan bo'lsa: aks holda uning
    # tushumi kalkulyatorda yo'qolib, jami moliya sahifasidan farq qilardi.
    dishes = list(
        Dish.objects.filter(branch=branch).filter(Q(archived=False) | Q(id__in=list(sold)))
        .select_related('category').order_by('category__position', 'category_id', 'id')
    )
    unit_costs = recipe_unit_costs(branch, [dish.id for dish in dishes])
    categories = {}
    for dish in dishes:
        categories.setdefault(dish.category_id, dish.category.name)

    seats = Table.objects.filter(branch=branch, active=True).aggregate(
        total=Coalesce(Sum('seats'), 0))['total']

    return {
        'version': PLANNER_VERSION,
        'month': month_key(start),
        'start': start,
        'end': end,
        'days': (end - start).days + 1,
        # Oyning oxirgi kuni ham o'tib ketgan bo'lsagina oy to'liq.
        'complete': month_end(start) < today,
        'months': finance['months'],
        'branch': {'name': branch.name, 'seats': seats},
        'sales': {
            'revenue': profit['revenue'],
            'orders': profit['orders'],
            'items': profit['items'],
            'discounts': profit['discounts'],
            'open_days': open_days,
        },
        'cogs': profit['cogs'],
        'platform_fee': profit['platform_fee'],
        'waste': profit['waste'],
        'staff_meals': profit['staff_meals'],
        'partners': {
            'revenue': profit['partner_revenue'],
            'cogs': profit['partner_cogs'],
            'profit': profit['partner_profit'],
        },
        # Moliya sahifasidagi sof foydaning o'zi: kalkulyator o'z natijasini
        # shu raqam bilan solishtirib ko'rsatadi.
        'net_profit': profit['net_profit'],
        'channels': [{
            'channel': row['channel'],
            'label': row['label'],
            'revenue': row['revenue'],
            'fee': row['fee'],
            'orders': row['orders'],
        } for row in finance['channels']],
        'expenses': [{
            'category': row['category'],
            'amount': row['amount'],
            'kind': expense_kind(row['category']),
        } for row in finance['expenses']],
        'categories': [{'id': key, 'name': name} for key, name in categories.items()],
        'dishes': [{
            'id': dish.id,
            'name': dish.name,
            'category_id': dish.category_id,
            'price': money(dish.price),
            'unit_cost': money(unit_costs.get(dish.id, Decimal('0'))),
            'archived': dish.archived,
            'quantity': sold[dish.id]['portions'] if dish.id in sold else 0,
            'menu_value': money(sold[dish.id]['menu_value'] if dish.id in sold else ZERO),
            'cost': money(sold[dish.id]['cost'] if dish.id in sold else ZERO),
        } for dish in dishes],
        'payroll': payroll_facts(branch, start, end),
    }


class PlannerView(APIView):
    """Kalkulyator uchun bir oylik faktlar. Faqat superadmin.

    `?month=YYYY-MM` berilmasa oxirgi to'liq oy olinadi.
    """

    permission_classes = [OwnerOnly]

    def get(self, request):
        filters = PlannerFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        today = timezone.localdate()
        branch = request.user.branch
        first = filters.validated_data.get('month') or default_month(branch, today)
        end = min(month_end(first), today)
        return Response(build_planner(branch, first, end, today))
