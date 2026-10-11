"""Kalkulyator uchun faktlar (/api/v1/finance/planner/).

Eng muhim kafolat: faktlar «Umumiy moliya» sahifasidagi sof foydani TO'LIQ
tushuntirishi kerak. Biror qism (bonus, ushlanma, hamkor, hodimlar ovqati)
tushib qolsa, kalkulyatordagi boshlang'ich foyda Xonim'dagidan farq qiladi va
egasi qaysi biriga ishonishni bilmay qoladi.
"""
from datetime import datetime, time
from decimal import Decimal
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import Category, Dish
from operations.models import (
    Attendance,
    Expense,
    Ingredient,
    Order,
    OrderLine,
    Partner,
    PartnerDelivery,
    Recipe,
    RecipeLine,
    StaffMeal,
    StockMovement,
    Table,
)
from operations.money import month_key, next_month, previous_month
from users.models import Branch, Employee, User

URL = '/api/v1/finance/planner/'


def dec(value):
    return Decimal(value)


class PlannerFactsTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='Xonim', slug='xonim')
        self.owner = User.objects.create_user(
            'owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user(
            'cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

        # Hisobot oyi — o'tgan oy: u to'liq va sukut bo'yicha aynan u tanlanadi.
        self.current = timezone.localdate().replace(day=1)
        self.month = previous_month(self.current)

        self.food = Category.objects.create(branch=self.branch, name='Taom')
        self.osh = Dish.objects.create(
            branch=self.branch, category=self.food, name='Osh', price=Decimal('50000'))
        self.choy = Dish.objects.create(
            branch=self.branch, category=self.food, name='Choy', price=Decimal('10000'))
        self.somsa = Dish.objects.create(
            branch=self.branch, category=self.food, name='Somsa', price=Decimal('8000'))
        self.lagmon = Dish.objects.create(
            branch=self.branch, category=self.food, name='Lag‘mon', price=Decimal('40000'))

        self.meat = Ingredient.objects.create(
            branch=self.branch, name='Go‘sht', unit='kg',
            quantity=Decimal('10'), unit_cost=Decimal('80000'))
        recipe = Recipe.objects.create(
            branch=self.branch, dish=self.lagmon, name='Lag‘mon', yield_quantity=Decimal('2'))
        RecipeLine.objects.create(
            recipe=recipe, ingredient=self.meat, quantity=Decimal('0.2'), batch_cost=Decimal('16000'))

        Table.objects.create(branch=self.branch, number=1, seats=4)
        Table.objects.create(branch=self.branch, number=2, seats=6)
        Table.objects.create(branch=self.branch, number=3, seats=8, active=False)

    # --- yordamchilar ---

    def day(self, number, month=None):
        return (month or self.month).replace(day=number)

    def moment(self, number, month=None):
        return timezone.make_aware(datetime.combine(self.day(number, month), time(12)))

    def order(self, number, lines, *, channel='hall', commission='0', discount='0',
              service='0', branch=None, month=None):
        """Lines: (taom, soni, to'langan narx, menyu narxi, bir porsiya tannarxi, bonus)."""
        gross = sum((Decimal(price) * qty for _dish, qty, price, *_rest in lines), Decimal('0'))
        order = Order.objects.create(
            branch=branch or self.branch, cashier=self.owner, key=uuid4(), request_hash='x',
            total=gross - Decimal(discount), discount=Decimal(discount),
            service_charge=Decimal(service), channel=channel,
            channel_commission=Decimal(commission), status='paid', payment_method='cash',
            paid_at=self.moment(number, month),
        )
        for dish, qty, price, menu, cost, bonus in lines:
            OrderLine.objects.create(
                order=order, dish=dish, name=dish.name, price=Decimal(price), quantity=qty,
                menu_price=Decimal(menu), cost_per_unit=Decimal(cost),
                cost_total=Decimal(cost) * qty, bonus=bonus,
            )
        return order

    def expense(self, number, category, amount):
        Expense.objects.create(
            branch=self.branch, actor=self.owner, key=uuid4(), request_hash='x',
            category=category, purpose='sinov', amount=Decimal(amount),
            payment_method='cash', date=self.day(number),
        )

    def seed_month(self):
        # Zal: chegirma bilan. Xizmat haqi ofitsiantniki — tushumga kirmaydi.
        self.order(5, [
            (self.osh, 2, '50000', '50000', '20000', False),
            (self.choy, 1, '10000', '10000', '1000', False),
        ], discount='10000', service='11000')
        # Uzum: 30% ushlanma va tekin berilgan choy (bonus).
        self.order(6, [
            (self.osh, 1, '50000', '50000', '20000', False),
            (self.choy, 1, '0', '10000', '1000', True),
        ], channel='uzum', commission='30')
        # Eski qator: menyu narxi saqlanmagan (nol) — to'langan narx olinadi.
        self.order(6, [(self.somsa, 3, '8000', '0', '3000', False)])
        self.somsa.archived = True
        self.somsa.save()

        # Bekor qilingan hisob va boshqa filial savdosi faktlarga tushmaydi.
        Order.objects.create(
            branch=self.branch, cashier=self.owner, key=uuid4(), request_hash='x',
            total=Decimal('99000'), status='cancelled', void_reason='sinov',
            voided_at=self.moment(7), paid_at=None,
        )
        other = Branch.objects.create(name='Boshqa', slug='boshqa')
        other_food = Category.objects.create(branch=other, name='Taom')
        other_dish = Dish.objects.create(
            branch=other, category=other_food, name='Osh', price=Decimal('50000'))
        self.order(5, [(other_dish, 4, '50000', '50000', '20000', False)], branch=other)
        # Joriy oy savdosi o'tgan oyning faktlariga aralashmaydi.
        self.order(1, [(self.osh, 5, '50000', '50000', '20000', False)], month=self.current)

        self.expense(2, 'Ijara', '3000000')
        self.expense(3, 'Ish haqi', '400000')
        self.expense(4, 'Masalliq', '150000')
        self.expense(4, 'Kommunal', '250000')

        ali = Employee.objects.create(
            branch=self.branch, name='Ali', position='Oshpaz', daily_wage=Decimal('100000'))
        Employee.objects.create(
            branch=self.branch, name='Vali', position='Ofitsiant', daily_wage=Decimal('80000'))
        Employee.objects.create(
            branch=self.branch, name='Eski', position='Farrosh', daily_wage=Decimal('50000'),
            active=False)
        gone = Employee.objects.create(
            branch=self.branch, name='Ketgan', position='Yordamchi',
            daily_wage=Decimal('90000'), active=False)
        for number in (2, 3, 4):
            Attendance.objects.create(
                branch=self.branch, employee=ali, actor=self.owner, date=self.day(number),
                present=True, daily_wage=Decimal('100000'))
        Attendance.objects.create(
            branch=self.branch, employee=ali, actor=self.owner, date=self.day(5),
            present=False, daily_wage=Decimal('0'))
        Attendance.objects.create(
            branch=self.branch, employee=gone, actor=self.owner, date=self.day(2),
            present=True, daily_wage=Decimal('90000'))

        StaffMeal.objects.create(
            branch=self.branch, actor=self.owner, key=uuid4(), request_hash='x', dish=self.osh,
            name='Osh', quantity=1, menu_price=Decimal('50000'), cost_per_unit=Decimal('5000'),
            cost_total=Decimal('5000'), note='Ali', date=self.day(7))
        StockMovement.objects.create(
            branch=self.branch, ingredient=self.meat, actor=self.owner, key=uuid4(),
            request_hash='x', kind='consumption', quantity=Decimal('0.1'),
            unit_cost=Decimal('70000'), cost_total=Decimal('7000'), date=self.day(7), note='isrof')
        school = Partner.objects.create(branch=self.branch, name='1-maktab')
        PartnerDelivery.objects.create(
            branch=self.branch, partner=school, actor=self.owner, key=uuid4(), request_hash='x',
            date=self.day(8), status='reported', total=Decimal('300000'),
            cost_total=Decimal('120000'), due_total=Decimal('280000'),
            reported_at=self.moment(8))

    def facts(self, **params):
        response = self.client.get(URL, params)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    # --- kim ko'ra oladi ---

    def test_only_the_owner_sees_the_facts(self):
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        self.assertEqual(cashier.get(URL).status_code, 403)
        self.assertIn(APIClient().get(URL).status_code, (401, 403))

    # --- faktlar moliya sahifasi bilan bir xil ---

    def test_facts_match_the_finance_page_for_the_same_month(self):
        self.seed_month()
        month = month_key(self.month)
        facts = self.facts(month=month)
        finance = self.client.get('/api/v1/finance/', {'month': month}).data['profit']

        self.assertEqual(facts['sales']['revenue'], finance['revenue'])
        self.assertEqual(facts['net_profit'], finance['net_profit'])
        self.assertEqual(facts['cogs'], finance['cogs'])
        self.assertEqual(facts['platform_fee'], finance['platform_fee'])
        self.assertEqual(dec(facts['sales']['revenue']), Decimal('174000'))
        self.assertEqual(facts['sales']['orders'], 3)
        self.assertEqual(facts['sales']['items'], 8)
        self.assertEqual(facts['sales']['open_days'], 2)

    def test_facts_explain_the_whole_net_profit(self):
        """Faktlardagi qismlardan sof foydani qayta yig'ib bo'lishi shart."""
        self.seed_month()
        facts = self.facts(month=month_key(self.month))
        rebuilt = (
            dec(facts['sales']['revenue']) - dec(facts['cogs'])
            - dec(facts['platform_fee']) - dec(facts['waste']) - dec(facts['staff_meals'])
            - sum((dec(row['amount']) for row in facts['expenses']), Decimal('0'))
            + dec(facts['partners']['profit'])
        )
        self.assertEqual(rebuilt, dec(facts['net_profit']))
        self.assertEqual(dec(facts['net_profit']), Decimal('-3564000'))

    def test_dish_rows_add_up_to_the_month(self):
        self.seed_month()
        facts = self.facts(month=month_key(self.month))
        rows = {row['name']: row for row in facts['dishes']}

        self.assertEqual(sum(row['quantity'] for row in facts['dishes']), facts['sales']['items'])
        self.assertEqual(
            sum((dec(row['cost']) for row in facts['dishes']), Decimal('0')), dec(facts['cogs']))
        # Bonus menyu narxida sanaladi, eski qatorda esa to'langan narx olinadi.
        self.assertEqual(rows['Choy']['quantity'], 2)
        self.assertEqual(dec(rows['Choy']['menu_value']), Decimal('20000'))
        self.assertEqual(dec(rows['Somsa']['menu_value']), Decimal('24000'))
        # Menyu qiymati bilan tushum farqi — chegirma va bonus, boshqa hech narsa.
        menu_value = sum((dec(row['menu_value']) for row in facts['dishes']), Decimal('0'))
        self.assertEqual(menu_value - dec(facts['sales']['revenue']), Decimal('20000'))

    def test_archived_dish_stays_while_it_has_sales_and_unsold_dish_brings_its_recipe(self):
        self.seed_month()
        rows = {row['name']: row for row in self.facts(month=month_key(self.month))['dishes']}
        self.assertTrue(rows['Somsa']['archived'])
        self.assertEqual(rows['Somsa']['quantity'], 3)
        # Sotilmagan taom: retsept bo'yicha bugungi tannarx (16 000 / 2 porsiya).
        self.assertEqual(rows['Lag‘mon']['quantity'], 0)
        self.assertEqual(dec(rows['Lag‘mon']['unit_cost']), Decimal('8000'))

    def test_expenses_are_tagged_for_the_calculator(self):
        self.seed_month()
        kinds = {row['category']: row['kind'] for row in self.facts(month=month_key(self.month))['expenses']}
        self.assertEqual(kinds, {
            'Ijara': 'other', 'Kommunal': 'other', 'Ish haqi': 'salary', 'Masalliq': 'produce'})

    def test_payroll_is_accrued_from_attendance(self):
        self.seed_month()
        rows = {row['name']: row for row in self.facts(month=month_key(self.month))['payroll']}
        self.assertEqual((rows['Ali']['days'], dec(rows['Ali']['accrued'])), (3, Decimal('300000')))
        # Ishlayotgan, lekin shu oy kelmagan xodim ham ro'yxatda.
        self.assertEqual((rows['Vali']['days'], rows['Vali']['active']), (0, True))
        # Ketgan xodim, agar shu oy ishlagan bo'lsa, ko'rinadi; ishlamagani yo'q.
        self.assertEqual((rows['Ketgan']['days'], rows['Ketgan']['active']), (1, False))
        self.assertNotIn('Eski', rows)

    def test_channels_carry_the_platform_fee(self):
        self.seed_month()
        channels = {row['channel']: row for row in self.facts(month=month_key(self.month))['channels']}
        self.assertEqual(dec(channels['uzum']['fee']), Decimal('15000'))
        self.assertEqual(dec(channels['uzum']['revenue']), Decimal('50000'))
        self.assertEqual(dec(channels['hall']['fee']), Decimal('0'))

    def test_branch_facts(self):
        self.seed_month()
        facts = self.facts(month=month_key(self.month))
        self.assertEqual(facts['branch'], {'name': 'Xonim', 'seats': 10})
        self.assertEqual(facts['version'], 1)
        self.assertTrue(facts['complete'])
        self.assertEqual(dec(facts['partners']['profit']), Decimal('160000'))

    # --- qaysi oy ---

    def test_last_full_month_is_the_default(self):
        self.seed_month()
        facts = self.facts()
        self.assertEqual(facts['month'], month_key(self.month))
        self.assertEqual(facts['months'][:2], [month_key(self.current), month_key(self.month)])

    def test_a_new_restaurant_starts_with_the_current_month(self):
        facts = self.facts()
        self.assertEqual(facts['month'], month_key(self.current))
        self.assertFalse(facts['complete'])

    def test_future_and_broken_months_are_refused(self):
        for month in (month_key(next_month(self.current)), '2026-13', '0000-01', 'sentabr'):
            self.assertEqual(self.client.get(URL, {'month': month}).status_code, 400, month)
