import base64
import re
from datetime import datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4
from zipfile import ZipFile

from django.conf import settings
from django.db import connection
from django.db.models import Sum
from django.test import SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from catalog.models import Category, Dish
from users.models import AuditEvent, Branch, User

from .models import (
    AssistantChat,
    AssistantMessage,
    DailyUsage,
    DishPrep,
    Expense,
    Ingredient,
    Order,
    OrderLine,
    PrintJob,
    Recipe,
    RecipeLine,
    SalaryPayment,
    ShiftClose,
    StockMovement,
    Table,
    Waiter,
    WaiterPayment,
)
from .money import money, percent, quantity, share
from .services import Conflict, append_order_lines, create_order, move_stock


def prepare(user, *dishes, quantity=999):
    """Testda sotuvdan oldin oshxona nima pishirganini yozadi.

    Tizim tayyor bo'lmagan taomni sotmaydi — oshxona talon kelgach
    pishirmaydi, u faqat tayyoridan yig'adi. Shuning uchun sotuvni
    tekshiradigan har bir test avval shu qadamdan o'tadi, xuddi haqiqiy
    kunda bo'lgani kabi. Miqdor ataylab katta: bu testlar qoldiqni emas,
    boshqa narsani tekshiradi.
    """
    DishPrep.objects.bulk_create([
        DishPrep(branch=user.branch, dish=dish, actor=user,
                 date=timezone.localdate(), quantity=quantity)
        for dish in dishes
    ])


class WorkflowTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.other = Branch.objects.create(name='Two', slug='two')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.kitchen = User.objects.create_user('kitchen', password='test-only-long-password', role='kitchen', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=45000)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def order_data(self):
        return {'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash', 'lines': [{'dish': self.dish.id, 'quantity': 2, 'note': ''}]}

    def test_server_price_snapshot_and_idempotency(self):
        data = self.order_data()
        first = create_order(self.owner, data)
        self.dish.price = 60000
        self.dish.save()
        second = create_order(self.owner, data)
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.total, Decimal('90000'))
        self.assertEqual(first.lines.get().price, Decimal('45000'))
        self.assertEqual(Order.objects.count(), 1)
        data['lines'][0]['quantity'] = 3
        with self.assertRaises(Conflict):
            create_order(self.owner, data)

    def test_branch_category_injection_blocked(self):
        category = Category.objects.create(branch=self.other, name='Other')
        response = self.client.post('/api/v1/dishes/', {'category': category.id, 'name': 'Bad', 'price': '100'})
        self.assertEqual(response.status_code, 400)
        self.assertNotIn(category.id, [item['id'] for item in self.client.get('/api/v1/categories/').data['results']])

    def test_cashier_runs_the_day_but_does_not_set_the_rules(self):
        self.client.force_authenticate(self.cashier)
        # Kundalik ish — kassirda: xarajat, ombor, kunlik sarf, stollar.
        self.assertEqual(self.client.get('/api/v1/expenses/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/ingredients/').status_code, 200)
        self.assertEqual(self.client.get('/api/v1/daily-usage/').status_code, 200)
        self.assertEqual(self.client.post('/api/v1/tables/', {'number': 77}, format='json').status_code, 201)
        # Qoida va nazorat — superadminda.
        self.assertEqual(self.client.post('/api/v1/categories/', {'name': 'No'}).status_code, 403)
        self.assertEqual(self.client.get('/api/v1/recipes/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/dashboard/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/finance/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/staff/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/shift/history/').status_code, 403)
        # Ombor harakatlari tarixi ham nazorat vositasi: kassir kirim yozadi,
        # lekin qaysi taomga qancha ketganini ko'rmaydi.
        self.assertEqual(self.client.get('/api/v1/stock/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/daily-usage/compare/').status_code, 403)

    def test_only_owner_creates_staff_and_password_is_never_returned(self):
        response = self.client.post('/api/v1/staff/', {
            'name': 'Yangi kassir', 'username': 'branch_cashier',
            'role': 'cashier', 'password': 'Safe-test-password-48!'
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('password', response.data)
        created = User.objects.get(username='branch_cashier')
        self.assertTrue(created.check_password('Safe-test-password-48!'))
        self.assertEqual(created.branch, self.branch)
        # «Admin» roli olib tashlandi — uni tanlab bo'lmaydi.
        self.assertEqual(self.client.post('/api/v1/staff/', {
            'name': 'Eski rol', 'username': 'old_admin',
            'role': 'admin', 'password': 'Safe-test-password-50!'
        }, format='json').status_code, 400)
        self.client.force_authenticate(created)
        self.assertEqual(self.client.post('/api/v1/staff/', {
            'name': 'No', 'username': 'no_staff',
            'role': 'cashier', 'password': 'Safe-test-password-49!'
        }, format='json').status_code, 403)

    def test_owner_updates_employee_and_the_wage_payment_hits_finance_once(self):
        employee = User.objects.create_user(
            'manager', password='Safe-test-password-51!', first_name='Menejer',
            role='cashier', branch=self.branch, daily_wage=Decimal('130000')
        )
        detail = f'/api/v1/staff/{employee.id}/'
        response = self.client.patch(detail, {
            'phone': '+998901234567', 'daily_wage': '150000', 'active': True,
            'hired_at': str(timezone.localdate()), 'notes': 'Bosh admin'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        employee.refresh_from_db()
        self.assertEqual(employee.daily_wage, Decimal('150000'))
        self.assertEqual(employee.phone, '+998901234567')

        payload = {
            'key': str(uuid4()), 'amount': '900000', 'payment_method': 'card',
            'paid_on': str(timezone.localdate()), 'note': 'Haftalik'
        }
        pay_url = f'/api/v1/staff/{employee.id}/salary-payments/'
        self.assertEqual(self.client.post(pay_url, payload, format='json').status_code, 201)
        # Bir xil kalit bilan ikkinchi so'rov yangi pul bermaydi.
        self.assertEqual(self.client.post(pay_url, payload, format='json').status_code, 200)
        self.assertEqual(SalaryPayment.objects.filter(employee=employee).count(), 1)
        expense = Expense.objects.get(category='Ish haqi')
        self.assertEqual(expense.amount, Decimal('900000'))
        self.assertEqual(expense.recipient, 'Menejer')
        dashboard = self.client.get('/api/v1/dashboard/').data
        self.assertEqual(Decimal(dashboard['expenses']), Decimal('900000'))

        # Kassir pul bera oladi, lekin xodim kartasini o'zgartira olmaydi.
        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.client.patch(detail, {'daily_wage': '1'}, format='json').status_code, 403)
        self.assertEqual(self.client.get(pay_url).status_code, 200)

    def test_stock_exactly_once_and_no_negative_balance(self):
        ingredient = Ingredient.objects.create(branch=self.branch, name='Guruch', unit='kg', quantity=50)
        data = {'key': uuid4(), 'ingredient': ingredient.id, 'kind': 'consumption', 'quantity': Decimal('12'), 'date': timezone.localdate(), 'note': 'Kunlik sarf'}
        move_stock(self.owner, data)
        move_stock(self.owner, data)
        ingredient.refresh_from_db()
        self.assertEqual(ingredient.quantity, 38)
        self.assertEqual(StockMovement.objects.count(), 1)
        response = self.client.post('/api/v1/stock/', {**data, 'key': str(uuid4()), 'quantity': '40'}, format='json')
        self.assertEqual(response.status_code, 400)
        ingredient.refresh_from_db()
        self.assertEqual(ingredient.quantity, 38)

    def test_public_menu_read_only_and_archived_hidden(self):
        self.dish.archived = True
        self.dish.save()
        client = APIClient()
        self.assertEqual(client.get('/api/v1/public/menu/one/').data['dishes'], [])
        self.assertEqual(client.post('/api/v1/public/menu/one/', {}).status_code, 405)
        self.assertEqual(client.get('/api/v1/orders/').status_code, 403)

    def test_login_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        payload = {'username': 'owner', 'password': 'test-only-long-password'}
        self.assertEqual(client.post('/api/v1/auth/login/', payload).status_code, 403)
        token = client.get('/api/v1/auth/csrf/').data['csrfToken']
        self.assertEqual(client.post('/api/v1/auth/login/', payload, HTTP_X_CSRFTOKEN=token).status_code, 200)
        self.assertEqual(client.post('/api/v1/categories/', {'name': 'Unsafe'}).status_code, 403)

    def test_expense_and_dashboard_use_actual_records(self):
        data = {'key': str(uuid4()), 'category': 'Kommunal', 'purpose': 'Elektr', 'amount': '10000', 'payment_method': 'cash', 'date': str(timezone.localdate())}
        self.assertEqual(self.client.post('/api/v1/expenses/', data).status_code, 201)
        self.assertEqual(self.client.post('/api/v1/expenses/', data).status_code, 201)
        create_order(self.owner, self.order_data())
        dashboard = self.client.get('/api/v1/dashboard/').data
        self.assertEqual(Decimal(dashboard['revenue']), 90000)
        self.assertEqual(Decimal(dashboard['expenses']), 10000)
        self.assertEqual(Decimal(dashboard['net_cash']), 80000)

    def test_dashboard_month_filter_scopes_every_figure(self):
        today = timezone.localdate()
        this_month = today.replace(day=1)
        previous_month = (this_month - timedelta(days=1)).replace(day=1)
        create_order(self.owner, self.order_data())
        older = create_order(self.owner, self.order_data())
        Order.objects.filter(pk=older.pk).update(paid_at=timezone.make_aware(datetime.combine(previous_month, time(12, 0))))
        expense = {'key': str(uuid4()), 'category': 'Ijara', 'purpose': 'Ofis', 'amount': '50000', 'payment_method': 'cash', 'date': str(previous_month)}
        self.assertEqual(self.client.post('/api/v1/expenses/', expense).status_code, 201)

        current = self.client.get('/api/v1/dashboard/', {'month': this_month.strftime('%Y-%m')}).data
        self.assertEqual(current['period']['kind'], 'month')
        self.assertEqual(current['paid_count'], 1)
        self.assertEqual(Decimal(current['revenue']), 90000)
        self.assertEqual(Decimal(current['expenses']), 0)
        # The month before is the comparison window, so last month's sale shows up there.
        self.assertEqual(Decimal(current['previous_revenue']), 90000)
        self.assertEqual(len(current['trend']), today.day)

        earlier = self.client.get('/api/v1/dashboard/', {'month': previous_month.strftime('%Y-%m')}).data
        self.assertEqual(earlier['paid_count'], 1)
        self.assertEqual(Decimal(earlier['expenses']), 50000)
        self.assertEqual(Decimal(earlier['previous_revenue']), 0)
        self.assertEqual(len(earlier['trend']), (this_month - previous_month).days)
        self.assertIn(previous_month.strftime('%Y-%m'), earlier['months'])
        self.assertIn(this_month.strftime('%Y-%m'), earlier['months'])

    def test_cashier_sees_live_takings_but_kitchen_does_not(self):
        today = timezone.localdate()
        create_order(self.cashier, self.order_data())
        create_order(self.owner, self.order_data())
        older = create_order(self.owner, self.order_data())
        Order.objects.filter(pk=older.pk).update(paid_at=timezone.make_aware(datetime.combine(today - timedelta(days=1), time(12, 0))))
        unpaid = self.order_data()
        unpaid['payment_method'] = ''
        create_order(self.cashier, unpaid)

        self.client.force_authenticate(self.cashier)
        summary = self.client.get('/api/v1/sales/summary/').data
        self.assertEqual(Decimal(summary['today']['revenue']), 180000)
        self.assertEqual(summary['today']['orders'], 2)
        self.assertEqual(Decimal(summary['yesterday']['revenue']), 90000)
        self.assertEqual(Decimal(summary['last_7_days']['revenue']), 270000)
        # Only the signed-in cashier's own sales, not the whole till.
        self.assertEqual(Decimal(summary['mine_today']['revenue']), 90000)
        self.assertEqual(summary['mine_today']['orders'], 1)
        self.assertEqual(summary['open']['orders'], 1)
        self.assertEqual(Decimal(summary['open']['revenue']), 90000)
        self.assertEqual(len(summary['today_by_method']), 1)
        self.assertEqual(summary['today_by_method'][0]['method'], 'cash')
        self.assertEqual(summary['today_by_method'][0]['label'], 'Naqd')
        self.assertEqual(Decimal(summary['today_by_method'][0]['revenue']), 180000)

        self.client.force_authenticate(self.kitchen)
        self.assertEqual(self.client.get('/api/v1/sales/summary/').status_code, 403)

    def test_cashier_appends_to_open_bill_and_kitchen_sees_it_again(self):
        second = Dish.objects.create(branch=self.branch, category=self.category, name='Choy', price=8000)
        prepare(self.cashier, second)
        data = self.order_data()
        data['payment_method'] = ''
        order = create_order(self.cashier, data)
        self.assertEqual(order.total, 90000)

        self.client.force_authenticate(self.cashier)
        url = f'/api/v1/orders/{order.id}/lines/'
        payload = {'key': str(uuid4()), 'lines': [{'dish': second.id, 'quantity': 3, 'note': 'issiq'}]}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Decimal(response.data['total']), 114000)
        self.assertEqual(len(response.data['lines']), 2)
        self.assertEqual([line['added'] for line in response.data['lines']], [False, True])

        # The same request twice must not charge the guest twice.
        repeat = self.client.post(url, payload, format='json')
        self.assertEqual(repeat.status_code, 200)
        self.assertEqual(Decimal(repeat.data['total']), 114000)
        self.assertEqual(len(repeat.data['lines']), 2)

        # A finished ticket returns to the kitchen board so the new dish gets cooked.
        Order.objects.filter(pk=order.pk).update(preparation_status='served', served_at=timezone.now())
        self.client.post(url, {'key': str(uuid4()), 'lines': [{'dish': second.id, 'quantity': 1, 'note': ''}]}, format='json')
        order.refresh_from_db()
        self.assertEqual(order.preparation_status, 'queued')
        self.assertIsNone(order.served_at)
        self.assertEqual(order.total, 122000)

        # Paying closes the bill for further additions, and the stock leaves once.
        self.assertEqual(self.client.post(f'/api/v1/orders/{order.id}/pay/', {'payment_method': 'cash'}).status_code, 200)
        closed = self.client.post(url, {'key': str(uuid4()), 'lines': [{'dish': second.id, 'quantity': 1, 'note': ''}]}, format='json')
        self.assertEqual(closed.status_code, 409)

        self.client.force_authenticate(self.kitchen)
        self.assertEqual(self.client.post(url, {'key': str(uuid4()), 'lines': [{'dish': second.id, 'quantity': 1, 'note': ''}]}, format='json').status_code, 403)

    def test_table_holds_one_open_bill_and_frees_up_after_payment(self):
        from .models import Table, TableZone

        table = Table.objects.create(branch=self.branch, number=4, zone=TableZone.HALL_RIGHT, seats=4)
        self.client.force_authenticate(self.cashier)

        data = self.order_data()
        data['payment_method'] = ''
        data['table_id'] = table.id
        data['table'] = ''
        order = create_order(self.cashier, data)
        # Stol matni cheklar va hisobotlar uchun raqamdan to'ldiriladi.
        self.assertEqual(order.table, '4')
        self.assertEqual(order.table_ref, table)

        listed = next(row for row in self.client.get('/api/v1/tables/').data['results'] if row['id'] == table.id)
        self.assertEqual(listed['label'], '4-stol')
        self.assertEqual(Decimal(listed['open_order']['total']), 90000)
        self.assertEqual(listed['open_order']['items'], 2)

        # Bitta stolda ikkita ochiq hisob bo'lmaydi: taom mavjud hisobga qo'shiladi.
        second = self.order_data()
        second['payment_method'] = ''
        second['table_id'] = table.id
        second['table'] = ''
        with self.assertRaises(Conflict):
            create_order(self.cashier, second)

        self.assertEqual(self.client.post(f'/api/v1/orders/{order.id}/pay/', {'payment_method': 'cash'}).status_code, 200)
        freed = next(row for row in self.client.get('/api/v1/tables/').data['results'] if row['id'] == table.id)
        self.assertIsNone(freed['open_order'])

        # Stol endi kassirda: zalni qayta joylash kundalik ish.
        self.assertEqual(self.client.post('/api/v1/tables/', {'number': 99}, format='json').status_code, 201)
        self.assertEqual(self.client.post('/api/v1/tables/', {'number': 99}, format='json').status_code, 400)

    def test_prep_tickets_split_by_station_and_carry_no_prices(self):
        from catalog.models import Station
        from operations import printing

        drinks = Category.objects.create(branch=self.branch, name='Ichimliklar', station=Station.COUNTER)
        water = Dish.objects.create(branch=self.branch, category=drinks, name='Suv', price=5000)
        # Kategoriyasi kassa, lekin o'zi oshxonada damlanadi - alohida qiymat kategoriyadan ustun.
        tea = Dish.objects.create(branch=self.branch, category=drinks, name='Choy', price=8000, station=Station.KITCHEN)
        prepare(self.cashier, water, tea)

        data = self.order_data()
        data['payment_method'] = ''
        data['table'] = '4'
        data['waiter'] = 'Fazliddin'
        data['lines'] = [
            {'dish': self.dish.id, 'quantity': 2, 'note': 'achchiq bo‘lmasin'},
            {'dish': water.id, 'quantity': 3, 'note': ''},
            {'dish': tea.id, 'quantity': 1, 'note': ''},
        ]
        order = create_order(self.cashier, data)

        groups = printing.group_by_station(list(order.lines.select_related('dish__category')))
        self.assertEqual({line.name for line in groups['kitchen']}, {'Osh', 'Choy'})
        self.assertEqual({line.name for line in groups['counter']}, {'Suv'})

        kitchen = printing.prep_ticket_bytes(order, 'kitchen', groups['kitchen']).decode('ascii')
        self.assertIn('OSHXONA', kitchen)
        self.assertIn('#0001'[:1], kitchen)
        self.assertIn('4-STOL', kitchen)
        self.assertIn('Fazliddin', kitchen)
        self.assertIn('2 x Osh', kitchen)
        self.assertIn("achchiq bo'lmasin", kitchen)
        self.assertNotIn('Suv', kitchen)
        # Oshpazga narx kerak emas va ko'rinmasligi kerak.
        self.assertNotIn('45 000', kitchen)
        self.assertNotIn('so\'m', kitchen)

        counter = printing.prep_ticket_bytes(order, 'counter', groups['counter']).decode('ascii')
        self.assertIn('KASSA', counter)
        self.assertIn('3 x Suv', counter)
        self.assertNotIn('Osh', counter)

        # Qo'shimcha talon faqat yangi qatorlarni oladi va shundayligini aytadi.
        append = {'key': uuid4(), 'lines': [{'dish': water.id, 'quantity': 1, 'note': ''}]}
        append_order_lines(self.cashier, order.id, append)
        fresh = list(OrderLine.objects.filter(order=order, batch_key=append['key']).select_related('dish__category'))
        extra = printing.prep_ticket_bytes(order, 'counter', fresh, addition=True).decode('ascii')
        self.assertIn('QO\'SHIMCHA BUYURTMA', extra)
        self.assertIn('1 x Suv', extra)
        self.assertNotIn('3 x Suv', extra)

        # Printer sozlanmagan bo'lsa savdo yoziladi, lekin muammo kassirga qaytadi.
        with override_settings(RECEIPT_PRINTER='', KITCHEN_PRINTER=''):
            quiet = self.order_data()
            quiet['payment_method'] = ''
            saved = create_order(self.cashier, quiet)
        self.assertTrue(Order.objects.filter(pk=saved.pk).exists())
        self.assertTrue(saved.print_problems)
        self.assertIn('Oshxona', ' '.join(saved.print_problems))

    def test_receipt_layout_and_printer_failure_never_loses_the_sale(self):
        from operations import printing

        order = create_order(self.cashier, self.order_data())
        text = printing.receipt_bytes(order).decode('ascii')
        self.assertIn('XONIM', text)
        self.assertIn('Osh', text)
        self.assertIn('90 000', text)
        self.assertIn('FISKAL CHEK EMAS', text)
        self.assertIn("To'lov: Naqd", text)
        # Printer typografik apostrofni bilmaydi, chek sof ASCII bo'lishi shart.
        self.assertTrue(all(ord(ch) < 128 for ch in text))
        # 48 belgi kengligi sinov chekida o'lchangan.
        body = [line for line in text.split('\n') if not line.startswith('\x1b')]
        self.assertTrue(max(len(line) for line in body) <= printing.WIDTH)
        self.assertTrue(printing.receipt_bytes(order).endswith(printing.CUT))
        self.assertIn(printing.OPEN_DRAWER, printing.receipt_bytes(order, open_drawer=True))
        self.assertNotIn(printing.OPEN_DRAWER, printing.receipt_bytes(order, open_drawer=False))

        # Printer o'chiq bo'lsa ham savdo yozilib qolishi kerak.
        with override_settings(RECEIPT_PRINTER='YOQ-BUNDAY-PRINTER', RECEIPT_AUTO_PRINT=True):
            with self.assertLogs('operations.printing', level='WARNING'):
                self.assertFalse(printing.print_receipt_quietly(order))
            data = self.order_data()
            data['key'] = uuid4()
            paid = create_order(self.cashier, data)
        self.assertEqual(paid.status, 'paid')
        self.assertTrue(Order.objects.filter(pk=paid.pk).exists())

        # Sozlanmagan bo'lsa qo'lda chop etish tushunarli xato beradi.
        self.client.force_authenticate(self.cashier)
        with override_settings(RECEIPT_PRINTER=''):
            response = self.client.post(f'/api/v1/orders/{order.id}/print/')
        self.assertEqual(response.status_code, 409)
        self.client.force_authenticate(self.kitchen)
        self.assertEqual(self.client.post(f'/api/v1/orders/{order.id}/print/').status_code, 403)

    def test_wallet_payments_reach_every_report(self):
        for method in ('cash', 'uzum', 'click', 'yandex'):
            data = self.order_data()
            data['payment_method'] = method
            create_order(self.owner, data)

        dashboard = self.client.get('/api/v1/dashboard/').data
        self.assertEqual(
            {row['method']: row['label'] for row in dashboard['by_method']},
            {'cash': 'Naqd', 'uzum': 'Uzum', 'click': 'Click', 'yandex': 'Yandex'},
        )
        # Each method separately must add back up to the headline figure.
        self.assertEqual(sum(Decimal(row['revenue']) for row in dashboard['by_method']), Decimal(dashboard['revenue']))

        report = self.client.get('/api/v1/reports/sales/').data
        self.assertEqual({row['method'] for row in report['summary']['by_method']}, {'cash', 'uzum', 'click', 'yandex'})
        self.assertEqual(
            sum(Decimal(row['revenue']) for row in report['summary']['by_method']),
            Decimal(report['summary']['revenue']),
        )

        board = self.client.get('/api/v1/sales/board/').data
        self.assertEqual({row['label'] for row in board['methods']}, {'Naqd', 'Uzum', 'Click', 'Yandex'})

        pending = self.order_data()
        pending['payment_method'] = ''
        order = create_order(self.owner, pending)
        self.assertEqual(self.client.post(f'/api/v1/orders/{order.id}/pay/', {'payment_method': 'click'}).status_code, 200)
        self.assertEqual(self.client.post(f'/api/v1/orders/{order.id}/pay/', {'payment_method': 'payme'}).status_code, 400)

        listed = {item['method'] for item in self.client.get('/api/v1/auth/me/').data['payment_methods']}
        self.assertEqual(listed, {'cash', 'card', 'terminal', 'uzum', 'click', 'yandex'})

    def test_sales_board_groups_what_sold_and_respects_filters(self):
        create_order(self.cashier, self.order_data())
        create_order(self.owner, self.order_data())
        self.client.force_authenticate(self.cashier)

        board = self.client.get('/api/v1/sales/board/').data
        self.assertEqual(Decimal(board['summary']['revenue']), 180000)
        self.assertEqual(board['summary']['orders'], 2)
        self.assertEqual(board['summary']['items'], 4)
        self.assertEqual(Decimal(board['summary']['average_check']), 90000)
        self.assertEqual(board['summary']['top_dish'], 'Osh')
        self.assertEqual(len(board['dishes']), 1)
        self.assertEqual(board['dishes'][0]['quantity'], 4)
        self.assertEqual(Decimal(board['dishes'][0]['revenue']), 180000)
        self.assertEqual([row['label'] for row in board['methods']], ['Naqd'])
        self.assertEqual(len(board['cashiers']), 2)
        self.assertEqual(len(board['checks']), 2)
        self.assertEqual(sum(row['orders'] for row in board['hours']), 2)
        # The board is for selling, not costing: no recipe cost or margin leaks here.
        self.assertNotIn('cost', board['summary'])
        self.assertNotIn('gross_profit', board['summary'])

        mine = self.client.get('/api/v1/sales/board/', {'mine': 'true'}).data
        self.assertEqual(Decimal(mine['summary']['revenue']), 90000)
        self.assertEqual(len(mine['cashiers']), 1)
        self.assertEqual(len(mine['checks']), 1)

        empty_category = Category.objects.create(branch=self.branch, name='Ichimlik')
        filtered = self.client.get('/api/v1/sales/board/', {'category': empty_category.id}).data
        self.assertEqual(filtered['summary']['orders'], 0)
        self.assertEqual(Decimal(filtered['summary']['revenue']), 0)
        self.assertEqual(self.client.get('/api/v1/sales/board/', {'category': 999999}).status_code, 400)

        self.client.force_authenticate(self.kitchen)
        self.assertEqual(self.client.get('/api/v1/sales/board/').status_code, 403)

    def test_dashboard_rejects_broken_and_future_months(self):
        future = (timezone.localdate().replace(day=28) + timedelta(days=10)).replace(day=1)
        self.assertEqual(self.client.get('/api/v1/dashboard/', {'month': '2026-13'}).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/dashboard/', {'month': 'sentabr'}).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/dashboard/', {'month': future.strftime('%Y-%m')}).status_code, 400)
        self.assertEqual(self.client.get('/api/v1/dashboard/', {'days': 14}).status_code, 400)
        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.client.get('/api/v1/dashboard/', {'month': '2026-09'}).status_code, 403)

    def test_payment_repeat_not_double_counted(self):
        data = self.order_data()
        data['payment_method'] = ''
        order = create_order(self.owner, data)
        url = f'/api/v1/orders/{order.id}/pay/'
        self.assertEqual(self.client.post(url, {'payment_method': 'cash'}).status_code, 200)
        self.assertEqual(self.client.post(url, {'payment_method': 'cash'}).status_code, 200)
        self.assertEqual(self.client.post(url, {'payment_method': 'card'}).status_code, 409)
        self.assertEqual(self.client.get('/api/v1/dashboard/').data['paid_count'], 1)

    def test_kitchen_receives_order_and_advances_only_in_sequence(self):
        order = create_order(self.owner, self.order_data())
        self.client.force_authenticate(self.kitchen)
        kitchen_url = '/api/v1/kitchen/orders/'
        response = self.client.get(kitchen_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['id'], order.id)
        self.assertEqual(response.data[0]['preparation_status'], 'queued')
        self.assertEqual(self.client.get('/api/v1/orders/').status_code, 403)
        self.assertEqual(self.client.post('/api/v1/categories/', {'name': 'No'}).status_code, 403)
        self.assertEqual(self.client.get('/api/v1/expenses/').status_code, 403)

        status_url = f'/api/v1/kitchen/orders/{order.id}/status/'
        self.assertEqual(self.client.post(status_url, {'status': 'ready'}, format='json').status_code, 409)
        for status in ('preparing', 'ready', 'served'):
            response = self.client.post(status_url, {'status': status}, format='json')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data['preparation_status'], status)
        self.assertEqual(self.client.get(kitchen_url).data, [])

    def test_sales_report_filters_and_exports_excel_for_managers(self):
        dessert = Category.objects.create(branch=self.branch, name='Shirinlik')
        cake = Dish.objects.create(branch=self.branch, category=dessert, name='Tort', price=20000)
        prepare(self.owner, cake)
        first = create_order(self.owner, self.order_data())
        second = create_order(self.owner, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'card',
            'lines': [{'dish': cake.id, 'quantity': 3, 'note': ''}],
        })
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        Order.objects.filter(pk=first.pk).update(paid_at=timezone.make_aware(datetime.combine(yesterday, time(12))))
        Order.objects.filter(pk=second.pk).update(paid_at=timezone.make_aware(datetime.combine(today, time(13))))
        url = f'/api/v1/reports/sales/?start={yesterday}&end={today}&group=day'
        report = self.client.get(url)
        self.assertEqual(report.status_code, 200)
        self.assertEqual(Decimal(report.data['summary']['revenue']), Decimal('150000'))
        self.assertEqual(report.data['summary']['orders'], 2)
        self.assertEqual(report.data['summary']['items'], 5)
        self.assertEqual(len(report.data['trend']), 2)

        filtered = self.client.get(f'{url}&category={dessert.id}')
        self.assertEqual(Decimal(filtered.data['summary']['revenue']), Decimal('60000'))
        self.assertEqual(filtered.data['dishes'][0]['dish'], 'Tort')
        export = self.client.get(f'/api/v1/reports/sales/export/?start={yesterday}&end={today}&dish={cake.id}')
        self.assertEqual(export.status_code, 200)
        self.assertTrue(export.content.startswith(b'PK'))
        self.assertEqual(export['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        with ZipFile(BytesIO(export.content)) as workbook:
            self.assertIsNone(workbook.testzip())
            self.assertIn('xl/worksheets/sheet4.xml', workbook.namelist())
            self.assertIn(b'Tort', workbook.read('xl/worksheets/sheet4.xml'))

        # Savdo hisoboti endi faqat superadminda.
        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_authenticate(self.kitchen)
        self.assertEqual(self.client.get(url).status_code, 403)


class ActivityLogTests(TestCase):
    """Superadmin jurnalidagi harakatlar: hammasi saqlanadi, 100 tadan ko'rinadi."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.other = Branch.objects.create(name='Two', slug='two')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=45000)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def stamp(self, event, day, hour=12):
        """auto_now_add'ni chetlab o'tib, yozuvga aniq sana qo'yadi."""
        AuditEvent.objects.filter(pk=event.pk).update(
            created_at=timezone.make_aware(datetime.combine(day, time(hour, 0))))

    def test_ten_thousand_events_are_all_kept_and_served_hundred_per_page(self):
        AuditEvent.objects.bulk_create([
            AuditEvent(branch=self.branch, actor=self.owner, action='order.create', description=f'#{index}')
            for index in range(250)
        ])
        first = self.client.get('/api/v1/audit/').data
        self.assertEqual(first['count'], 250)
        self.assertEqual(first['pages'], 3)
        self.assertEqual(first['page_size'], 100)
        self.assertEqual(len(first['results']), 100)
        self.assertEqual(len(self.client.get('/api/v1/audit/?page=3').data['results']), 50)

        seen = set()
        for page in (1, 2, 3):
            seen.update(row['id'] for row in self.client.get(f'/api/v1/audit/?page={page}').data['results'])
        # Hech bir yozuv tushib qolmaydi va takrorlanmaydi.
        self.assertEqual(seen, set(AuditEvent.objects.values_list('id', flat=True)))
        # Chegaradan tashqari sahifa so'ralsa, oxirgi sahifa qaytadi.
        self.assertEqual(self.client.get('/api/v1/audit/?page=99').data['page'], 3)

    def test_day_and_action_filters_narrow_the_log(self):
        today = timezone.localdate()
        yesterday = today - timedelta(days=1)
        self.stamp(AuditEvent.objects.create(branch=self.branch, actor=self.owner, action='order.pay', description='bugun'), today)
        self.stamp(AuditEvent.objects.create(branch=self.branch, actor=self.cashier, action='order.create', description='kecha'), yesterday)
        self.stamp(AuditEvent.objects.create(branch=self.branch, actor=self.owner, action='stock.receipt', description='kecha kirim'), yesterday)
        stranger = User.objects.create_user('stranger', password='test-only-long-password', role='owner', branch=self.other)
        AuditEvent.objects.create(branch=self.other, actor=stranger, action='order.pay', description='boshqa filial')

        today_only = self.client.get(f'/api/v1/audit/?start={today}&end={today}').data
        self.assertEqual([row['description'] for row in today_only['results']], ['bugun'])

        by_action = self.client.get(f'/api/v1/audit/?start={yesterday}&end={today}&action=order.create').data
        self.assertEqual([row['description'] for row in by_action['results']], ['kecha'])
        # Harakat turlari ro'yxati tanlovdan qisqarmaydi, aks holda filtrni qaytarib bo'lmasdi.
        self.assertEqual({item['action'] for item in by_action['actions']}, {'order.pay', 'order.create', 'stock.receipt'})
        self.assertEqual(by_action['total'], 3)

        by_actor = self.client.get(f'/api/v1/audit/?actor={self.cashier.id}').data
        self.assertEqual([row['actor'] for row in by_actor['results']], ['cashier'])
        # Boshqa filial jurnalga umuman tushmaydi.
        self.assertEqual(self.client.get('/api/v1/audit/').data['count'], 3)

    def test_rows_carry_readable_label_and_group(self):
        AuditEvent.objects.create(branch=self.branch, actor=self.owner, action='stock.receipt', description='Guruch')
        row = self.client.get('/api/v1/audit/').data['results'][0]
        self.assertEqual(row['label'], 'Omborga kirim')
        self.assertEqual(row['group'], 'Ombor')
        self.assertEqual(row['actor'], 'owner')

    def test_ingredient_and_stock_moves_record_what_and_how_much(self):
        created = self.client.post('/api/v1/ingredients/', {'name': 'Guruch', 'unit': 'kg', 'quantity': '10', 'minimum': '2'}, format='json')
        self.assertEqual(created.status_code, 201)
        entry = AuditEvent.objects.get(action='stock.ingredient')
        self.assertIn('Guruch', entry.description)
        self.assertIn('eng kam qoldiq 2 kg', entry.description)

        self.client.post('/api/v1/stock/', {
            'key': str(uuid4()), 'ingredient': created.data['id'], 'kind': 'receipt',
            'quantity': '20', 'date': str(timezone.localdate()), 'note': 'Bozordan',
        }, format='json')
        receipt = AuditEvent.objects.get(action='stock.receipt')
        # Miqdor ham, yangi qoldiq ham ko'rinib turishi kerak.
        self.assertIn('+20 kg', receipt.description)
        self.assertIn('qoldiq 20 kg', receipt.description)

    def test_sale_consumption_names_every_ingredient_and_amount(self):
        rice = Ingredient.objects.create(branch=self.branch, name='Guruch', unit='kg', quantity=50)
        oil = Ingredient.objects.create(branch=self.branch, name='Yog', unit='l', quantity=20)
        recipe = Recipe.objects.create(branch=self.branch, dish=self.dish, name='Osh', yield_quantity=Decimal('10'))
        RecipeLine.objects.create(recipe=recipe, ingredient=rice, quantity=Decimal('2'), batch_cost=Decimal('20000'))
        RecipeLine.objects.create(recipe=recipe, ingredient=oil, quantity=Decimal('1'), batch_cost=Decimal('15000'))

        create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': self.dish.id, 'quantity': 5, 'note': ''}],
        })
        rows = sorted(AuditEvent.objects.filter(action='stock.sale_consumption').values_list('description', flat=True))
        # Har bir masalliq alohida qatorda: qaysi buyurtma, nima va qancha.
        self.assertEqual(len(rows), 2)
        self.assertTrue(any('Guruch' in row and '-1 kg' in row for row in rows), rows)
        self.assertTrue(any('Yog' in row and '-0.5 l' in row for row in rows), rows)

    def test_tables_reprint_and_sessions_all_reach_the_log(self):
        table = self.client.post('/api/v1/tables/', {'number': 7, 'name': '', 'seats': 4, 'zone': 'hall_left', 'seating': 'divan'}, format='json').data
        self.client.patch(f'/api/v1/tables/{table["id"]}/', {'seats': 6}, format='json')
        self.client.delete(f'/api/v1/tables/{table["id"]}/')
        self.assertEqual(
            list(AuditEvent.objects.filter(action__startswith='table.').order_by('id').values_list('action', flat=True)),
            ['table.create', 'table.update', 'table.remove'],
        )

        guest = APIClient()
        guest.post('/api/v1/auth/login/', {'username': 'cashier', 'password': 'test-only-long-password'}, format='json')
        guest.post('/api/v1/auth/logout/', {}, format='json')
        self.assertTrue(AuditEvent.objects.filter(action='auth.login', actor=self.cashier).exists())
        self.assertTrue(AuditEvent.objects.filter(action='auth.logout', actor=self.cashier).exists())

    def test_only_owner_reads_the_activity_log(self):
        for role in ('cashier', 'kitchen'):
            user = User.objects.create_user(f'{role}-2', password='test-only-long-password', role=role, branch=self.branch)
            client = APIClient()
            client.force_authenticate(user)
            self.assertEqual(client.get('/api/v1/audit/').status_code, 403)
        self.assertEqual(APIClient().get('/api/v1/audit/').status_code, 403)


class StockCostingTests(TestCase):
    """Ombor tannarxi: kirimda narx kiritiladi, sarf o'sha narxda baholanadi."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=45000)
        self.rice = Ingredient.objects.create(branch=self.branch, name='Guruch', unit='kg')
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def receipt(self, quantity, cost):
        return move_stock(self.owner, {
            'key': uuid4(), 'ingredient': self.rice.id, 'kind': 'receipt',
            'quantity': Decimal(quantity), 'cost_total': Decimal(cost),
            'date': timezone.localdate(), 'note': 'Bozordan',
        })

    def test_two_receipts_average_out_and_consumption_is_valued_at_that_price(self):
        self.receipt('10', '100000')
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.unit_cost, Decimal('10000.0000'))

        # Ikkinchi partiya qimmatroq: o'rtacha tortilgan narx ikkovining orasida.
        self.receipt('10', '200000')
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.unit_cost, Decimal('15000.0000'))
        self.assertEqual(self.rice.stock_value, Decimal('300000.00'))

        used = move_stock(self.owner, {
            'key': uuid4(), 'ingredient': self.rice.id, 'kind': 'consumption',
            'quantity': Decimal('5'), 'date': timezone.localdate(), 'note': 'Kunlik sarf',
        })
        # Sarf o'rtacha tannarxda baholanadi va narx o'zgarmaydi.
        self.assertEqual(used.cost_total, Decimal('75000.00'))
        self.assertEqual(used.unit_cost, Decimal('15000.0000'))
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.unit_cost, Decimal('15000.0000'))
        self.assertEqual(self.rice.quantity, Decimal('15.000'))

    def test_receipt_without_price_keeps_the_old_cost(self):
        self.receipt('10', '100000')
        self.receipt('10', '0')
        self.rice.refresh_from_db()
        # Narxsiz kirim o'rtachani nolga tortib tushirmaydi.
        self.assertEqual(self.rice.unit_cost, Decimal('10000.0000'))

    def test_price_is_rejected_on_consumption(self):
        self.receipt('10', '100000')
        response = self.client.post('/api/v1/stock/', {
            'key': str(uuid4()), 'ingredient': self.rice.id, 'kind': 'consumption',
            'quantity': '1', 'cost_total': '5000', 'date': str(timezone.localdate()), 'note': 'x',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_sale_consumption_freezes_the_cost_of_the_day(self):
        self.receipt('10', '100000')
        recipe = Recipe.objects.create(branch=self.branch, dish=self.dish, name='Osh', yield_quantity=Decimal('10'))
        RecipeLine.objects.create(recipe=recipe, ingredient=self.rice, quantity=Decimal('2'), batch_cost=Decimal('20000'))

        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': self.dish.id, 'quantity': 5, 'note': ''}],
        })
        movement = StockMovement.objects.get(kind='sale_consumption')
        # 5 porsiya uchun 1 kg guruch, kilosi 10 000 so'm.
        self.assertEqual(movement.quantity, Decimal('1.000'))
        self.assertEqual(movement.cost_total, Decimal('10000.00'))

        # Narx keyin oshsa ham eski harakat o'zgarmaydi.
        self.receipt('10', '300000')
        movement.refresh_from_db()
        self.assertEqual(movement.cost_total, Decimal('10000.00'))
        self.assertEqual(order.status, 'paid')


class PayrollTests(TestCase):
    """Ish haqi: kunlik yig'iladi, istalgan kuni beriladi.

    Butun bo'lim bitta tenglamaga tayanadi:
        balans = kelgan kunlar uchun yozilgan haq − berilgan pul
    Shu tenglama buzilmasligi shu yerda tekshiriladi.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.other = Branch.objects.create(name='Two', slug='two')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user(
            'cashier', password='test-only-long-password', role='cashier', branch=self.branch,
            first_name='Kassir', daily_wage=Decimal('150000'))
        self.cook = User.objects.create_user(
            'oshpaz', password='test-only-long-password', role='kitchen', branch=self.branch,
            first_name='Oshpaz', daily_wage=Decimal('200000'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.today = timezone.localdate()
        # Yakshanbaga haq yozilmaydi, shuning uchun sinov ish kunida
        # o'tkaziladi: bugun yakshanba bo'lsa shanbaga suriladi.
        self.workday = self.today - timedelta(days=1) if self.today.weekday() == 6 else self.today
        # Oldingi ish kuni. Shunchaki «bir kun oldin» deb bo'lmaydi:
        # dushanba kuni u yakshanbaga tushadi va davomat qabul qilinmaydi —
        # sinov haftaning qaysi kuni yurishiga bog'liq bo'lib qolardi.
        earlier = self.workday - timedelta(days=1)
        self.earlier = earlier - timedelta(days=1) if earlier.weekday() == 6 else earlier
        # Eng yaqin yakshanba — dam olish kuni qoidasini sinash uchun.
        self.sunday = self.today - timedelta(days=(self.today.weekday() + 1) % 7)

    def mark(self, rows, day=None, client=None):
        return (client or self.client).post('/api/v1/attendance/', {
            'date': str(day or self.workday),
            'rows': [{'employee': person.id, 'present': present} for person, present in rows],
        }, format='json')

    def pay(self, employee, amount, method='cash', key=None, day=None, client=None):
        return (client or self.client).post(f'/api/v1/staff/{employee.id}/salary-payments/', {
            'key': str(key or uuid4()),
            'amount': str(amount),
            'payment_method': method,
            'paid_on': str(day or self.today),
            'note': '',
        }, format='json')

    def rows(self, client=None):
        data = (client or self.client).get('/api/v1/payroll/').data
        return data, {row['username']: row for row in data['employees']}

    def test_nothing_is_owed_before_anyone_is_marked(self):
        data, rows = self.rows()
        self.assertEqual(data['summary']['balance'], '0.00')
        self.assertEqual(data['summary']['staff_count'], 2)
        self.assertEqual(data['summary']['unmarked_today'], 2 if not data['rest_day'] else 2)
        self.assertEqual(rows['cashier']['balance'], '0.00')
        self.assertEqual(rows['cashier']['daily_wage'], '150000.00')
        # Olti kunlik hafta: kunlik haq olti barobar.
        self.assertEqual(rows['cashier']['week_wage'], '900000.00')
        # Superadmin o'z haqini bu bo'limda yuritmaydi.
        self.assertNotIn('owner', rows)

    def test_a_marked_day_adds_that_days_wage_to_the_balance(self):
        self.assertEqual(self.mark([(self.cashier, True), (self.cook, True)]).status_code, 201)
        data, rows = self.rows()
        self.assertEqual(rows['cashier']['balance'], '150000.00')
        self.assertEqual(rows['oshpaz']['balance'], '200000.00')
        self.assertEqual(rows['cashier']['days_worked'], 1)
        self.assertEqual(data['summary']['balance'], '350000.00')
        self.assertEqual(data['summary']['earned'], '350000.00')

    def test_a_day_off_adds_nothing(self):
        self.mark([(self.cashier, False), (self.cook, True)])
        _data, rows = self.rows()
        self.assertEqual(rows['cashier']['balance'], '0.00')
        self.assertEqual(rows['cashier']['days_worked'], 0)
        # Belgilangan, lekin kelmagan: «so'ralmagan» emas, «kelmadi».
        self.assertEqual(rows['cashier']['today'] or 'absent', 'absent')
        self.assertEqual(rows['oshpaz']['balance'], '200000.00')

    def test_marking_the_same_day_twice_corrects_it_instead_of_doubling(self):
        self.mark([(self.cashier, True)])
        self.mark([(self.cashier, True)])
        _data, rows = self.rows()
        self.assertEqual(rows['cashier']['balance'], '150000.00')
        # Xato tuzatiladi: kelgan deb belgilangan kun kelmaganga o'tkazilsa
        # o'sha kunning haqi balansdan ham chiqib ketadi.
        self.mark([(self.cashier, False)])
        _data, rows = self.rows()
        self.assertEqual(rows['cashier']['balance'], '0.00')

    def test_sunday_is_a_rest_day_and_earns_nothing(self):
        response = self.mark([(self.cashier, True)], day=self.sunday)
        self.assertEqual(response.status_code, 400)
        self.assertIn('akshanba', str(response.data))
        self.assertEqual(self.rows()[1]['cashier']['balance'], '0.00')

    def test_a_raise_never_rewrites_the_days_already_worked(self):
        self.mark([(self.cashier, True)])
        self.assertEqual(self.client.patch(
            f'/api/v1/staff/{self.cashier.id}/', {'daily_wage': '300000'}, format='json').status_code, 200)
        _data, rows = self.rows()
        # O'tgan kun eski kelishuv bilan qoladi, yangi kunlar yangisi bilan.
        self.assertEqual(rows['cashier']['balance'], '150000.00')
        self.assertEqual(rows['cashier']['daily_wage'], '300000.00')
        self.mark([(self.cashier, True)], day=self.earlier)
        self.assertEqual(self.rows()[1]['cashier']['balance'], '450000.00')

    def test_money_paid_comes_off_the_balance(self):
        self.mark([(self.cashier, True)])
        self.assertEqual(self.pay(self.cashier, Decimal('100000')).status_code, 201)
        _data, rows = self.rows()
        self.assertEqual(rows['cashier']['earned'], '150000.00')
        self.assertEqual(rows['cashier']['paid'], '100000.00')
        self.assertEqual(rows['cashier']['balance'], '50000.00')
        self.assertFalse(rows['cashier']['advance'])

    def test_paying_before_the_work_is_an_advance(self):
        # Pul zarur bo'lsa oldinroq beriladi: balans manfiyga tushadi va
        # keyingi ish kunlari bilan o'zi yopiladi.
        self.pay(self.cashier, Decimal('150000'))
        _data, rows = self.rows()
        self.assertEqual(rows['cashier']['balance'], '-150000.00')
        self.assertTrue(rows['cashier']['advance'])
        self.mark([(self.cashier, True)])
        self.assertEqual(self.rows()[1]['cashier']['balance'], '0.00')

    def test_the_same_key_never_pays_twice(self):
        key = uuid4()
        self.assertEqual(self.pay(self.cashier, Decimal('100000'), key=key).status_code, 201)
        # Ikkinchi marta bosilgan tugma yangi pul bermaydi.
        self.assertEqual(self.pay(self.cashier, Decimal('100000'), key=key).status_code, 200)
        self.assertEqual(SalaryPayment.objects.filter(employee=self.cashier).count(), 1)
        self.assertEqual(self.rows()[1]['cashier']['paid'], '100000.00')
        # Bir xil kalit boshqa summa bilan kelsa — bu xato, qabul qilinmaydi.
        self.assertEqual(self.pay(self.cashier, Decimal('200000'), key=key).status_code, 409)

    def test_a_payment_lands_in_expenses_exactly_once(self):
        self.pay(self.cashier, Decimal('120000'))
        expenses = Expense.objects.filter(branch=self.branch, category='Ish haqi')
        self.assertEqual(expenses.count(), 1)
        self.assertEqual(expenses.first().amount, Decimal('120000'))
        self.assertEqual(expenses.first().recipient, 'Kassir')
        # Moliyada oylik xarajatlar ICHIDA turadi, ustiga qo'shilmaydi.
        finance = self.client.get('/api/v1/finance/').data
        self.assertEqual(finance['salary']['total'], '120000.00')
        self.assertEqual(finance['profit']['expenses'], '120000.00')

    def test_several_payments_in_one_month_are_all_kept(self):
        # Eski tizimda bir oyga bitta to'lov sig'ardi. Endi hafta oxirida
        # ham, o'rtasida ham berish mumkin.
        self.pay(self.cashier, Decimal('100000'))
        self.pay(self.cashier, Decimal('50000'))
        data, rows = self.rows()
        self.assertEqual(rows['cashier']['paid'], '150000.00')
        self.assertEqual(rows['cashier']['payments'], 2)
        self.assertEqual(data['summary']['month_count'], 2)
        self.assertEqual(data['all_time'], {'total': '150000.00', 'payments': 2})

    def test_the_cashier_marks_attendance_and_pays_too(self):
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        self.assertEqual(self.mark([(self.cook, True)], client=cashier).status_code, 201)
        self.assertEqual(self.pay(self.cook, Decimal('50000'), client=cashier).status_code, 201)
        _data, rows = self.rows(client=cashier)
        self.assertEqual(rows['oshpaz']['balance'], '150000.00')

    def test_the_kitchen_reaches_none_of_it(self):
        kitchen = APIClient()
        kitchen.force_authenticate(self.cook)
        self.assertEqual(kitchen.get('/api/v1/payroll/').status_code, 403)
        self.assertEqual(self.mark([(self.cashier, True)], client=kitchen).status_code, 403)
        self.assertEqual(self.pay(self.cashier, Decimal('10000'), client=kitchen).status_code, 403)

    def test_other_branches_stay_out(self):
        stranger = User.objects.create_user(
            'stranger', password='test-only-long-password', role='cashier',
            branch=self.other, daily_wage=Decimal('700000'))
        self.assertNotIn('stranger', self.rows()[1])
        # Begona xodimni belgilab ham bo'lmaydi.
        self.assertEqual(self.mark([(stranger, True)]).status_code, 400)

    def test_future_and_forgotten_days_are_refused(self):
        self.assertEqual(self.mark([(self.cashier, True)], day=self.today + timedelta(days=1)).status_code, 400)
        self.assertEqual(self.mark([(self.cashier, True)], day=self.today - timedelta(days=40)).status_code, 400)
        self.assertEqual(self.pay(self.cashier, Decimal('1000'), day=self.today + timedelta(days=1)).status_code, 400)
        self.assertEqual(self.pay(self.cashier, Decimal('0')).status_code, 400)

    def test_the_week_shows_six_working_days_and_one_rest_day(self):
        data = self.client.get('/api/v1/payroll/').data
        self.assertEqual(len(data['week']['days']), 7)
        self.assertEqual(sum(1 for day in data['week']['days'] if day['rest']), 1)
        self.assertEqual(data['summary']['work_days'], 6)
        # Har bir xodimning hafta qatori ham yetti kun.
        self.assertEqual(len(data['employees'][0]['week']), 7)

    def test_the_week_total_follows_the_days_actually_marked(self):
        self.mark([(self.cashier, True), (self.cook, True)])
        data, rows = self.rows()
        self.assertEqual(rows['cashier']['week_days'], 1)
        self.assertEqual(rows['cashier']['week_earned'], '150000.00')
        self.assertEqual(data['summary']['week_earned'], '350000.00')
        # To'liq hafta olti kun bo'lardi.
        self.assertEqual(data['summary']['week_wage'], '2100000.00')

    def test_the_marking_is_written_into_the_audit_log(self):
        self.mark([(self.cashier, True), (self.cook, False)])
        entry = AuditEvent.objects.filter(action='attendance.mark').first()
        self.assertIsNotNone(entry)
        self.assertIn('1 keldi', entry.description)
        self.assertIn('1 kelmadi', entry.description)

    def test_a_broken_month_filter_is_refused(self):
        future = (self.today.replace(day=28) + timedelta(days=10)).replace(day=1)
        self.assertEqual(self.client.get(f'/api/v1/payroll/?month={future:%Y-%m}').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/payroll/?month=2026-13').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/payroll/?month=sentabr').status_code, 400)


class StockUsageTests(TestCase):
    """Masalliqlar sarfi: qoldiq qayta tiklanadi, jamlar bo'linib ketmaydi."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.rice = Ingredient.objects.create(branch=self.branch, name='Guruch', unit='kg')
        self.oil = Ingredient.objects.create(branch=self.branch, name='Yog', unit='l')
        self.idle = Ingredient.objects.create(branch=self.branch, name='Ziravor', unit='kg', quantity=Decimal('5'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.today = timezone.localdate()

    def move(self, ingredient, kind, amount, cost='0', day=None):
        """Harakat yozadi; sana majburan qo'yiladi, chunki serializer faqat bugunni oladi."""
        data = {
            'key': uuid4(), 'ingredient': ingredient.id, 'kind': kind,
            'quantity': Decimal(amount), 'cost_total': Decimal(cost),
            'date': self.today, 'note': 'sinov',
        }
        movement = move_stock(self.owner, data)
        if day and day != self.today:
            StockMovement.objects.filter(pk=movement.pk).update(date=day)
        return movement

    def usage(self, query=''):
        return self.client.get(f'/api/v1/stock/usage/{query}').data

    def test_opening_and_closing_balances_are_rebuilt_from_movements(self):
        yesterday = self.today - timedelta(days=1)
        self.move(self.rice, 'receipt', '100', '1000000', day=yesterday)
        self.move(self.rice, 'consumption', '30', day=self.today)

        data = self.usage(f'?start={self.today}&end={self.today}')
        row = next(item for item in data['ingredients'] if item['name'] == 'Guruch')
        # Bugun: 70 kg bilan ochildi, 30 kg ketdi, 70 kg qoldi.
        self.assertEqual(row['opening'], '100.000')
        self.assertEqual(row['used'], '30.000')
        self.assertEqual(row['closing'], '70.000')
        self.assertEqual(row['received'], '0.000')

        # Kechagi kunni so'rasak, ochilish nolga qaytadi.
        earlier = self.usage(f'?start={yesterday}&end={yesterday}')
        row = next(item for item in earlier['ingredients'] if item['name'] == 'Guruch')
        self.assertEqual(row['opening'], '0.000')
        self.assertEqual(row['received'], '100.000')
        self.assertEqual(row['closing'], '100.000')

    def test_money_follows_the_frozen_cost_of_each_movement(self):
        self.move(self.rice, 'receipt', '100', '1000000')
        self.move(self.rice, 'consumption', '30')
        data = self.usage()
        row = next(item for item in data['ingredients'] if item['name'] == 'Guruch')
        # Kilosi 10 000 so'm, 30 kg ketdi. Bu hisobotda narx tiyingacha
        # ko'rsatiladi; bazada aniqlik uchun to'rt kasr saqlanadi.
        self.assertEqual(row['unit_cost'], '10000.00')
        self.assertEqual(row['used_value'], '300000.00')
        self.assertEqual(row['received_value'], '1000000.00')
        self.assertEqual(row['stock_value'], '700000.00')
        self.assertEqual(data['summary']['used_value'], '300000.00')
        self.assertEqual(data['summary']['received_value'], '1000000.00')

    def test_unpriced_movements_are_counted_not_hidden(self):
        # Narxsiz kirim: eski ma'lumot shunday, buni yashirmaslik kerak.
        self.move(self.rice, 'receipt', '50')
        self.move(self.rice, 'consumption', '10')
        data = self.usage()
        self.assertEqual(data['summary']['moves'], 2)
        self.assertEqual(data['summary']['unpriced_moves'], 2)
        self.assertEqual(data['summary']['used_value'], '0.00')

    def test_sale_and_manual_consumption_are_told_apart(self):
        self.move(self.rice, 'receipt', '100', '1000000')
        self.move(self.rice, 'consumption', '10')
        StockMovement.objects.create(
            branch=self.branch, ingredient=self.rice, actor=self.owner, key=uuid4(), request_hash='x',
            kind='sale_consumption', quantity=Decimal('5'), unit_cost=Decimal('10000'), cost_total=Decimal('50000'),
            date=self.today, note='#1 buyurtma',
        )
        row = next(item for item in self.usage()['ingredients'] if item['name'] == 'Guruch')
        self.assertEqual(row['manual'], '10.000')
        self.assertEqual(row['sold'], '5.000')
        self.assertEqual(row['used'], '15.000')
        self.assertEqual(row['sold_value'], '50000.00')

    def test_idle_ingredients_are_listed_separately(self):
        self.move(self.rice, 'receipt', '100', '1000000')
        data = self.usage()
        moved = [item['name'] for item in data['ingredients']]
        idle = [item['name'] for item in data['idle']]
        self.assertEqual(moved, ['Guruch'])
        # Harakatsiz mahsulotlar alohida ro'yxatda — e'tibordan chetda qolmasin.
        self.assertEqual(sorted(idle), ['Yog', 'Ziravor'])
        self.assertEqual(data['summary']['items_moved'], 1)
        self.assertEqual(data['summary']['items_idle'], 2)

    def test_daily_series_fills_quiet_days_and_monthly_grouping_switches(self):
        self.move(self.rice, 'receipt', '100', '1000000')
        week = self.today - timedelta(days=6)
        data = self.usage(f'?start={week}&end={self.today}')
        self.assertEqual(data['filters']['group'], 'day')
        self.assertEqual(len(data['series']), 7)
        # Bu davrda faqat guruch harakat qilgan — birlik yagona, shuning uchun
        # miqdor jamlanadi.
        self.assertEqual(data['summary']['unit'], 'kg')
        self.assertEqual(sum(1 for row in data['series'] if row['received'] == '0.000'), 6)

        # Litrdagi mahsulot qo'shilsa, birliklar aralashadi va miqdor jamlanmaydi.
        self.move(self.oil, 'receipt', '50', '500000')
        mixed = self.usage(f'?start={week}&end={self.today}')
        self.assertEqual(mixed['summary']['unit'], '')
        self.assertEqual(mixed['summary']['used'], '')
        self.assertEqual({row['received'] for row in mixed['series']}, {''})
        # Pul esa har doim jamlanadi.
        self.assertEqual(mixed['summary']['received_value'], '1500000.00')

        # Uzun oraliq avtomatik oylik guruhga o'tadi.
        far = self.today - timedelta(days=100)
        monthly = self.usage(f'?start={far}&end={self.today}')
        self.assertEqual(monthly['filters']['group'], 'month')
        self.assertLessEqual(len(monthly['series']), 5)

    def test_days_left_and_share_help_planning(self):
        self.move(self.rice, 'receipt', '100', '1000000')
        self.move(self.rice, 'consumption', '20')
        self.move(self.oil, 'receipt', '50', '500000')
        self.move(self.oil, 'consumption', '5')
        data = self.usage(f'?start={self.today}&end={self.today}')
        rows = {item['name']: item for item in data['ingredients']}
        # Kuniga 20 kg ketyapti, 80 kg qolgan -> 4 kunga yetadi.
        self.assertEqual(rows['Guruch']['per_day'], '20.000')
        self.assertEqual(rows['Guruch']['days_left'], '4')
        # 25 birlik chiqimning 20 tasi guruch.
        self.assertEqual(rows['Guruch']['share'], '80.00')
        self.assertEqual(rows['Yog']['share'], '20.00')
        # Eng ko'p pul ketgani birinchi turadi.
        self.assertEqual(data['ingredients'][0]['name'], 'Guruch')

    def test_filters_are_validated_and_cashier_is_refused(self):
        self.assertEqual(self.client.get(f'/api/v1/stock/usage/?start={self.today}&end={self.today - timedelta(days=1)}').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/stock/usage/?ingredient=999999').status_code, 400)
        cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        client = APIClient()
        client.force_authenticate(cashier)
        self.assertEqual(client.get('/api/v1/stock/usage/').status_code, 403)


class FinanceTests(TestCase):
    """Umumiy moliya: raqamlar ikki marta sanalmasin va zanjir yopilsin."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch, daily_wage=Decimal('120000'), first_name='Kassir')
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.osh = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.choy = Dish.objects.create(branch=self.branch, category=self.category, name='Choy', price=Decimal('10000'))
        self.rice = Ingredient.objects.create(branch=self.branch, name='Guruch', unit='kg')
        # Faqat oshning retsepti bor — choy tannarxsiz sotiladi.
        recipe = Recipe.objects.create(branch=self.branch, dish=self.osh, name='Osh', yield_quantity=Decimal('10'))
        RecipeLine.objects.create(recipe=recipe, ingredient=self.rice, quantity=Decimal('2'), batch_cost=Decimal('100000'))
        move_stock(self.owner, {
            'key': uuid4(), 'ingredient': self.rice.id, 'kind': 'receipt',
            'quantity': Decimal('100'), 'cost_total': Decimal('500000'),
            'date': timezone.localdate(), 'note': 'Bozordan',
        })
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def sell(self, dish, quantity, method='cash'):
        return create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': method,
            'lines': [{'dish': dish.id, 'quantity': quantity, 'note': ''}],
        })

    def finance(self, query=''):
        return self.client.get(f'/api/v1/finance/{query}').data

    def test_profit_chain_adds_up_from_revenue_to_net(self):
        self.sell(self.osh, 10)     # 500 000, tannarx 10 * 10 000 = 100 000
        self.sell(self.choy, 5)     # 50 000, tannarxsiz
        self.client.post('/api/v1/expenses/', {
            'key': str(uuid4()), 'category': 'Ijara', 'purpose': 'Sentabr ijarasi',
            'recipient': '', 'amount': '200000', 'payment_method': 'cash', 'date': str(timezone.localdate()),
        }, format='json')

        p = self.finance()['profit']
        self.assertEqual(p['revenue'], '550000.00')
        # Tannarx ombor narxidan kelib chiqadi: 100 kg 500 000 so'mga olingan,
        # ya'ni 5 000 so'm/kg; 10 porsiya uchun 2 kg -> 10 000 so'm.
        self.assertEqual(p['cogs'], '10000.00')
        self.assertEqual(p['gross_profit'], '540000.00')
        self.assertEqual(p['expenses'], '200000.00')
        self.assertEqual(p['net_profit'], '340000.00')
        self.assertEqual(p['orders'], 2)
        # Zanjir arifmetikasi hech qayerda uzilmasligi kerak.
        self.assertEqual(
            Decimal(p['revenue']) - Decimal(p['cogs']) - Decimal(p['expenses']),
            Decimal(p['net_profit']),
        )

    def test_cost_coverage_exposes_the_fake_margin(self):
        self.sell(self.osh, 10)
        self.sell(self.choy, 5)
        data = self.finance()
        # Umumiy marja 98.2% ko'rinadi, lekin tannarx tushumning 91% ini qamragan.
        self.assertEqual(data['profit']['gross_margin'], '98.18')
        coverage = data['coverage']
        self.assertEqual(coverage['covered_revenue'], '500000.00')
        self.assertEqual(coverage['share'], '90.91')
        # Retsepti bor taomlar bo'yicha marja — faqat shu raqamga ishonish mumkin.
        self.assertEqual(coverage['covered_margin'], '98.00')
        self.assertEqual(coverage['dishes_total'], 2)
        self.assertEqual(coverage['dishes_with_recipe'], 1)
        self.assertEqual([row['dish'] for row in coverage['top_uncovered']], ['Choy'])

    def test_salary_sits_inside_expenses_and_is_never_added_twice(self):
        self.sell(self.osh, 10)
        self.assertEqual(self.client.post(f'/api/v1/staff/{self.cashier.id}/salary-payments/', {
            'key': str(uuid4()), 'amount': '3000000',
            'payment_method': 'cash', 'paid_on': str(timezone.localdate()), 'note': '',
        }, format='json').status_code, 201)

        data = self.finance()
        # Oylik xarajatlar ichida — jami xarajat aynan oylikning o'zi.
        self.assertEqual(data['profit']['expenses'], '3000000.00')
        self.assertEqual(data['salary']['total'], '3000000.00')
        self.assertEqual(data['salary']['share'], '100.00')
        categories = {row['category']: row for row in data['expenses']}
        self.assertEqual(categories['Ish haqi']['amount'], '3000000.00')
        self.assertTrue(categories['Ish haqi']['salary'])
        # Sof foyda oylikni bir marta ayiradi, ikki marta emas.
        self.assertEqual(data['profit']['net_profit'], '-2510000.00')

    def test_stock_purchase_hits_cash_but_not_profit(self):
        self.sell(self.osh, 10)
        data = self.finance()
        # Ombor xaridi 500 000 so'm edi: foydadan ayirilmaydi.
        self.assertEqual(data['profit']['expenses'], '0.00')
        self.assertEqual(data['stock']['purchases'], '500000.00')
        self.assertEqual(data['cash']['stock_purchases'], '500000.00')
        self.assertEqual(data['cash']['out'], '500000.00')
        self.assertEqual(data['cash']['in'], '500000.00')
        self.assertEqual(data['cash']['net'], '0.00')
        # Sotilgan qismi tannarx bo'lib foydaga kiradi.
        self.assertEqual(data['profit']['cogs'], '10000.00')
        self.assertEqual(data['stock']['consumed'], '10000.00')
        # Retsept narxi ham, ombor narxi ham bitta manbadan — masalliq
        # narxidan — kelgani uchun farq qolmaydi.
        self.assertEqual(data['stock']['gap'], '0.00')
        self.assertEqual(data['stock']['gap_share'], '0.00')

    def test_cash_and_profit_are_reconciled_by_the_bridge(self):
        self.sell(self.osh, 10)
        self.client.post('/api/v1/expenses/', {
            'key': str(uuid4()), 'category': 'Ijara', 'purpose': 'Ijara',
            'recipient': '', 'amount': '150000', 'payment_method': 'unpaid', 'date': str(timezone.localdate()),
        }, format='json')
        data = self.finance()
        # sof_pul = sof_foyda + tannarx + to'lanmagan − ombor xaridi
        self.assertEqual(data['cash']['bridge'], data['cash']['net'])
        self.assertEqual(data['cash']['unpaid'], '150000.00')
        self.assertEqual(data['cash']['settled_expenses'], '0.00')

    def test_month_filter_trend_and_payment_methods(self):
        self.sell(self.osh, 10, method='cash')
        self.sell(self.choy, 5, method='click')
        month = timezone.localdate().strftime('%Y-%m')
        data = self.finance(f'?month={month}')
        self.assertEqual(data['filters']['month'], month)
        methods = {row['method']: row for row in data['methods']}
        self.assertEqual(methods['cash']['revenue'], '500000.00')
        self.assertEqual(methods['click']['revenue'], '50000.00')
        self.assertEqual(methods['click']['share'], '9.09')

        self.assertEqual(len(data['trend']), 12)
        point = next(row for row in data['trend'] if row['period'] == month)
        self.assertEqual(point['revenue'], '550000.00')
        self.assertEqual(point['net_profit'], '540000.00')
        self.assertIn(month, data['months'])

    def test_manual_salary_row_never_counts_as_a_real_salary_payment(self):
        self.sell(self.osh, 10)
        # Haqiqiy oylik to'lovi: bog'langan Expense yaratadi.
        self.assertEqual(self.client.post(f'/api/v1/staff/{self.cashier.id}/salary-payments/', {
            'key': str(uuid4()), 'amount': '3000000',
            'payment_method': 'cash', 'paid_on': str(timezone.localdate()), 'note': '',
        }, format='json').status_code, 201)
        # Qo'lda «Ish haqi» deb yozilgan xarajat: kategoriya erkin matn bo'lgani uchun
        # eski usul buni ham oylik deb sanardi.
        self.client.post('/api/v1/expenses/', {
            'key': str(uuid4()), 'category': 'Ish haqi', 'purpose': 'Avans',
            'recipient': 'Kassir', 'amount': '500000', 'payment_method': 'cash',
            'date': str(timezone.localdate()),
        }, format='json')

        data = self.finance()
        # Oylik ulushi faqat bog'langan to'lov: 3 000 000, 3 500 000 emas.
        self.assertEqual(data['salary']['total'], '3000000.00')
        self.assertEqual(data['salary']['payments'], 1)
        # Qo'lda yozilgani ogohlantirish sifatida alohida ko'rinadi.
        self.assertEqual(data['salary']['manual_total'], '500000.00')
        self.assertEqual(data['salary']['manual_count'], 1)
        # Ikkalasi ham xarajatlar ichida — jami 3 500 000.
        self.assertEqual(data['profit']['expenses'], '3500000.00')

    def test_waste_is_its_own_profit_line_and_the_bridge_still_closes(self):
        self.sell(self.osh, 10)
        # Qo'lda sarf: sotuvda ayrilmagan, xarajat yozuvi ham yo'q, lekin yo'qotish.
        move_stock(self.owner, {
            'key': uuid4(), 'ingredient': self.rice.id, 'kind': 'consumption',
            'quantity': Decimal('4'), 'date': timezone.localdate(), 'note': 'Buzilib qoldi',
        })
        data = self.finance()
        # 4 kg × 5 000 so'm = 20 000 so'm isrof.
        self.assertEqual(data['profit']['waste'], '20000.00')
        # Sof foyda = 500 000 − 10 000 − 0 − 20 000
        self.assertEqual(data['profit']['net_profit'], '470000.00')
        # Isrof pul chiqimi emas: pul allaqachon ombor xaridida chiqqan.
        self.assertEqual(data['cash']['out'], '500000.00')
        self.assertEqual(data['cash']['bridge'], data['cash']['net'])

    def test_coverage_counts_dishes_without_double_counting(self):
        self.sell(self.osh, 10)
        self.sell(self.choy, 5)
        # Bir taomga ikkinchi sotuv qo'shilsa ham u bitta taom bo'lib sanaladi.
        self.sell(self.choy, 2)
        coverage = self.finance()['coverage']
        self.assertEqual(coverage['sold_uncovered'], 1)
        self.assertEqual(coverage['menu_without_recipe'], 1)
        self.assertEqual(coverage['dishes_total'], 2)

    def test_broken_filters_and_non_owner_are_refused(self):
        self.assertEqual(self.client.get('/api/v1/finance/?month=2026-13').status_code, 400)
        future = (timezone.localdate().replace(day=28) + timedelta(days=10)).strftime('%Y-%m')
        self.assertEqual(self.client.get(f'/api/v1/finance/?month={future}').status_code, 400)
        today = timezone.localdate()
        self.assertEqual(
            self.client.get(f'/api/v1/finance/?start={today}&end={today - timedelta(days=1)}').status_code, 400)
        for role in ('admin', 'cashier', 'kitchen'):
            client = APIClient()
            client.force_authenticate(User.objects.create_user(f'{role}-f', password='test-only-long-password', role=role, branch=self.branch))
            self.assertEqual(client.get('/api/v1/finance/').status_code, 403)


class DailyUsageTests(TestCase):
    """Kunlik haqiqiy sarf: ombordan ayirmaydi, faqat solishtirish uchun."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        # Kunlik sarfni endi kassir kiritadi — «admin» roli olib tashlandi.
        self.admin = User.objects.create_user('admin', password='test-only-long-password', role='cashier', branch=self.branch, first_name='Admin')
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Manti', price=Decimal('12000'))
        # 1 kg kartoshka 5 000 so'm, 1 kg go'sht 80 000 so'm.
        self.potato = Ingredient.objects.create(branch=self.branch, name='Kartoshka', unit='kg', quantity=Decimal('100'), unit_cost=Decimal('5000'))
        self.meat = Ingredient.objects.create(branch=self.branch, name='Go‘sht', unit='kg', quantity=Decimal('50'), unit_cost=Decimal('80000'))
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.today = timezone.localdate()
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def recipe_for_one_manti(self):
        """1 ta manti uchun 20 g go'sht va 30 g kartoshka."""
        recipe = Recipe.objects.create(branch=self.branch, dish=self.dish, name='Manti', yield_quantity=Decimal('1'))
        RecipeLine.objects.create(recipe=recipe, ingredient=self.meat, quantity=Decimal('0.020'), batch_cost=Decimal('1600'))
        RecipeLine.objects.create(recipe=recipe, ingredient=self.potato, quantity=Decimal('0.030'), batch_cost=Decimal('150'))
        return recipe

    def report(self, lines, day=None):
        return self.client.post('/api/v1/daily-usage/', {
            'date': str(day or self.today),
            'lines': lines,
        }, format='json')

    def test_daily_report_never_touches_the_warehouse_balance(self):
        before = self.potato.quantity
        response = self.report([{'ingredient': self.potato.id, 'quantity': '5', 'note': 'Kechki sarf'}])
        self.assertEqual(response.status_code, 201)
        self.potato.refresh_from_db()
        # Eng muhim qoida: sotuv allaqachon ayirgan, bu yerda ikkinchi marta
        # ayirilsa qoldiq buzilardi.
        self.assertEqual(self.potato.quantity, before)
        self.assertEqual(DailyUsage.objects.get(ingredient=self.potato).quantity, Decimal('5.000'))
        self.assertFalse(StockMovement.objects.filter(kind='consumption').exists())

    def test_same_day_report_is_overwritten_not_added(self):
        self.report([{'ingredient': self.potato.id, 'quantity': '5', 'note': ''}])
        self.report([{'ingredient': self.potato.id, 'quantity': '8', 'note': 'tuzatildi'}])
        rows = DailyUsage.objects.filter(ingredient=self.potato, date=self.today)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.first().quantity, Decimal('8.000'))
        self.assertEqual(rows.first().note, 'tuzatildi')
        # O'zgartirish jurnalga tushadi.
        self.assertTrue(AuditEvent.objects.filter(action='usage.update').exists())

    def test_zero_removes_a_mistaken_line(self):
        self.report([{'ingredient': self.potato.id, 'quantity': '5', 'note': ''}])
        self.report([{'ingredient': self.potato.id, 'quantity': '0', 'note': ''}])
        self.assertFalse(DailyUsage.objects.filter(ingredient=self.potato).exists())
        self.assertTrue(AuditEvent.objects.filter(action='usage.remove').exists())

    def test_admin_sees_every_day_that_was_reported(self):
        yesterday = self.today - timedelta(days=1)
        self.report([{'ingredient': self.potato.id, 'quantity': '5', 'note': ''}])
        self.report([
            {'ingredient': self.potato.id, 'quantity': '4', 'note': ''},
            {'ingredient': self.meat.id, 'quantity': '2', 'note': ''},
        ], day=yesterday)

        data = self.client.get('/api/v1/daily-usage/').data
        self.assertEqual([day['date'] for day in data['days']], [str(self.today), str(yesterday)])
        earlier = data['days'][1]
        self.assertEqual(earlier['items'], 2)
        # 4 kg × 5 000 + 2 kg × 80 000 = 180 000
        self.assertEqual(earlier['value'], '180000.00')
        self.assertEqual(earlier['actors'], ['Admin'])

    def test_future_and_too_old_days_are_refused(self):
        tomorrow = self.today + timedelta(days=1)
        self.assertEqual(self.report([{'ingredient': self.potato.id, 'quantity': '1', 'note': ''}], day=tomorrow).status_code, 400)
        long_ago = self.today - timedelta(days=30)
        self.assertEqual(self.report([{'ingredient': self.potato.id, 'quantity': '1', 'note': ''}], day=long_ago).status_code, 400)
        # Dona butun bo'lishi kerak.
        piece = Ingredient.objects.create(branch=self.branch, name='Tuxum', unit='dona', quantity=Decimal('100'))
        self.assertEqual(self.report([{'ingredient': piece.id, 'quantity': '2.5', 'note': ''}]).status_code, 400)

    def test_comparison_puts_system_and_admin_side_by_side(self):
        self.recipe_for_one_manti()
        # 100 ta manti sotildi -> tizim 2 kg go'sht va 3 kg kartoshka hisoblaydi.
        create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': self.dish.id, 'quantity': 100, 'note': ''}],
        })
        # Kassir esa 2 kg go'sht va 4 kg kartoshka ketgan deb yozdi.
        self.report([
            {'ingredient': self.meat.id, 'quantity': '2', 'note': ''},
            {'ingredient': self.potato.id, 'quantity': '4', 'note': ''},
        ])

        owner = APIClient()
        owner.force_authenticate(self.owner)
        data = owner.get('/api/v1/daily-usage/compare/').data
        rows = {row['name']: row for row in data['rows']}
        self.assertEqual(rows['Go‘sht']['expected'], '2.000')
        self.assertEqual(rows['Go‘sht']['counted'], '2.000')
        self.assertEqual(rows['Go‘sht']['status'], 'ok')
        # Kartoshkada 1 kg ortiqcha ketgan — 33% farq, ogohlantiriladi.
        self.assertEqual(rows['Kartoshka']['expected'], '3.000')
        self.assertEqual(rows['Kartoshka']['counted'], '4.000')
        self.assertEqual(rows['Kartoshka']['gap'], '1.000')
        self.assertEqual(rows['Kartoshka']['gap_value'], '5000.00')
        self.assertEqual(rows['Kartoshka']['status'], 'alert')
        self.assertEqual(data['summary']['alerts'], 1)
        # Eng katta pul farqi yuqorida turadi.
        self.assertEqual(data['rows'][0]['name'], 'Kartoshka')

    def test_comparison_marks_one_sided_rows_without_calling_them_alerts(self):
        self.recipe_for_one_manti()
        create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': self.dish.id, 'quantity': 100, 'note': ''}],
        })
        owner = APIClient()
        owner.force_authenticate(self.owner)
        data = owner.get('/api/v1/daily-usage/compare/').data
        rows = {row['name']: row for row in data['rows']}
        # Admin hali yozmagan: bu farq emas, hisobot to'liq emas.
        self.assertEqual(rows['Kartoshka']['status'], 'missing')
        self.assertEqual(data['summary']['alerts'], 0)
        self.assertGreater(data['summary']['missing_days'], 0)

    def test_the_cashier_writes_but_only_the_owner_compares(self):
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        # Kunlik sarfni kassir kiritadi.
        self.assertEqual(cashier.get('/api/v1/daily-usage/').status_code, 200)
        self.assertEqual(cashier.post('/api/v1/daily-usage/', {
            'date': str(self.today),
            'lines': [{'ingredient': self.potato.id, 'quantity': '3', 'note': ''}],
        }, format='json').status_code, 201)
        # Lekin solishtirishni ko'rmaydi — bu uning ustidan nazorat.
        self.assertEqual(cashier.get('/api/v1/daily-usage/compare/').status_code, 403)
        # Oshxona umuman kira olmaydi.
        kitchen = APIClient()
        kitchen.force_authenticate(User.objects.create_user(
            'oshxona-x', password='test-only-long-password', role='kitchen', branch=self.branch))
        self.assertEqual(kitchen.get('/api/v1/daily-usage/').status_code, 403)
        owner = APIClient()
        owner.force_authenticate(self.owner)
        self.assertEqual(owner.get('/api/v1/daily-usage/compare/').status_code, 200)


class FullSetupFlowTests(TestCase):
    """Egasi aytgan tartib: masalliq -> narx -> taom + retsept -> sotuv -> kunlik hisobot."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.admin = User.objects.create_user('admin', password='test-only-long-password', role='cashier', branch=self.branch, first_name='Admin')
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Milliy taomlar')
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_owner_builds_the_menu_and_the_system_costs_every_sale(self):
        # 1-qadam: masalliqlar narxi bilan qo'shiladi.
        meat = self.client.post('/api/v1/ingredients/', {
            'name': 'Go‘sht', 'unit': 'kg', 'minimum': '2', 'unit_cost': '80000',
        }, format='json').data
        flour = self.client.post('/api/v1/ingredients/', {
            'name': 'Un', 'unit': 'kg', 'minimum': '5', 'unit_cost': '6000',
        }, format='json').data
        self.assertEqual(Ingredient.objects.get(pk=meat['id']).unit_cost, Decimal('80000.0000'))

        # 2-qadam: taom yaratiladi va o'sha zahoti retsepti yoziladi.
        dish = self.client.post('/api/v1/dishes/', {
            'name': 'Manti', 'category': self.category.id, 'description': '',
            'price': '12000', 'portion': '1 dona', 'available': True,
        }, format='json').data
        recipe = self.client.post('/api/v1/recipes/', {
            'dish': dish['id'], 'name': 'Manti', 'yield_quantity': 1, 'yield_unit': 'porsiya',
            'active': True,
            # 1 ta manti: 20 g go'sht + 15 g un (frontend grammni kg ga aylantirib yuboradi).
            'lines': [
                {'ingredient': meat['id'], 'quantity': 0.020},
                {'ingredient': flour['id'], 'quantity': 0.015},
            ],
        }, format='json').data

        # Tannarx qo'lda emas, masalliq narxidan hisoblanadi:
        # 0.020 × 80 000 = 1 600 va 0.015 × 6 000 = 90.
        costs = {line['ingredient_name']: line['batch_cost'] for line in recipe['lines']}
        self.assertEqual(costs['Go‘sht'], '1600.00')
        self.assertEqual(costs['Un'], '90.00')
        self.assertEqual(Decimal(recipe['unit_cost']), Decimal('1690'))
        # 12 000 so'mga sotiladi, tannarxi 1 690 -> foyda 10 310.
        self.assertEqual(Decimal(recipe['gross_profit']), Decimal('10310'))

        # 3-qadam: ombor to'ldiriladi.
        for item, amount, spent in ((meat, '10', '800000'), (flour, '20', '120000')):
            self.client.post('/api/v1/stock/', {
                'key': str(uuid4()), 'ingredient': item['id'], 'kind': 'receipt',
                'quantity': amount, 'cost_total': spent,
                'date': str(timezone.localdate()), 'note': 'Bozordan',
            }, format='json')

        # 4-qadam: 50 ta manti sotiladi -> ombordan o'zi ayriladi.
        # Oshxona ertalab pishirdi — tayyorsiz sotuv bo'lmaydi.
        prepare(self.cashier, Dish.objects.get(pk=dish['id']))
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': dish['id'], 'quantity': 50, 'note': ''}],
        })
        meat_row = Ingredient.objects.get(pk=meat['id'])
        flour_row = Ingredient.objects.get(pk=flour['id'])
        self.assertEqual(meat_row.quantity, Decimal('9.000'))    # 10 − 50×0.020
        self.assertEqual(flour_row.quantity, Decimal('19.250'))  # 20 − 50×0.015
        # Sotuv tannarxi ham o'sha narxda muzlatiladi: 50 × 1 690.
        self.assertEqual(order.lines.first().cost_total, Decimal('84500.00'))

        # 5-qadam: admin kechqurun haqiqiy sarfni yozadi.
        admin = APIClient()
        admin.force_authenticate(self.admin)
        self.assertEqual(admin.post('/api/v1/daily-usage/', {
            'date': str(timezone.localdate()),
            'lines': [
                {'ingredient': meat['id'], 'quantity': '1.2', 'note': ''},
                {'ingredient': flour['id'], 'quantity': '0.75', 'note': ''},
            ],
        }, format='json').status_code, 201)
        # Kunlik hisobot ombordan hech narsa ayirmaydi.
        meat_row.refresh_from_db()
        self.assertEqual(meat_row.quantity, Decimal('9.000'))

        # 6-qadam: superadmin farqni ko'radi.
        compare = self.client.get('/api/v1/daily-usage/compare/').data
        rows = {row['name']: row for row in compare['rows']}
        # Tizim 1 kg go'sht deydi, admin 1.2 kg yozdi -> 200 g ortiqcha, 20% farq.
        self.assertEqual(rows['Go‘sht']['expected'], '1.000')
        self.assertEqual(rows['Go‘sht']['counted'], '1.200')
        self.assertEqual(rows['Go‘sht']['gap'], '0.200')
        self.assertEqual(rows['Go‘sht']['gap_value'], '16000.00')
        self.assertEqual(rows['Go‘sht']['status'], 'alert')
        # Unda farq 0 — retsept to'g'ri.
        self.assertEqual(rows['Un']['status'], 'ok')
        self.assertEqual(compare['summary']['alerts'], 1)

    def test_changing_an_ingredient_price_updates_every_recipe_at_once(self):
        meat = self.client.post('/api/v1/ingredients/', {
            'name': 'Go‘sht', 'unit': 'kg', 'minimum': '0', 'unit_cost': '80000',
        }, format='json').data
        for name in ('Manti', 'Somsa'):
            dish = self.client.post('/api/v1/dishes/', {
                'name': name, 'category': self.category.id, 'description': '',
                'price': '12000', 'available': True,
            }, format='json').data
            self.client.post('/api/v1/recipes/', {
                'dish': dish['id'], 'name': name, 'yield_quantity': 1, 'yield_unit': 'porsiya',
                'active': True,
                'lines': [{'ingredient': meat['id'], 'quantity': 0.020}],
            }, format='json')
        self.assertEqual(set(RecipeLine.objects.values_list('batch_cost', flat=True)), {Decimal('1600.00')})

        # Go'sht qimmatlashdi: ikkala retsept ham o'zi yangilanadi.
        response = self.client.patch(f'/api/v1/ingredients/{meat["id"]}/', {'unit_cost': '120000'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(RecipeLine.objects.values_list('batch_cost', flat=True)), {Decimal('2400.00')})
        # O'zgarish jurnalga tushadi.
        entry = AuditEvent.objects.get(action='stock.price')
        self.assertIn('Go‘sht', entry.description)
        self.assertIn('2 ta retsept qatori', entry.description)

    def test_old_sales_keep_their_original_cost_when_prices_change(self):
        meat = self.client.post('/api/v1/ingredients/', {
            'name': 'Go‘sht', 'unit': 'kg', 'minimum': '0', 'unit_cost': '80000',
        }, format='json').data
        dish = self.client.post('/api/v1/dishes/', {
            'name': 'Manti', 'category': self.category.id, 'description': '',
            'price': '12000', 'available': True,
        }, format='json').data
        self.client.post('/api/v1/recipes/', {
            'dish': dish['id'], 'name': 'Manti', 'yield_quantity': 1, 'yield_unit': 'porsiya',
            'active': True,
            'lines': [{'ingredient': meat['id'], 'quantity': 0.020}],
        }, format='json')
        self.client.post('/api/v1/stock/', {
            'key': str(uuid4()), 'ingredient': meat['id'], 'kind': 'receipt',
            'quantity': '10', 'cost_total': '800000', 'date': str(timezone.localdate()), 'note': 'x',
        }, format='json')
        # Oshxona ertalab pishirdi — tayyorsiz sotuv bo'lmaydi.
        prepare(self.cashier, Dish.objects.get(pk=dish['id']))
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': dish['id'], 'quantity': 10, 'note': ''}],
        })
        self.assertEqual(order.lines.first().cost_total, Decimal('16000.00'))

        # Narx ikki barobar oshsa ham o'tgan savdoning tannarxi o'zgarmaydi.
        self.client.patch(f'/api/v1/ingredients/{meat["id"]}/', {'unit_cost': '160000'}, format='json')
        order.lines.first().refresh_from_db()
        self.assertEqual(order.lines.first().cost_total, Decimal('16000.00'))
        # Yangi retsept tannarxi esa yangilangan.
        self.assertEqual(RecipeLine.objects.first().batch_cost, Decimal('3200.00'))


class OrderCorrectionTests(TestCase):
    """Kassir xatosini qaytarish: qator o'chirish, bekor qilish, pul qaytarish."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.kitchen = User.objects.create_user('oshxona', password='test-only-long-password', role='kitchen', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.osh = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.choy = Dish.objects.create(branch=self.branch, category=self.category, name='Choy', price=Decimal('10000'))
        self.rice = Ingredient.objects.create(branch=self.branch, name='Guruch', unit='kg', quantity=Decimal('100'), unit_cost=Decimal('5000'))
        recipe = Recipe.objects.create(branch=self.branch, dish=self.osh, name='Osh', yield_quantity=Decimal('10'))
        RecipeLine.objects.create(recipe=recipe, ingredient=self.rice, quantity=Decimal('2'), batch_cost=Decimal('10000'))
        self.table = Table.objects.create(branch=self.branch, number=1)
        self.client = APIClient()
        self.client.force_authenticate(self.cashier)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def open_bill(self, lines=None):
        return create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'table_id': self.table.id, 'waiter': '', 'payment_method': '',
            'lines': lines or [
                {'dish': self.osh.id, 'quantity': 2, 'note': ''},
                {'dish': self.choy.id, 'quantity': 3, 'note': ''},
            ],
        })

    def test_wrong_dish_can_be_taken_off_an_open_bill(self):
        order = self.open_bill()
        self.assertEqual(order.total, Decimal('130000'))  # 2×50 000 + 3×10 000
        wrong = order.lines.get(name='Choy')

        response = self.client.delete(f'/api/v1/orders/{order.id}/lines/{wrong.id}/')
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal('100000'))
        self.assertEqual(order.lines.count(), 1)
        entry = AuditEvent.objects.get(action='order.line_remove')
        self.assertIn('Choy x3', entry.description)

    def test_the_last_line_cannot_be_removed_only_the_whole_bill(self):
        order = self.open_bill([{'dish': self.osh.id, 'quantity': 1, 'note': ''}])
        only = order.lines.first()
        response = self.client.delete(f'/api/v1/orders/{order.id}/lines/{only.id}/')
        # Summasi nol hisob bo'lolmaydi, shuning uchun butun hisob bekor qilinadi.
        self.assertEqual(response.status_code, 409)
        order.refresh_from_db()
        self.assertEqual(order.lines.count(), 1)

    def test_cancelling_an_open_bill_frees_the_table_and_keeps_the_record(self):
        order = self.open_bill()
        response = self.client.post(f'/api/v1/orders/{order.id}/cancel/', {'reason': 'Mijoz ketib qoldi'}, format='json')
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')
        self.assertEqual(order.void_reason, 'Mijoz ketib qoldi')
        self.assertEqual(order.voided_by, self.cashier)
        self.assertIsNotNone(order.voided_at)
        # Yozuv o'chmaydi — tarixda qoladi.
        self.assertTrue(Order.objects.filter(pk=order.pk).exists())
        # Stol bo'shaydi.
        table = self.client.get('/api/v1/tables/').data['results'][0]
        self.assertIsNone(table['open_order'])
        # Bekor qilingan hisob oshxona taxtasida turmaydi.
        kitchen = APIClient()
        kitchen.force_authenticate(self.kitchen)
        self.assertEqual(kitchen.get('/api/v1/kitchen/orders/').data, [])

    def test_cancelling_requires_a_reason_and_only_works_once(self):
        order = self.open_bill()
        self.assertEqual(self.client.post(f'/api/v1/orders/{order.id}/cancel/', {'reason': ''}, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'/api/v1/orders/{order.id}/cancel/', {'reason': 'ha'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(f'/api/v1/orders/{order.id}/cancel/', {'reason': 'Mijoz ketdi'}, format='json').status_code, 200)
        # Ikkinchi marta bekor qilib bo'lmaydi.
        again = self.client.post(f'/api/v1/orders/{order.id}/cancel/', {'reason': 'yana'}, format='json')
        self.assertEqual(again.status_code, 409)

    def test_cancelled_bill_cannot_be_paid_or_added_to(self):
        order = self.open_bill()
        self.client.post(f'/api/v1/orders/{order.id}/cancel/', {'reason': 'Mijoz ketdi'}, format='json')
        self.assertEqual(self.client.post(f'/api/v1/orders/{order.id}/pay/', {'payment_method': 'cash'}, format='json').status_code, 409)
        added = self.client.post(f'/api/v1/orders/{order.id}/lines/', {
            'key': str(uuid4()), 'lines': [{'dish': self.choy.id, 'quantity': 1, 'note': ''}],
        }, format='json')
        self.assertEqual(added.status_code, 409)

    def test_refund_returns_the_money_and_the_ingredients(self):
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': self.osh.id, 'quantity': 10, 'note': ''}],
        })
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.quantity, Decimal('98.000'))  # 100 − 2 kg

        owner = APIClient()
        owner.force_authenticate(self.owner)
        response = owner.post(f'/api/v1/orders/{order.id}/refund/', {'reason': 'Mijoz shikoyat qildi'}, format='json')
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, 'refunded')
        # Masalliq omborga qaytadi.
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.quantity, Decimal('100.000'))
        # Qaytish alohida harakat bo'lib yoziladi, eski yozuv o'chmaydi.
        back = StockMovement.objects.get(note=f'#{order.id} buyurtma qaytarildi')
        self.assertEqual(back.quantity, Decimal('2.000'))
        self.assertTrue(StockMovement.objects.filter(kind='sale_consumption', note__startswith=f'#{order.id}').exists())

    def test_refunded_sale_leaves_every_revenue_figure(self):
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': self.osh.id, 'quantity': 10, 'note': ''}],
        })
        owner = APIClient()
        owner.force_authenticate(self.owner)
        before = owner.get('/api/v1/finance/').data['profit']['revenue']
        self.assertEqual(before, '500000.00')

        owner.post(f'/api/v1/orders/{order.id}/refund/', {'reason': 'Noto‘g‘ri to‘lov'}, format='json')
        # Qaytarilgan savdo tushumda ham, tannarxda ham qolmaydi.
        after = owner.get('/api/v1/finance/').data
        self.assertEqual(after['profit']['revenue'], '0.00')
        self.assertEqual(after['profit']['cogs'], '0.00')
        # Eslatma: bu ikki endpoint pulni boshqa formatda qaytaradi ('0' va '0.00').
        # Formatni money.py ga birlashtirganda tekislanadi.
        self.assertEqual(Decimal(owner.get('/api/v1/sales/summary/').data['today']['revenue']), Decimal('0'))
        self.assertEqual(Decimal(owner.get('/api/v1/dashboard/').data['revenue']), Decimal('0'))

    def test_only_managers_refund_but_any_cashier_cancels(self):
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': self.osh.id, 'quantity': 1, 'note': ''}],
        })
        # Kassir pul qaytara olmaydi — bu boshqaruv qarori.
        self.assertEqual(self.client.post(f'/api/v1/orders/{order.id}/refund/', {'reason': 'xato'}, format='json').status_code, 403)
        owner = APIClient()
        owner.force_authenticate(self.owner)
        self.assertEqual(owner.post(f'/api/v1/orders/{order.id}/refund/', {'reason': 'Noto‘g‘ri'}, format='json').status_code, 200)


class ShiftCloseTests(TestCase):
    """Kun yakuni: kassada qancha bo'lishi kerak edi va qancha chiqdi."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch, first_name='Kassir')
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.client = APIClient()
        self.client.force_authenticate(self.cashier)
        self.today = timezone.localdate()
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def sell(self, quantity, method):
        return create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': method,
            'lines': [{'dish': self.dish.id, 'quantity': quantity, 'note': ''}],
        })

    def spend(self, amount, method='cash'):
        # Xarajatni faqat boshqaruv kiritadi, kassir emas.
        manager = APIClient()
        manager.force_authenticate(self.owner)
        return manager.post('/api/v1/expenses/', {
            'key': str(uuid4()), 'category': 'Bozor', 'purpose': 'Kunlik xarid',
            'recipient': '', 'amount': str(amount), 'payment_method': method, 'date': str(self.today),
        }, format='json')

    def test_expected_cash_counts_only_cash_and_subtracts_cash_spending(self):
        self.sell(4, 'cash')     # 200 000 naqd
        self.sell(2, 'card')     # 100 000 karta — kassada qolmaydi
        self.sell(1, 'click')    # 50 000 Click — kassada qolmaydi
        self.spend(30000)        # 30 000 naqd chiqdi
        self.spend(70000, 'card')  # karta orqali — naqdga tegmaydi

        data = self.client.get('/api/v1/shift/').data
        self.assertFalse(data['closed'])
        self.assertEqual(data['revenue'], '350000.00')
        self.assertEqual(data['cash_in'], '200000.00')
        self.assertEqual(data['cash_out'], '30000.00')
        # Kassada 200 000 − 30 000 = 170 000 bo'lishi kerak.
        self.assertEqual(data['expected_cash'], '170000.00')
        drawer = {row['method']: row['in_drawer'] for row in data['breakdown']}
        self.assertTrue(drawer['cash'])
        self.assertFalse(drawer['card'])
        self.assertFalse(drawer['click'])

    def test_closing_records_the_difference_and_freezes_the_day(self):
        self.sell(4, 'cash')
        response = self.client.post('/api/v1/shift/', {'counted_cash': '195000', 'note': 'Sanaldi'}, format='json')
        self.assertEqual(response.status_code, 201)
        closed = response.data
        self.assertTrue(closed['closed'])
        self.assertEqual(closed['expected_cash'], '200000.00')
        self.assertEqual(closed['counted_cash'], '195000.00')
        # 5 000 so'm kam chiqdi.
        self.assertEqual(closed['difference'], '-5000.00')
        self.assertEqual(closed['actor'], 'Kassir')

        # Yopilgandan keyin yangi savdo bo'lsa ham yopilgan kun o'zgarmaydi.
        self.sell(10, 'cash')
        again = self.client.get('/api/v1/shift/').data
        self.assertEqual(again['expected_cash'], '200000.00')
        self.assertEqual(again['revenue'], '200000.00')

    def test_a_big_difference_is_flagged(self):
        self.sell(4, 'cash')  # 200 000 kutilyapti
        small = self.client.post('/api/v1/shift/', {'counted_cash': '198000', 'note': ''}, format='json').data
        self.assertFalse(small['alert'])

        ShiftClose.objects.all().delete()
        big = self.client.post('/api/v1/shift/', {'counted_cash': '150000', 'note': ''}, format='json').data
        # 50 000 so'm farq — e'tibor talab qiladi.
        self.assertEqual(big['difference'], '-50000.00')
        self.assertTrue(big['alert'])

    def test_a_day_cannot_be_closed_twice(self):
        self.sell(1, 'cash')
        self.assertEqual(self.client.post('/api/v1/shift/', {'counted_cash': '50000'}, format='json').status_code, 201)
        second = self.client.post('/api/v1/shift/', {'counted_cash': '50000'}, format='json')
        self.assertEqual(second.status_code, 400)
        self.assertEqual(ShiftClose.objects.count(), 1)

    def test_open_bills_are_shown_so_the_cashier_does_not_close_too_early(self):
        create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': '',
            'lines': [{'dish': self.dish.id, 'quantity': 2, 'note': ''}],
        })
        data = self.client.get('/api/v1/shift/').data
        # Ochiq hisob kassaga hali tushmagan — kassir buni ko'rishi kerak.
        self.assertEqual(data['open_orders'], 1)
        self.assertEqual(data['expected_cash'], '0.00')

    def test_refunded_sale_leaves_the_expected_cash(self):
        order = self.sell(4, 'cash')
        owner = APIClient()
        owner.force_authenticate(self.owner)
        owner.post(f'/api/v1/orders/{order.id}/refund/', {'reason': 'Shikoyat'}, format='json')
        data = self.client.get('/api/v1/shift/').data
        self.assertEqual(data['expected_cash'], '0.00')
        self.assertEqual(data['revenue'], '0.00')

    def test_history_is_for_managers_and_sums_the_gaps(self):
        self.sell(4, 'cash')
        self.client.post('/api/v1/shift/', {'counted_cash': '195000'}, format='json')
        # Kassir tarixni ko'rmaydi — bu boshqaruv nazorati.
        self.assertEqual(self.client.get('/api/v1/shift/history/').status_code, 403)
        owner = APIClient()
        owner.force_authenticate(self.owner)
        history = owner.get('/api/v1/shift/history/').data
        self.assertEqual(history['summary']['closed_days'], 1)
        self.assertEqual(history['summary']['total_difference'], '-5000.00')
        self.assertEqual(history['days'][0]['note'], '')

    def test_future_and_old_days_are_refused(self):
        tomorrow = self.today + timedelta(days=1)
        self.assertEqual(self.client.get(f'/api/v1/shift/?date={tomorrow}').status_code, 400)
        old = self.today - timedelta(days=30)
        self.assertEqual(self.client.post('/api/v1/shift/', {'date': str(old), 'counted_cash': '0'}, format='json').status_code, 400)


class MoneyFormatTests(TestCase):
    """Pul hamma joyda bir xil ko'rinsin: «0» va «0.00» aralashmasin."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def test_helpers_agree_on_shape(self):
        # Ikki kasr har doim, manfiy nol esa hech qachon.
        self.assertEqual(money(Decimal('3000000')), '3000000.00')
        self.assertEqual(money(None), '0.00')
        self.assertEqual(money(Decimal('-0.001')), '0.00')
        self.assertEqual(quantity(Decimal('20')), '20.000')
        self.assertEqual(quantity(Decimal('19.705') - Decimal('20') + Decimal('0.295')), '0.000')
        # Bo'luvchi nol bo'lganda: percent nol, share esa «noma'lum».
        self.assertEqual(percent(Decimal('1'), Decimal('0')), '0.00')
        self.assertEqual(share(Decimal('1'), Decimal('0')), '')
        self.assertEqual(share(Decimal('1'), Decimal('4')), '25.00')

    def test_every_money_endpoint_returns_the_same_shape_when_empty(self):
        # Bo'sh bazada ham hamma nol bir xil yozilishi kerak.
        self.assertEqual(self.client.get('/api/v1/sales/summary/').data['today']['revenue'], '0.00')
        self.assertEqual(self.client.get('/api/v1/dashboard/').data['revenue'], '0.00')
        self.assertEqual(self.client.get('/api/v1/finance/').data['profit']['revenue'], '0.00')
        self.assertEqual(self.client.get('/api/v1/payroll/').data['summary']['paid'], '0.00')
        self.assertEqual(self.client.get('/api/v1/shift/').data['expected_cash'], '0.00')
        self.assertEqual(self.client.get('/api/v1/stock/usage/').data['summary']['used_value'], '0.00')

    def test_the_same_sale_reads_the_same_in_every_report(self):
        create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': self.dish.id, 'quantity': 3, 'note': ''}],
        })
        expected = '150000.00'
        self.assertEqual(self.client.get('/api/v1/finance/').data['profit']['revenue'], expected)
        self.assertEqual(self.client.get('/api/v1/sales/summary/').data['today']['revenue'], expected)
        self.assertEqual(self.client.get('/api/v1/dashboard/').data['revenue'], expected)
        self.assertEqual(self.client.get('/api/v1/shift/').data['revenue'], expected)
        # Hisobot ham, sotuv taxtasi ham xuddi shu raqamni beradi.
        today = timezone.localdate()
        report = self.client.get(f'/api/v1/reports/sales/?start={today}&end={today}').data
        board = self.client.get(f'/api/v1/sales/board/?start={today}&end={today}').data
        self.assertEqual(Decimal(report['summary']['revenue']), Decimal(expected))
        self.assertEqual(Decimal(board['summary']['revenue']), Decimal(expected))

    def test_money_module_is_the_only_definition(self):
        """money() endi bitta joyda — nusxalar qayta paydo bo'lmasin."""
        import pathlib
        root = pathlib.Path(__file__).resolve().parent.parent
        owners = []
        for path in root.rglob('*.py'):
            if 'migrations' in path.parts or path.name == 'tests.py':
                continue
            marker = chr(10) + 'def money('
            if marker in path.read_text(encoding='utf-8'):
                owners.append(path.name)
        # printing.py chek uchun boshqacha formatlaydi ('40 000'), shuning uchun
        # uning funksiyasi som_text deb ataladi va bu ro'yxatga tushmaydi.
        self.assertEqual(sorted(owners), ['money.py'], owners)


class DiscountTests(TestCase):
    """Chegirma: tushumdan o'zi ayriladi, kassir esa cheksiz bera olmaydi."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.client = APIClient()
        self.client.force_authenticate(self.cashier)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def open_bill(self, quantity=4):
        return create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': '',
            'lines': [{'dish': self.dish.id, 'quantity': quantity, 'note': ''}],
        })

    def discount(self, order, amount, reason='Doimiy mijoz', client=None):
        return (client or self.client).post(
            f'/api/v1/orders/{order.id}/discount/',
            {'amount': str(amount), 'reason': reason}, format='json',
        )

    def test_discount_lowers_what_the_guest_pays(self):
        order = self.open_bill()  # 200 000
        response = self.discount(order, 30000)
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.discount, Decimal('30000.00'))
        self.assertEqual(order.total, Decimal('170000.00'))
        self.assertEqual(order.discount_reason, 'Doimiy mijoz')
        entry = AuditEvent.objects.get(action='order.discount')
        self.assertIn('15.0%', entry.description)

    def test_discount_flows_straight_into_revenue(self):
        order = self.open_bill()
        self.discount(order, 30000)
        self.client.post(f'/api/v1/orders/{order.id}/pay/', {'payment_method': 'cash'}, format='json')

        owner = APIClient()
        owner.force_authenticate(self.owner)
        finance = owner.get('/api/v1/finance/').data['profit']
        # Tushum chegirma ayirilgandan keyingi summa — alohida ayirish shart emas.
        self.assertEqual(finance['revenue'], '170000.00')
        self.assertEqual(finance['discounts'], '30000.00')
        self.assertEqual(finance['discount_share'], '15.00')
        # Kassa ham 170 000 kutadi.
        self.assertEqual(self.client.get('/api/v1/shift/').data['expected_cash'], '170000.00')

    def test_reapplying_replaces_rather_than_stacking(self):
        order = self.open_bill()
        self.discount(order, 30000)
        self.discount(order, 10000)
        order.refresh_from_db()
        # Ikkinchi chegirma birinchisining ustiga qo'shilmaydi.
        self.assertEqual(order.discount, Decimal('10000.00'))
        self.assertEqual(order.total, Decimal('190000.00'))

        # Nol yuborilsa chegirma butunlay olib tashlanadi.
        self.discount(order, 0, reason='')
        order.refresh_from_db()
        self.assertEqual(order.discount, Decimal('0.00'))
        self.assertEqual(order.total, Decimal('200000.00'))
        self.assertEqual(order.discount_reason, '')

    def test_a_cashier_may_discount_any_amount_but_it_is_always_recorded(self):
        order = self.open_bill()  # 200 000
        # Cheklov yo'q — egasining qarori. Yagona nazorat jurnal.
        allowed = self.discount(order, 50000, reason='Doimiy mijoz')
        self.assertEqual(allowed.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal('150000.00'))
        entry = AuditEvent.objects.get(action='order.discount')
        self.assertEqual(entry.actor, self.cashier)
        self.assertIn('25.0%', entry.description)
        self.assertIn('Doimiy mijoz', entry.description)

    def test_a_reason_is_required_and_a_full_discount_is_refused(self):
        order = self.open_bill()
        self.assertEqual(self.discount(order, 10000, reason='').status_code, 400)
        # To'liq chegirma o'rniga hisob bekor qilinadi — yozuv shunda to'g'ri bo'ladi.
        owner = APIClient()
        owner.force_authenticate(self.owner)
        self.assertEqual(self.discount(order, 200000, client=owner).status_code, 400)
        self.assertEqual(self.discount(order, 300000, client=owner).status_code, 400)

    def test_discount_survives_adding_more_dishes(self):
        order = self.open_bill(2)  # 100 000
        self.discount(order, 10000)
        self.client.post(f'/api/v1/orders/{order.id}/lines/', {
            'key': str(uuid4()), 'lines': [{'dish': self.dish.id, 'quantity': 1, 'note': ''}],
        }, format='json')
        order.refresh_from_db()
        # 100 000 − 10 000 + 50 000
        self.assertEqual(order.total, Decimal('140000.00'))
        self.assertEqual(order.discount, Decimal('10000.00'))

    def test_a_closed_bill_cannot_be_discounted(self):
        order = self.open_bill()
        self.client.post(f'/api/v1/orders/{order.id}/pay/', {'payment_method': 'cash'}, format='json')
        self.assertEqual(self.discount(order, 10000).status_code, 409)


class AssistantChatTests(TestCase):
    """AI suhbatlari saqlanadi va faqat egasiga ko'rinadi."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.other = Branch.objects.create(name='Two', slug='two')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.admin = User.objects.create_user('admin', password='test-only-long-password', role='admin', branch=self.branch)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def ask(self, question, chat=None):
        body = {'question': question}
        if chat:
            body['chat'] = chat
        return self.client.post('/api/v1/assistant/chat/', body, format='json')

    def test_a_question_starts_a_chat_titled_after_it(self):
        response = self.ask('Bugun qanday o‘tdi?')
        self.assertEqual(response.status_code, 200)
        self.assertIn('chat', response.data)
        chat = AssistantChat.objects.get()
        self.assertEqual(chat.title, 'Bugun qanday o‘tdi?')
        self.assertEqual(chat.actor, self.owner)
        # Savol ham, javob ham saqlanadi.
        self.assertEqual([item.role for item in chat.messages.all()], ['user', 'assistant'])
        self.assertTrue(chat.messages.last().text)

    def test_a_long_question_gets_a_trimmed_title(self):
        long_question = 'Bugun ' + 'juda uzun savol ' * 10
        self.ask(long_question)
        title = AssistantChat.objects.get().title
        self.assertLessEqual(len(title), 60)
        self.assertTrue(title.endswith('…'))

    def test_following_up_stays_in_the_same_chat(self):
        first = self.ask('Bugun qanday o‘tdi?').data['chat']
        second = self.ask('Oxirgi 7 kun tahlili', chat=first).data['chat']
        self.assertEqual(first, second)
        self.assertEqual(AssistantChat.objects.count(), 1)
        self.assertEqual(AssistantMessage.objects.count(), 4)
        # Sarlavha birinchi savoldan qoladi.
        self.assertEqual(AssistantChat.objects.get().title, 'Bugun qanday o‘tdi?')

    def test_a_new_question_without_a_chat_opens_a_new_one(self):
        self.ask('Bugun qanday o‘tdi?')
        self.ask('Omborda nima kamaygan?')
        self.assertEqual(AssistantChat.objects.count(), 2)

    def test_the_list_shows_newest_first_with_a_preview(self):
        self.ask('Bugun qanday o‘tdi?')
        self.ask('Omborda nima kamaygan?')
        rows = self.client.get('/api/v1/assistant/chats/').data['chats']
        self.assertEqual([row['title'] for row in rows], ['Omborda nima kamaygan?', 'Bugun qanday o‘tdi?'])
        self.assertEqual(rows[0]['preview'], 'Omborda nima kamaygan?')

    def test_opening_a_chat_returns_the_whole_conversation(self):
        chat = self.ask('Bugun qanday o‘tdi?').data['chat']
        self.ask('Oxirgi 7 kun tahlili', chat=chat)
        data = self.client.get(f'/api/v1/assistant/chats/{chat}/').data
        self.assertEqual(len(data['messages']), 4)
        self.assertEqual(data['messages'][0]['text'], 'Bugun qanday o‘tdi?')
        self.assertEqual(data['messages'][0]['role'], 'user')
        # Grafiklar javob bilan birga qaytadi.
        self.assertIsInstance(data['messages'][1]['charts'], list)

    def test_a_chat_can_be_deleted_with_its_messages(self):
        chat = self.ask('Bugun qanday o‘tdi?').data['chat']
        self.assertEqual(self.client.delete(f'/api/v1/assistant/chats/{chat}/').status_code, 200)
        self.assertFalse(AssistantChat.objects.exists())
        self.assertFalse(AssistantMessage.objects.exists())

    def test_one_owner_never_sees_another_persons_chat(self):
        mine = self.ask('Bugun qanday o‘tdi?').data['chat']
        stranger = User.objects.create_user('owner2', password='test-only-long-password', role='owner', branch=self.branch)
        theirs = APIClient()
        theirs.force_authenticate(stranger)
        # Bu shaxsiy ish daftari: boshqa superadmin ham ko'rmaydi.
        self.assertEqual(theirs.get('/api/v1/assistant/chats/').data['chats'], [])
        self.assertEqual(theirs.get(f'/api/v1/assistant/chats/{mine}/').status_code, 400)
        self.assertEqual(theirs.delete(f'/api/v1/assistant/chats/{mine}/').status_code, 400)
        self.assertTrue(AssistantChat.objects.filter(pk=mine).exists())

    def test_writing_into_someone_elses_chat_is_refused(self):
        mine = self.ask('Bugun qanday o‘tdi?').data['chat']
        stranger = User.objects.create_user('owner3', password='test-only-long-password', role='owner', branch=self.branch)
        theirs = APIClient()
        theirs.force_authenticate(stranger)
        response = theirs.post('/api/v1/assistant/chat/', {'question': 'Salom', 'chat': mine}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(AssistantMessage.objects.filter(chat_id=mine).count(), 2)

    def test_a_chat_can_be_renamed(self):
        chat = self.ask('Bugun qanday o‘tdi?').data['chat']
        response = self.client.patch(
            f'/api/v1/assistant/chats/{chat}/', {'title': 'Sentabr tahlili'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Sentabr tahlili')
        self.assertEqual(AssistantChat.objects.get(pk=chat).title, 'Sentabr tahlili')
        # Gaplar tegilmaydi.
        self.assertEqual(AssistantMessage.objects.filter(chat_id=chat).count(), 2)

    def test_a_blank_name_is_refused_and_spaces_are_trimmed(self):
        chat = self.ask('Bugun qanday o‘tdi?').data['chat']
        self.assertEqual(
            self.client.patch(f'/api/v1/assistant/chats/{chat}/', {'title': '   '}, format='json').status_code, 400)
        self.client.patch(f'/api/v1/assistant/chats/{chat}/', {'title': '  Oylik  '}, format='json')
        self.assertEqual(AssistantChat.objects.get(pk=chat).title, 'Oylik')

    def test_renaming_someone_elses_chat_is_refused(self):
        mine = self.ask('Bugun qanday o‘tdi?').data['chat']
        stranger = User.objects.create_user('owner4', password='test-only-long-password', role='owner', branch=self.branch)
        theirs = APIClient()
        theirs.force_authenticate(stranger)
        self.assertEqual(
            theirs.patch(f'/api/v1/assistant/chats/{mine}/', {'title': 'Meniki'}, format='json').status_code, 400)
        self.assertEqual(AssistantChat.objects.get(pk=mine).title, 'Bugun qanday o‘tdi?')

    def test_only_the_owner_role_reaches_the_assistant(self):
        client = APIClient()
        client.force_authenticate(self.admin)
        self.assertEqual(client.get('/api/v1/assistant/chats/').status_code, 403)
        self.assertEqual(client.post('/api/v1/assistant/chat/', {'question': 'Salom'}, format='json').status_code, 403)


class WaiterTests(TestCase):
    """Ofitsiant va uning ulushi: foizni egasi belgilaydi, kassir bog'laydi."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def add_waiter(self, name='Fazliddin', commission='5'):
        return self.client.post('/api/v1/waiters/', {
            'name': name, 'phone': '', 'commission': commission, 'active': True,
        }, format='json')

    def sell(self, waiter_id=None, quantity=4, channel='hall'):
        body = {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'channel': channel,
            'lines': [{'dish': self.dish.id, 'quantity': quantity, 'note': ''}],
        }
        if waiter_id:
            body['waiter_id'] = waiter_id
        return create_order(self.cashier, body)

    def test_owner_adds_a_waiter_and_sets_the_share(self):
        response = self.add_waiter()
        self.assertEqual(response.status_code, 201)
        waiter = Waiter.objects.get()
        self.assertEqual(waiter.name, 'Fazliddin')
        self.assertEqual(waiter.commission, Decimal('5.00'))
        self.assertIn('5', AuditEvent.objects.get(action='waiter.create').description)

    def test_a_cashier_may_pick_a_waiter_but_not_change_the_share(self):
        waiter = self.add_waiter().data
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        # Ro'yxatni ko'radi — buyurtmaga bog'lash uchun kerak.
        self.assertEqual(cashier.get('/api/v1/waiters/').status_code, 200)
        # Lekin foizni o'zgartira olmaydi: bu pul masalasi.
        self.assertEqual(
            cashier.patch(f'/api/v1/waiters/{waiter["id"]}/', {'commission': '50'}, format='json').status_code, 403)
        self.assertEqual(cashier.post('/api/v1/waiters/', {'name': 'O‘zi', 'commission': '90'}, format='json').status_code, 403)
        self.assertEqual(Waiter.objects.get().commission, Decimal('5.00'))

    def test_the_share_is_frozen_at_the_moment_of_sale(self):
        waiter = self.add_waiter(commission='5').data
        order = self.sell(waiter_id=waiter['id'])          # 200 000 × 5% = 10 000
        self.assertEqual(order.waiter_commission, Decimal('5.00'))
        self.assertEqual(order.waiter, 'Fazliddin')

        # Foiz keyin oshirilsa ham o'tgan buyurtma o'zgarmaydi.
        self.client.patch(f'/api/v1/waiters/{waiter["id"]}/', {'commission': '10'}, format='json')
        order.refresh_from_db()
        self.assertEqual(order.waiter_commission, Decimal('5.00'))
        # Yangi buyurtma yangi foizda ketadi.
        later = self.sell(waiter_id=waiter['id'])
        self.assertEqual(later.waiter_commission, Decimal('10.00'))

    def test_earnings_use_each_order_own_share(self):
        waiter = self.add_waiter(commission='5').data
        self.sell(waiter_id=waiter['id'])                       # 200 000 @ 5% = 10 000
        self.client.patch(f'/api/v1/waiters/{waiter["id"]}/', {'commission': '10'}, format='json')
        self.sell(waiter_id=waiter['id'], quantity=2)           # 100 000 @ 10% = 10 000

        today = timezone.localdate()
        data = self.client.get(f'/api/v1/reports/waiters/?start={today}&end={today}').data
        row = data['waiters'][0]
        self.assertEqual(row['name'], 'Fazliddin')
        self.assertEqual(row['orders'], 2)
        self.assertEqual(row['revenue'], '300000.00')
        # Har buyurtma o'z foizida: 10 000 + 10 000
        self.assertEqual(row['fee'], '20000.00')
        self.assertEqual(data['summary']['fees'], '20000.00')

    def test_orders_without_a_waiter_are_shown_separately(self):
        waiter = self.add_waiter().data
        self.sell(waiter_id=waiter['id'])
        self.sell()  # ofitsiantsiz
        today = timezone.localdate()
        summary = self.client.get(f'/api/v1/reports/waiters/?start={today}&end={today}').data['summary']
        self.assertEqual(summary['revenue'], '200000.00')
        self.assertEqual(summary['unassigned_revenue'], '200000.00')
        self.assertEqual(summary['unassigned_orders'], 1)

    def test_removing_a_waiter_keeps_the_sales_history(self):
        waiter = self.add_waiter().data
        order = self.sell(waiter_id=waiter['id'])
        self.assertEqual(self.client.delete(f'/api/v1/waiters/{waiter["id"]}/').status_code, 204)
        # O'chirilmaydi — faolsizlantiriladi, buyurtma bog'liqligi saqlanadi.
        self.assertFalse(Waiter.objects.get(pk=waiter['id']).active)
        order.refresh_from_db()
        self.assertEqual(order.waiter_ref_id, waiter['id'])
        # Faolsiz ofitsiantni yangi buyurtmaga bog'lab bo'lmaydi.
        with self.assertRaises(ValidationError):
            self.sell(waiter_id=waiter['id'])

    def test_a_duplicate_name_is_refused(self):
        self.add_waiter()
        self.assertEqual(self.add_waiter().status_code, 400)
        self.assertEqual(self.add_waiter(name='FAZLIDDIN').status_code, 400)

    def test_the_share_must_stay_between_zero_and_a_hundred(self):
        self.assertEqual(self.add_waiter(commission='-1').status_code, 400)
        self.assertEqual(self.add_waiter(commission='101').status_code, 400)
        self.assertEqual(self.add_waiter(commission='0').status_code, 201)


class SalesChannelTests(TestCase):
    """Uzum va Yandex savdosi zal savdosidan ajratiladi."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def sell(self, channel, method, quantity=2):
        return create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': method,
            'channel': channel,
            'lines': [{'dish': self.dish.id, 'quantity': quantity, 'note': ''}],
        })

    def test_a_hall_order_defaults_to_the_hall_channel(self):
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': self.dish.id, 'quantity': 1, 'note': ''}],
        })
        self.assertEqual(order.channel, 'hall')

    def test_finance_splits_the_channels_and_totals_them(self):
        self.sell('hall', 'cash')        # 100 000
        self.sell('uzum', 'uzum')        # 100 000
        self.sell('yandex', 'yandex', 1)  # 50 000
        data = self.client.get('/api/v1/finance/').data
        rows = {row['channel']: row for row in data['channels']}
        self.assertEqual(rows['hall']['revenue'], '100000.00')
        self.assertEqual(rows['uzum']['revenue'], '100000.00')
        self.assertEqual(rows['yandex']['revenue'], '50000.00')
        self.assertTrue(rows['uzum']['delivery'])
        self.assertFalse(rows['hall']['delivery'])
        # Jami hamma kanalni qamraydi.
        self.assertEqual(data['profit']['revenue'], '250000.00')

    def test_delivery_money_never_lands_in_the_cash_drawer(self):
        self.sell('hall', 'cash')      # 100 000 naqd
        self.sell('uzum', 'uzum')      # 100 000 Uzum hisobiga
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        day = cashier.get('/api/v1/shift/').data
        self.assertEqual(day['revenue'], '200000.00')
        # Kassada faqat naqd bo'lishi kerak.
        self.assertEqual(day['expected_cash'], '100000.00')

    def test_the_sales_board_shows_the_channel_split(self):
        self.sell('hall', 'cash')
        self.sell('uzum', 'uzum')
        today = timezone.localdate()
        board = self.client.get(f'/api/v1/sales/board/?start={today}&end={today}').data
        rows = {row['channel']: row for row in board['channels']}
        self.assertEqual(sorted(rows), ['hall', 'uzum'])
        self.assertEqual(rows['uzum']['orders'], 1)

    def test_a_delivery_order_cannot_be_rung_up_as_cash(self):
        # Uzum buyurtmasining puli platforma hisobiga tushadi. Naqd deb
        # belgilansa kassa qoldig'i shishib, smena yopishda tushuntirib
        # bo'lmaydigan farq chiqardi.
        response = self.client.post('/api/v1/orders/', {
            'key': str(uuid4()), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'channel': 'uzum',
            'lines': [{'dish': self.dish.id, 'quantity': 1, 'note': ''}],
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_an_open_delivery_bill_cannot_be_closed_with_cash_either(self):
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': '',
            'channel': 'yandex',
            'lines': [{'dish': self.dish.id, 'quantity': 1, 'note': ''}],
        })
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        self.assertEqual(
            cashier.post(f'/api/v1/orders/{order.id}/pay/', {'payment_method': 'cash'}).status_code, 400)
        # O'z platformasi orqali to'lansa qabul qilinadi.
        self.assertEqual(
            cashier.post(f'/api/v1/orders/{order.id}/pay/', {'payment_method': 'yandex'}).status_code, 200)
        # Kassada esa hech narsa qolmaydi.
        self.assertEqual(Decimal(cashier.get('/api/v1/shift/').data['expected_cash']), Decimal('0'))

    def test_a_hall_order_can_still_be_paid_by_any_method(self):
        # Zalda o'tirgan mijoz Uzum ilovasi bilan to'lashi mumkin — bu
        # yetkazib berish emas, shuning uchun cheklanmaydi.
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': '',
            'channel': 'hall',
            'lines': [{'dish': self.dish.id, 'quantity': 1, 'note': ''}],
        })
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        self.assertEqual(
            cashier.post(f'/api/v1/orders/{order.id}/pay/', {'payment_method': 'uzum'}).status_code, 200)

    def test_every_payment_method_is_listed_even_at_zero(self):
        # Sotuvsiz usul ro'yxatdan tushib qolsa, kassir «tekshirilmagan» deb
        # o'ylashi mumkin. Har biri doim turadi, noli bilan.
        self.sell('uzum', 'uzum')

        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        rows = {row['method']: row for row in cashier.get('/api/v1/shift/').data['breakdown']}
        self.assertEqual(sorted(rows), ['card', 'cash', 'click', 'terminal', 'uzum', 'yandex'])
        self.assertEqual(Decimal(rows['uzum']['amount']), Decimal('100000'))
        self.assertEqual(Decimal(rows['yandex']['amount']), Decimal('0'))
        self.assertEqual(rows['yandex']['count'], 0)
        # Kassada faqat naqd qoladi.
        self.assertTrue(rows['cash']['in_drawer'])
        self.assertFalse(rows['yandex']['in_drawer'])
        # Yig'indi kun tushumiga teng bo'lishi shart.
        self.assertEqual(
            sum(Decimal(row['amount']) for row in rows.values()),
            Decimal(cashier.get('/api/v1/shift/').data['revenue']))

    def test_the_till_sees_each_channel_counted_on_its_own(self):
        # Kassir stollar sahifasida Uzum va Yandex tugmalarida bugungi
        # tushumni ko'radi, shuning uchun kesim shu javobda kelishi kerak.
        self.sell('hall', 'cash')          # 100 000
        self.sell('uzum', 'uzum')          # 100 000
        self.sell('yandex', 'yandex', 1)   # 50 000

        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        summary = cashier.get('/api/v1/sales/summary/').data
        rows = {row['channel']: row for row in summary['today_by_channel']}

        # To'rt kanal ham doim keladi: savdosi bo'lmagani nol bo'lib turadi,
        # aks holda tugma ekrandan yo'qolib qolardi.
        self.assertEqual(sorted(rows), ['hall', 'takeaway', 'uzum', 'yandex'])
        self.assertEqual(Decimal(rows['uzum']['revenue']), Decimal('100000'))
        self.assertEqual(rows['uzum']['orders'], 1)
        self.assertEqual(Decimal(rows['yandex']['revenue']), Decimal('50000'))
        self.assertEqual(Decimal(rows['takeaway']['revenue']), Decimal('0'))
        self.assertEqual(rows['takeaway']['orders'], 0)
        self.assertTrue(rows['uzum']['delivery'])
        self.assertFalse(rows['takeaway']['delivery'])

        # Kanallar yig'indisi bugungi jamiga teng bo'lishi shart.
        self.assertEqual(
            sum(Decimal(row['revenue']) for row in summary['today_by_channel']),
            Decimal(summary['today']['revenue']))

    def test_an_unknown_channel_is_refused(self):
        response = self.client.post('/api/v1/orders/', {
            'key': str(uuid4()), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'channel': 'telegram',
            'lines': [{'dish': self.dish.id, 'quantity': 1, 'note': ''}],
        }, format='json')
        self.assertEqual(response.status_code, 400)


class DishPrepTests(TestCase):
    """Bugun tayyorlangan taomlar va ularning qoldig'i."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.manti = Dish.objects.create(branch=self.branch, category=self.category, name='Manti', price=Decimal('25000'))
        self.somsa = Dish.objects.create(branch=self.branch, category=self.category, name='Somsa', price=Decimal('12000'))
        self.client = APIClient()
        self.client.force_authenticate(self.cashier)

    def prepare(self, dish, quantity, note=''):
        return self.client.post('/api/v1/dish-prep/', {
            'lines': [{'dish': dish.id, 'quantity': quantity, 'note': note}],
        }, format='json')

    def sell(self, dish, quantity, method='cash'):
        return create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': method,
            'lines': [{'dish': dish.id, 'quantity': quantity, 'note': ''}],
        })

    def row(self, dish):
        data = self.client.get('/api/v1/dish-prep/').data
        return next(item for item in data['dishes'] if item['dish'] == dish.id)

    def test_what_is_left_is_what_was_made_minus_what_went_out(self):
        self.assertEqual(self.prepare(self.manti, 20).status_code, 201)
        self.sell(self.manti, 8)
        row = self.row(self.manti)
        self.assertEqual(row['prepared'], 20)
        self.assertEqual(row['sold'], 8)
        self.assertEqual(row['remaining'], 12)
        self.assertFalse(row['out'])
        self.assertFalse(row['low'])

    def test_a_second_batch_adds_rather_than_replaces(self):
        self.prepare(self.manti, 20, 'ertalab')
        self.prepare(self.manti, 15, 'tushda')
        self.assertEqual(self.row(self.manti)['prepared'], 35)
        # Ikkala yozuv ham tarixda qoladi: kun davomida nima qo'shilgani ko'rinsin.
        history = self.client.get('/api/v1/dish-prep/history/').data['rows']
        self.assertEqual([item['quantity'] for item in history], [15, 20])
        self.assertEqual(history[0]['note'], 'tushda')

    def test_a_dish_with_no_entry_cannot_be_sold_at_all(self):
        # Kiritilmagan degani «yo'q» degani: oshxona talon kelgach pishirmaydi,
        # u faqat ertalab tayyorlanganidan yig'adi.
        self.prepare(self.manti, 5)
        with self.assertRaises(ValidationError) as caught:
            self.sell(self.somsa, 1)
        self.assertIn('Somsa', str(caught.exception))
        self.assertIn('tayyorlanmagan', str(caught.exception))
        self.assertFalse(self.row(self.somsa)['tracked'])
        self.assertEqual(self.client.get('/api/v1/dish-prep/').data['summary']['tracked'], 1)

    def test_the_low_warning_is_proportional_to_the_batch(self):
        self.prepare(self.manti, 20)   # 20% -> 4 tada ogohlantiradi
        self.sell(self.manti, 15)
        self.assertFalse(self.row(self.manti)['low'])   # 5 qoldi
        self.sell(self.manti, 1)
        self.assertTrue(self.row(self.manti)['low'])    # 4 qoldi

        # Kichik partiyada chegara ham kichik: 3 tadan 1 ta qolganda.
        self.prepare(self.somsa, 3)
        self.sell(self.somsa, 2)
        self.assertTrue(self.row(self.somsa)['low'])

    def test_selling_stops_when_the_batch_runs_out(self):
        self.prepare(self.manti, 5)
        self.sell(self.manti, 5)
        row = self.row(self.manti)
        self.assertEqual(row['remaining'], 0)
        self.assertTrue(row['out'])
        self.assertFalse(row['low'])

        # Tugagan taomni sotib bo'lmaydi — yig'adigan narsa yo'q.
        with self.assertRaises(ValidationError) as caught:
            self.sell(self.manti, 1)
        self.assertIn('Manti', str(caught.exception))
        self.assertEqual(self.row(self.manti)['remaining'], 0)

        # Oshxona yana pishirsa sotuv darhol davom etadi.
        self.prepare(self.manti, 3)
        self.sell(self.manti, 2)
        self.assertEqual(self.row(self.manti)['remaining'], 1)

    def test_a_bill_cannot_ask_for_more_than_is_left(self):
        self.prepare(self.manti, 3)
        with self.assertRaises(ValidationError) as caught:
            self.sell(self.manti, 4)
        self.assertIn('3 ta qoldi', str(caught.exception))
        # Hisob umuman ochilmaydi: yarim buyurtma qabul qilinmaydi.
        self.assertEqual(self.row(self.manti)['sold'], 0)

    def test_an_open_bill_already_counts_as_gone(self):
        self.prepare(self.manti, 10)
        create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': '',
            'lines': [{'dish': self.manti.id, 'quantity': 4, 'note': ''}],
        })
        # Ovqat oshxonaga ketgan; sanalmasa qoldiq yolg'on ko'rsatardi.
        self.assertEqual(self.row(self.manti)['remaining'], 6)

    def test_a_cancelled_bill_gives_the_portions_back(self):
        self.prepare(self.manti, 10)
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': '',
            'lines': [{'dish': self.manti.id, 'quantity': 4, 'note': ''}],
        })
        self.assertEqual(self.row(self.manti)['remaining'], 6)
        response = self.client.post(f'/api/v1/orders/{order.id}/cancel/', {'reason': 'Mijoz ketdi'}, format='json')
        self.assertEqual(response.status_code, 200)
        # Oshxonaga BEKOR taloni ketgan - pishirilmaydi, porsiya qaytadi.
        self.assertEqual(self.row(self.manti)['remaining'], 10)

    def test_a_refund_does_not_give_the_portion_back(self):
        self.prepare(self.manti, 10)
        order = self.sell(self.manti, 4)
        owner = APIClient()
        owner.force_authenticate(self.owner)
        response = owner.post(f'/api/v1/orders/{order.id}/refund/', {'reason': 'Shikoyat'}, format='json')
        self.assertEqual(response.status_code, 200)
        # Pul qaytdi, lekin ovqat yeyilgan - porsiya qaytmaydi.
        self.assertEqual(self.row(self.manti)['remaining'], 6)

    def test_the_summary_counts_what_needs_attention(self):
        self.prepare(self.manti, 10)
        self.prepare(self.somsa, 10)
        self.sell(self.manti, 10)   # tugadi
        self.sell(self.somsa, 8)    # 2 qoldi -> kam
        summary = self.client.get('/api/v1/dish-prep/').data['summary']
        self.assertEqual(summary['tracked'], 2)
        self.assertEqual(summary['out'], 1)
        self.assertEqual(summary['low'], 1)
        self.assertEqual(summary['prepared'], 20)
        self.assertEqual(summary['sold'], 18)
        self.assertEqual(summary['remaining'], 2)

    def test_yesterday_batch_does_not_carry_into_today(self):
        # Kecha pishirilgani bugun sotilmaydi - har kun noldan boshlanadi.
        DishPrep.objects.create(
            branch=self.branch, dish=self.manti, actor=self.cashier,
            date=timezone.localdate() - timedelta(days=1), quantity=30,
        )
        self.assertFalse(self.row(self.manti)['tracked'])
        self.assertEqual(self.client.get('/api/v1/dish-prep/history/').data['rows'], [])

    def test_the_owner_sees_what_was_left_unsold(self):
        self.prepare(self.manti, 20)
        self.prepare(self.somsa, 6)
        self.sell(self.manti, 12)
        self.sell(self.somsa, 6)
        owner = APIClient()
        owner.force_authenticate(self.owner)
        data = owner.get('/api/v1/dish-prep/leftovers/').data
        # Sotilib bitgani ro'yxatda turmaydi - faqat qolgani.
        self.assertEqual([row['name'] for row in data['leftovers']], ['Manti'])
        self.assertEqual(data['leftovers'][0]['remaining'], 8)
        # Kassir bu ro'yxatni ko'rmaydi: bu egasining nazorati.
        self.assertEqual(self.client.get('/api/v1/dish-prep/leftovers/').status_code, 403)

    def test_entering_a_batch_is_written_to_the_activity_log(self):
        self.prepare(self.manti, 20, 'ertalab')
        entry = AuditEvent.objects.get(action='prep.record')
        self.assertEqual(entry.actor, self.cashier)
        self.assertIn('Manti', entry.description)
        self.assertIn('+20 porsiya', entry.description)

    def test_bad_input_is_refused(self):
        self.assertEqual(self.client.post('/api/v1/dish-prep/', {'lines': []}, format='json').status_code, 400)
        self.assertEqual(self.prepare(self.manti, 0).status_code, 400)
        self.assertEqual(self.prepare(self.manti, -5).status_code, 400)
        # Bitta taom ro'yxatda ikki marta kelsa qaysi biri to'g'ri ekani noaniq.
        self.assertEqual(self.client.post('/api/v1/dish-prep/', {
            'lines': [{'dish': self.manti.id, 'quantity': 5}, {'dish': self.manti.id, 'quantity': 3}],
        }, format='json').status_code, 400)
        self.assertEqual(self.client.post('/api/v1/dish-prep/', {
            'lines': [{'dish': 999999, 'quantity': 5}],
        }, format='json').status_code, 400)
        self.assertEqual(DishPrep.objects.count(), 0)

    def test_another_branch_dish_cannot_be_entered(self):
        other = Branch.objects.create(name='Two', slug='two')
        category = Category.objects.create(branch=other, name='Taom')
        theirs = Dish.objects.create(branch=other, category=category, name='Lagmon', price=Decimal('30000'))
        self.assertEqual(self.prepare(theirs, 5).status_code, 400)
        self.assertEqual(DishPrep.objects.count(), 0)

    def test_the_kitchen_role_cannot_reach_it(self):
        kitchen = APIClient()
        kitchen.force_authenticate(User.objects.create_user(
            'oshxona', password='test-only-long-password', role='kitchen', branch=self.branch))
        self.assertEqual(kitchen.get('/api/v1/dish-prep/').status_code, 403)
        self.assertEqual(kitchen.post('/api/v1/dish-prep/', {
            'lines': [{'dish': self.manti.id, 'quantity': 5}],
        }, format='json').status_code, 403)


class RecipePriceTests(TestCase):
    """Sotuv narxi retseptga emas, menyudagi taomga yoziladi."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Manti', price=Decimal('12000'))
        self.meat = Ingredient.objects.create(
            branch=self.branch, name='Go‘sht', unit='kg', quantity=Decimal('10'), unit_cost=Decimal('80000'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def create(self, **extra):
        body = {
            'dish': self.dish.id, 'name': 'Manti', 'yield_quantity': 1, 'yield_unit': 'porsiya',
            'active': True, 'lines': [{'ingredient': self.meat.id, 'quantity': '0.020'}],
        }
        body.update(extra)
        return self.client.post('/api/v1/recipes/', body, format='json')

    def test_the_price_comes_from_the_dish(self):
        recipe = self.create().data
        # 0.020 × 80 000 = 1 600 tannarx, taom narxi 12 000.
        self.assertEqual(Decimal(recipe['selling_price']), Decimal('12000'))
        self.assertEqual(Decimal(recipe['gross_profit']), Decimal('10400'))

    def test_a_price_sent_by_hand_is_ignored(self):
        # Eski mijoz yuborsa ham qabul qilinmaydi: narx bitta joyda turadi.
        recipe = self.create(selling_price='99000').data
        self.assertEqual(Decimal(recipe['selling_price']), Decimal('12000'))

    def test_changing_the_dish_price_moves_the_recipe_profit(self):
        created = self.create().data
        self.client.patch(f'/api/v1/dishes/{self.dish.id}/', {'price': '15000'}, format='json')
        recipe = self.client.get(f'/api/v1/recipes/{created["id"]}/').data
        # Narx menyuda o'zgardi — retsept foydasi o'zi ergashdi.
        self.assertEqual(Decimal(recipe['selling_price']), Decimal('15000'))
        self.assertEqual(Decimal(recipe['gross_profit']), Decimal('13400'))

    def test_a_preparation_without_a_dish_has_no_profit(self):
        # Bulyon kabi yarim tayyor mahsulot sotilmaydi, shuning uchun foydasi yo'q.
        recipe = self.create(dish=None, name='Bulyon').data
        self.assertEqual(Decimal(recipe['selling_price']), Decimal('0'))
        self.assertEqual(Decimal(recipe['gross_profit']), Decimal('0'))


class WholeDayConsistencyTests(TestCase):
    """Bir kun boshidan oxirigacha: hamma bo'lim bitta raqamni ko'rsatishi shart.

    Alohida testlar har bir bo'limni o'zicha tekshiradi. Bu test ularning
    ORASIDAGI bog'lanishni tekshiradi: kassa, sotuv taxtasi, moliya, smena,
    ofitsiant hisoboti va tayyor taomlar bitta kunning bir xil manzarasini
    ko'rsatishi kerak. Biri ikkinchisidan ajralib qolsa, egasi qaysi raqamga
    ishonishni bilmay qoladi — shuning uchun bu yerda hammasi taqqoslanadi.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch, first_name='Kassir')
        self.category = Category.objects.create(branch=self.branch, name='Milliy taomlar')
        self.owner_client = APIClient()
        self.owner_client.force_authenticate(self.owner)
        self.client = APIClient()
        self.client.force_authenticate(self.cashier)

    def sell(self, quantity, channel='hall', method='cash', waiter_id=None):
        body = {
            'key': uuid4(), 'table': '', 'waiter': '', 'channel': channel,
            'payment_method': method,
            'lines': [{'dish': self.dish_id, 'quantity': quantity, 'note': ''}],
        }
        if waiter_id:
            body['waiter_id'] = waiter_id
        return create_order(self.cashier, body)

    def test_one_full_day_adds_up_the_same_way_in_every_report(self):
        today = timezone.localdate()

        # ── Ertalab: egasi menyuni va ofitsiantni tayyorlaydi ──────────────
        meat = self.owner_client.post('/api/v1/ingredients/', {
            'name': 'Go‘sht', 'unit': 'kg', 'minimum': '2', 'unit_cost': '80000',
        }, format='json').data
        dish = self.owner_client.post('/api/v1/dishes/', {
            'name': 'Manti', 'category': self.category.id, 'description': '',
            'price': '12000', 'portion': '1 dona', 'available': True,
        }, format='json').data
        self.dish_id = dish['id']
        self.owner_client.post('/api/v1/recipes/', {
            'dish': dish['id'], 'name': 'Manti', 'yield_quantity': 1, 'yield_unit': 'porsiya',
            'active': True, 'lines': [{'ingredient': meat['id'], 'quantity': '0.020'}],
        }, format='json')
        waiter = self.owner_client.post('/api/v1/waiters/', {
            'name': 'Fazliddin', 'phone': '', 'commission': '5', 'active': True,
        }, format='json').data

        # Kassir omborni to'ldiradi: 10 kg go'sht 800 000 so'mga.
        self.client.post('/api/v1/stock/', {
            'key': str(uuid4()), 'ingredient': meat['id'], 'kind': 'receipt',
            'quantity': '10', 'cost_total': '800000', 'date': str(today), 'note': 'Bozordan',
        }, format='json')

        # Oshxona 20 ta manti pishirdi.
        self.assertEqual(self.client.post('/api/v1/dish-prep/', {
            'lines': [{'dish': dish['id'], 'quantity': 20, 'note': 'ertalabki partiya'}],
        }, format='json').status_code, 201)

        # ── Kun davomida: to'rt xil sotuv ──────────────────────────────────
        self.sell(4, 'hall', 'cash', waiter['id'])          # 48 000 naqd, ofitsiantli
        self.sell(2, 'uzum', 'uzum')                        # 24 000 Uzum hisobiga
        # Chegirma to'lovdan OLDIN qo'yiladi: ochiq hisobga, keyin to'lanadi.
        discounted = self.sell(3, 'takeaway', '')           # 36 000, hali ochiq
        self.assertEqual(self.client.post(
            f'/api/v1/orders/{discounted.id}/discount/',
            {'amount': '6000', 'reason': 'Doimiy mijoz'}, format='json').status_code, 200)
        self.assertEqual(self.client.post(
            f'/api/v1/orders/{discounted.id}/pay/', {'payment_method': 'card'}).status_code, 200)
        returned = self.sell(1, 'hall', 'cash')             # 12 000 naqd, keyin qaytariladi
        self.assertEqual(self.owner_client.post(
            f'/api/v1/orders/{returned.id}/refund/', {'reason': 'Mijoz shikoyat qildi'},
            format='json').status_code, 200)

        # Kunning haqiqati: 48 000 + 24 000 + 30 000 = 102 000.
        # Qaytarilgani tushumda YO'Q, chunki puli mijozga qaytdi.
        expected_revenue = Decimal('102000')

        # ── 1. Hamma hisobot bir xil tushumni ko'rsatadimi ─────────────────
        dashboard = self.owner_client.get('/api/v1/dashboard/').data
        board = self.owner_client.get(f'/api/v1/sales/board/?start={today}&end={today}').data
        finance = self.owner_client.get('/api/v1/finance/').data
        shift = self.client.get('/api/v1/shift/').data
        report = self.owner_client.get(f'/api/v1/reports/sales/?start={today}&end={today}').data

        self.assertEqual(Decimal(dashboard['revenue']), expected_revenue)
        self.assertEqual(Decimal(board['summary']['revenue']), expected_revenue)
        self.assertEqual(Decimal(finance['profit']['revenue']), expected_revenue)
        self.assertEqual(Decimal(shift['revenue']), expected_revenue)
        self.assertEqual(Decimal(report['summary']['revenue']), expected_revenue)

        # ── 1b. «Sof pul oqimi» ikkala sahifada bir xil formulada ────────
        # Ikkala kartaning nomi ham bir xil, demak raqami ham bir xil bo'lishi
        # shart: kirim − to'langan xarajat − ombor xaridi (800 000) − Uzum
        # ushlab qolgan ulush (24 000 ning 30% i = 7 200). Ushlangan pul hech
        # qachon hisobga tushmaydi, shuning uchun pul oqimida ham yo'q.
        platform_cut = Decimal('7200')
        # Ofitsiant xizmat haqi esa aksincha: mijozdan olindi va hali
        # ofitsiantga berilmadi, demak pul kassada turibdi.
        service = Decimal('2400')
        self.assertEqual(Decimal(finance['profit']['platform_fee']), platform_cut)
        self.assertEqual(Decimal(finance['service']['collected']), service)
        self.assertEqual(Decimal(finance['service']['owed']), service)
        self.assertEqual(
            Decimal(dashboard['net_cash']),
            expected_revenue + service - Decimal('800000') - platform_cut)
        self.assertEqual(Decimal(finance['cash']['net']), Decimal(dashboard['net_cash']))
        # Ko'prik foydadan pulga aniq olib borishi kerak.
        self.assertEqual(Decimal(finance['cash']['bridge']), Decimal(finance['cash']['net']))

        # ── 2. Kanal kesimi jamiga teng bo'lishi shart ────────────────────
        channels = {row['channel']: Decimal(row['revenue']) for row in finance['channels']}
        self.assertEqual(channels, {
            'hall': Decimal('48000'), 'uzum': Decimal('24000'), 'takeaway': Decimal('30000'),
        })
        self.assertEqual(sum(channels.values()), expected_revenue)
        board_channels = {row['channel']: Decimal(row['revenue']) for row in board['channels']}
        self.assertEqual(board_channels, channels)

        # ── 3. Kassada faqat naqd qolishi kerak ──────────────────────────
        # 48 000 naqd tushdi; ustiga ofitsiant xizmat haqi 5% = 2 400 —
        # mijoz uni ham naqd to'ladi, demak u ham kassada yotadi.
        # Qaytarilgan 12 000 kassadan chiqdi; karta va Uzum puli kassaga
        # umuman tushmaydi.
        self.assertEqual(Decimal(shift['service']), Decimal('2400'))
        self.assertEqual(Decimal(shift['expected_cash']), Decimal('50400'))
        # Tushum esa o'zgarmaydi: xizmat haqi restoranning puli emas.
        self.assertEqual(Decimal(shift['revenue']), expected_revenue)
        drawer = {row['method']: row['in_drawer'] for row in shift['breakdown']}
        self.assertTrue(drawer['cash'])
        self.assertFalse(drawer['card'])
        self.assertFalse(drawer['uzum'])

        # ── 4. Ofitsiant ulushi o'z hisobidan hisoblanadi ─────────────────
        earnings = self.owner_client.get(f'/api/v1/reports/waiters/?start={today}&end={today}').data
        self.assertEqual(earnings['waiters'][0]['name'], 'Fazliddin')
        self.assertEqual(Decimal(earnings['waiters'][0]['revenue']), Decimal('48000'))
        self.assertEqual(Decimal(earnings['waiters'][0]['fee']), Decimal('2400'))  # 5%
        # Ofitsiantsiz sotilgani ham ko'rinadi: 24 000 + 30 000.
        self.assertEqual(Decimal(earnings['summary']['unassigned_revenue']), Decimal('54000'))

        # ── 5. Masalliq ANIQ BIR MARTA hisobdan chiqishi shart ───────────
        # 10 porsiya sotildi (qaytarilgani ham pishirilgan edi) × 20 g = 200 g.
        consumed = StockMovement.objects.filter(
            branch=self.branch, kind='sale_consumption',
        ).aggregate(total=Sum('quantity'))['total']
        self.assertEqual(consumed, Decimal('0.200'))

        # ── 6. Tayyor taomlar qoldig'i sotuv bilan kamaygan ──────────────
        prep = self.client.get('/api/v1/dish-prep/').data
        row = next(item for item in prep['dishes'] if item['dish'] == dish['id'])
        self.assertEqual(row['prepared'], 20)
        self.assertEqual(row['sold'], 10)        # qaytarilgan porsiya ham ketgan
        self.assertEqual(row['remaining'], 10)
        self.assertFalse(row['out'])

        # ── 7. Tannarx va foyda zanjiri yopiladimi ───────────────────────
        # 9 ta to'langan porsiya × 1 600 = 14 400 tannarx.
        self.assertEqual(Decimal(finance['profit']['cogs']), Decimal('14400'))
        self.assertEqual(
            Decimal(finance['profit']['gross_profit']),
            expected_revenue - Decimal('14400'),
        )

        # ── 8. Bekor va qaytarilgan hisob oshxona taxtasida turmaydi ─────
        kitchen = APIClient()
        kitchen.force_authenticate(User.objects.create_user(
            'oshxona', password='test-only-long-password', role='kitchen', branch=self.branch))
        self.assertNotIn(returned.id, [item['id'] for item in kitchen.get('/api/v1/kitchen/orders/').data])

        # ── 9. Smena yopilgach kun muzlaydi va farq yoziladi ─────────────
        closed = self.client.post('/api/v1/shift/', {'counted_cash': '49400', 'note': 'Sanaldi'}, format='json')
        self.assertEqual(closed.status_code, 201)
        self.assertEqual(Decimal(closed.data['difference']), Decimal('-1000'))
        self.assertEqual(Decimal(closed.data['expected_cash']), Decimal('50400'))
        # Yopilgandan keyin ham tushum o'zgarmaydi.
        self.assertEqual(
            Decimal(self.owner_client.get('/api/v1/dashboard/').data['revenue']), expected_revenue)


class DiscountInReportsTests(TestCase):
    """Chegirma hisobotlarda ham ko'rinishi: aks holda «Sotuv» kassaga tushmagan
    pulni ko'rsatib, «Moliya» bilan ajralib ketadi."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.osh = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.choy = Dish.objects.create(branch=self.branch, category=self.category, name='Choy', price=Decimal('10000'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def bill_with_discount(self, amount):
        # 2×50 000 + 3×10 000 = 130 000 — chegirma teng bo'linmaydi.
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': '',
            'lines': [
                {'dish': self.osh.id, 'quantity': 2, 'note': ''},
                {'dish': self.choy.id, 'quantity': 3, 'note': ''},
            ],
        })
        self.client.post(f'/api/v1/orders/{order.id}/discount/',
                         {'amount': str(amount), 'reason': 'Tug‘ilgan kun'}, format='json')
        self.client.post(f'/api/v1/orders/{order.id}/pay/', {'payment_method': 'cash'})
        order.refresh_from_db()
        return order

    def test_the_sales_board_shows_what_was_taken_not_the_menu_price(self):
        order = self.bill_with_discount(7000)
        self.assertEqual(order.total, Decimal('123000'))
        today = timezone.localdate()
        board = self.client.get(f'/api/v1/sales/board/?start={today}&end={today}').data
        self.assertEqual(Decimal(board['summary']['revenue']), Decimal('123000'))
        # Taomlar kesimi ham jamiga teng bo'lishi kerak — tiyin yo'qolmaydi.
        self.assertEqual(
            sum(Decimal(row['revenue']) for row in board['dishes']), Decimal('123000'))
        self.assertEqual(
            sum(Decimal(row['revenue']) for row in board['channels']), Decimal('123000'))
        self.assertEqual(
            sum(Decimal(row['revenue']) for row in board['methods']), Decimal('123000'))

    def test_the_sales_report_and_its_excel_share_the_same_figure(self):
        self.bill_with_discount(7000)
        today = timezone.localdate()
        report = self.client.get(f'/api/v1/reports/sales/?start={today}&end={today}').data
        self.assertEqual(Decimal(report['summary']['revenue']), Decimal('123000'))
        # Har qator alohida taqsimlanadi, lekin yig'indi aniq teng chiqadi.
        self.assertEqual(
            sum(Decimal(row['revenue']) for row in report['dishes']), Decimal('123000'))
        self.assertEqual(
            sum(Decimal(row['revenue']) for row in report['categories']), Decimal('123000'))
        self.assertEqual(
            sum(Decimal(row['revenue']) for row in report['trend']), Decimal('123000'))
        # Excel ham shu hisobdan chiqadi, demak u ham to'g'ri.
        self.assertEqual(
            self.client.get(f'/api/v1/reports/sales/export/?start={today}&end={today}').status_code, 200)

    def test_every_money_screen_agrees_after_a_discount(self):
        self.bill_with_discount(7000)
        today = timezone.localdate()
        figures = {
            'dashboard': Decimal(self.client.get('/api/v1/dashboard/').data['revenue']),
            'board': Decimal(self.client.get(f'/api/v1/sales/board/?start={today}&end={today}').data['summary']['revenue']),
            'report': Decimal(self.client.get(f'/api/v1/reports/sales/?start={today}&end={today}').data['summary']['revenue']),
            'finance': Decimal(self.client.get('/api/v1/finance/').data['profit']['revenue']),
        }
        self.assertEqual(set(figures.values()), {Decimal('123000')}, figures)

    def test_cost_coverage_never_exceeds_a_hundred_percent(self):
        # Qamrov ulushi surat bilan maxrajni bir xil bazadan olishi shart.
        # Menyu narxi chegirmali tushumga bo'linsa, ulush 100% dan oshib,
        # «tannarx qamrovi past» ogohlantirishi o'chib qolardi.
        recipe = Recipe.objects.create(
            branch=self.branch, dish=self.osh, name='Osh', yield_quantity=Decimal('1'))
        meat = Ingredient.objects.create(
            branch=self.branch, name='Go‘sht', unit='kg', quantity=Decimal('50'), unit_cost=Decimal('80000'))
        RecipeLine.objects.create(
            recipe=recipe, ingredient=meat, quantity=Decimal('0.100'), batch_cost=Decimal('8000'))

        self.bill_with_discount(7000)
        data = self.client.get('/api/v1/finance/').data
        share = Decimal(data['coverage']['share'])
        self.assertLessEqual(share, Decimal('100'))
        # Oshning qamrab olingan tushumi ham chegirma ayrilgan qiymatda.
        self.assertEqual(Decimal(data['coverage']['covered_revenue']), Decimal('94615.38'))

    def test_a_bill_without_a_discount_keeps_its_exact_menu_price(self):
        # Chegirmasiz hisobda bo'lish umuman bajarilmaydi — aniqlik yo'qolmasin.
        create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': self.osh.id, 'quantity': 3, 'note': ''}],
        })
        today = timezone.localdate()
        board = self.client.get(f'/api/v1/sales/board/?start={today}&end={today}').data
        self.assertEqual(Decimal(board['summary']['revenue']), Decimal('150000'))
        self.assertEqual(board['dishes'][0]['revenue'], '150000.00')

    def test_a_dish_filter_still_shows_what_that_dish_actually_brought(self):
        # 2×50 000 (Osh) + 3×10 000 (Choy) = 130 000, chegirma 7 000 -> 123 000.
        # Osh ulushi: 100 000/130 000 × 123 000 = 94 615.38
        self.bill_with_discount(7000)
        today = timezone.localdate()
        board = self.client.get(
            f'/api/v1/sales/board/?start={today}&end={today}&dish={self.osh.id}').data
        self.assertEqual(Decimal(board['summary']['revenue']), Decimal('94615.38'))
        self.assertEqual(board['dishes'][0]['dish'], 'Osh')
        self.assertEqual(Decimal(board['dishes'][0]['revenue']), Decimal('94615.38'))

        report = self.client.get(
            f'/api/v1/reports/sales/?start={today}&end={today}&dish={self.osh.id}').data
        self.assertEqual(Decimal(report['summary']['revenue']), Decimal('94615.38'))

    def test_only_the_cashier_who_gave_the_discount_carries_it(self):
        # «Faqat mening savdolarim» filtri ham chegirmani hisobga olishi kerak.
        self.bill_with_discount(7000)
        today = timezone.localdate()
        cashier_client = APIClient()
        cashier_client.force_authenticate(self.cashier)
        mine = cashier_client.get(
            f'/api/v1/sales/board/?start={today}&end={today}&mine=true').data
        self.assertEqual(Decimal(mine['summary']['revenue']), Decimal('123000'))
        self.assertEqual(Decimal(mine['cashiers'][0]['revenue']), Decimal('123000'))


class DiscountedLineRemovalTests(TestCase):
    """Chegirmali hisobdan qator olib tashlash summani manfiyga tushirmasligi kerak."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.osh = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.choy = Dish.objects.create(branch=self.branch, category=self.category, name='Choy', price=Decimal('10000'))
        self.client = APIClient()
        self.client.force_authenticate(self.cashier)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def open_bill(self):
        # 2×50 000 + 3×10 000 = 130 000
        return create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': '',
            'lines': [
                {'dish': self.osh.id, 'quantity': 2, 'note': ''},
                {'dish': self.choy.id, 'quantity': 3, 'note': ''},
            ],
        })

    def test_removing_a_line_under_a_big_discount_is_refused_not_crashed(self):
        order = self.open_bill()
        self.client.post(f'/api/v1/orders/{order.id}/discount/',
                         {'amount': '100000', 'reason': 'Tanishga'}, format='json')
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal('30000'))

        # Oshni olib tashlasa qolgani 30 000, chegirma esa 100 000 — summa
        # manfiy bo'lardi. Kassir 500 xatosi emas, tushunarli javob olishi kerak.
        osh = order.lines.get(name='Osh')
        response = self.client.delete(f'/api/v1/orders/{order.id}/lines/{osh.id}/')
        self.assertEqual(response.status_code, 409)
        # Xabar aniq bo'lishi kerak: kassir nima qilishini bilsin.
        self.assertIn('chegirma', str(response.data).lower())
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal('30000'))
        self.assertEqual(order.lines.count(), 2)

    def test_a_line_can_still_be_removed_when_the_discount_leaves_room(self):
        order = self.open_bill()
        self.client.post(f'/api/v1/orders/{order.id}/discount/',
                         {'amount': '5000', 'reason': 'Doimiy mijoz'}, format='json')
        osh = order.lines.get(name='Osh')
        response = self.client.delete(f'/api/v1/orders/{order.id}/lines/{osh.id}/')
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        # Qolgani 30 000, chegirma 5 000 -> 25 000.
        self.assertEqual(order.total, Decimal('25000'))
        self.assertEqual(order.discount, Decimal('5000'))

    def test_removing_a_line_without_a_discount_is_unchanged(self):
        order = self.open_bill()
        osh = order.lines.get(name='Osh')
        self.assertEqual(self.client.delete(f'/api/v1/orders/{order.id}/lines/{osh.id}/').status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal('30000'))


class BadInputStaysFourHundredTests(TestCase):
    """Noto'g'ri kiritilgan ma'lumot 500 emas, tushunarli 400 bo'lishi kerak.

    500 xatosi foydalanuvchiga nima qilishni aytmaydi va serverda kutilmagan
    istisno bo'lib qoladi — ya'ni haqiqiy nosozlikni jurnalda ko'rish qiyinlashadi.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.osh = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.choy = Dish.objects.create(branch=self.branch, category=self.category, name='Choy', price=Decimal('10000'))
        self.meat = Ingredient.objects.create(
            branch=self.branch, name='Go‘sht', unit='kg', quantity=Decimal('10'), unit_cost=Decimal('80000'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def recipe(self, dish, name):
        return self.client.post('/api/v1/recipes/', {
            'dish': dish.id, 'name': name, 'yield_quantity': 1, 'yield_unit': 'porsiya',
            'active': True, 'lines': [{'ingredient': self.meat.id, 'quantity': '0.020'}],
        }, format='json')

    def test_a_repeated_recipe_name_is_refused_not_crashed(self):
        self.assertEqual(self.recipe(self.osh, 'Bir xil').status_code, 201)
        response = self.recipe(self.choy, 'Bir xil')
        self.assertEqual(response.status_code, 400)
        self.assertIn('retsept', str(response.data).lower())
        # Katta-kichik harf farqi ham himoyani chetlab o'tmaydi.
        self.assertEqual(self.recipe(self.choy, 'BIR XIL').status_code, 400)

    def test_a_recipe_can_keep_its_own_name_while_being_edited(self):
        created = self.recipe(self.osh, 'Osh').data
        response = self.client.patch(f'/api/v1/recipes/{created["id"]}/',
                                     {'name': 'Osh', 'yield_quantity': 2}, format='json')
        self.assertEqual(response.status_code, 200)

    def test_an_ingredient_can_keep_its_own_name_while_being_edited(self):
        # Faqat narxni o'zgartirmoqchi bo'lgan odam «bu mahsulot mavjud»
        # xabariga urilib qolmasligi kerak.
        response = self.client.patch(f'/api/v1/ingredients/{self.meat.id}/',
                                     {'name': 'Go‘sht', 'unit_cost': '90000'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.meat.refresh_from_db()
        self.assertEqual(self.meat.unit_cost, Decimal('90000.0000'))
        # Boshqa mahsulotning nomini olib bo'lmaydi.
        other = Ingredient.objects.create(branch=self.branch, name='Un', unit='kg', quantity=Decimal('5'))
        self.assertEqual(self.client.patch(f'/api/v1/ingredients/{other.id}/',
                                           {'name': 'go‘sht'}, format='json').status_code, 400)

    def test_an_impossible_month_is_refused_everywhere(self):
        # 0000-01 «year 0 is out of range» bilan 500 berardi.
        for path in ('/api/v1/payroll/', '/api/v1/finance/', '/api/v1/dashboard/'):
            for month in ('0000-01', '2026-13', '2026-00', '9999-01'):
                response = self.client.get(f'{path}?month={month}')
                self.assertEqual(response.status_code, 400, f'{path} {month} -> {response.status_code}')

    def test_a_real_month_still_works_everywhere(self):
        month = timezone.localdate().strftime('%Y-%m')
        for path in ('/api/v1/payroll/', '/api/v1/finance/', '/api/v1/dashboard/'):
            self.assertEqual(self.client.get(f'{path}?month={month}').status_code, 200, path)


class TranslationCoverageTests(SimpleTestCase):
    """Uch til to'liq ishlashini qo'riqlaydi.

    Bu test frontend lug'atlarini o'qiydi. G'alati ko'rinishi mumkin, lekin
    aynan shu chegarada xato tug'iladi: server o'zbekcha yorliq yuboradi
    («Naqd», «Taom tayyorlandi»), ekran uni tarjima qilishi kerak. Ikki tomon
    alohida o'zgarganda hech qanday tekshiruv ishlamaydi — natijada ruscha
    sahifada o'zbekcha so'z paydo bo'ladi. Shuning uchun tekshiruv shu yerda.

    Ikkinchi xato turi: sanoq shakli bor kalit t() bilan chaqirilsa, ekranda
    «7 шт.|7 шт.|7 шт.» chiqadi — chunki t() qiymatni xom qaytaradi.
    """

    FRONTEND = Path(settings.BASE_DIR).parent / 'xonim_frontend' / 'src'
    # Brend nomlari hamma tilda bir xil yoziladi, tarjima talab qilmaydi.
    BRANDS = {'Uzum', 'Yandex', 'Click'}
    QUOTED = "(?:'([^']*)'|\"([^\"]*)\")"
    FORMS = {'ru': 3, 'en': 2}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        entry = re.compile(r"^  " + cls.QUOTED + r":\s*" + cls.QUOTED + r",\s*$", re.M)
        cls.catalogues = {}
        for lang in cls.FORMS:
            path = cls.FRONTEND / 'i18n' / f'{lang}.ts'
            text = path.read_text(encoding='utf-8')
            cls.catalogues[lang] = {
                (match.group(1) if match.group(1) is not None else match.group(2)):
                (match.group(3) if match.group(3) is not None else match.group(4))
                for match in entry.finditer(text)
            }

    def setUp(self):
        if not self.FRONTEND.exists():
            self.skipTest('frontend manbasi yonida emas')

    def test_every_label_the_server_sends_has_a_translation(self):
        from operations.models import (
            ORDER_STATUS_LABELS,
            SALE_CHANNEL_LABELS,
            SALE_PAYMENT_LABELS,
            Ingredient,
        )
        from users.models import AUDIT_GROUPS, AUDIT_LABELS

        # Birliklar modeldan olinadi: qo'lda yozilsa ro'yxat sekin-asta
        # haqiqatdan uzoqlashadi va test o'zi yolg'on tinchlik beradi.
        units = {value for value, _ in Ingredient._meta.get_field('unit').choices}
        expected = (
            set(AUDIT_LABELS.values()) | set(AUDIT_GROUPS.values())
            | set(SALE_PAYMENT_LABELS.values()) | set(SALE_CHANNEL_LABELS.values())
            | set(ORDER_STATUS_LABELS.values())
            | {'Superadmin', 'Kassir', 'Oshxona'}
            | units
        ) - self.BRANDS

        for lang, catalogue in self.catalogues.items():
            missing = sorted(label for label in expected if label not in catalogue)
            self.assertEqual(missing, [], f'{lang}: tarjimasiz yorliqlar')

    def test_a_counted_key_is_never_read_through_the_singular_helper(self):
        call = re.compile(r"(?<![A-Za-z0-9_.])(tn?)\(\s*" + self.QUOTED)
        wrong = []
        for path in self.FRONTEND.rglob('*.ts*'):
            if 'i18n' in path.parts:
                continue
            for match in call.finditer(path.read_text(encoding='utf-8')):
                key = match.group(2) if match.group(2) is not None else match.group(3)
                for lang, catalogue in self.catalogues.items():
                    value = catalogue.get(key)
                    if match.group(1) == 't' and value and '|' in value:
                        wrong.append(f'{lang} · {path.name} · t({key!r})')
                    if match.group(1) == 'tn' and value and value.count('|') + 1 != self.FORMS[lang]:
                        wrong.append(f'{lang} · {path.name} · tn({key!r}) shakllari yetarli emas')
        self.assertEqual(sorted(set(wrong)), [], 'sanoq shakllari noto‘g‘ri ishlatilgan')

    def test_both_dictionaries_hold_the_same_keys(self):
        russian, english = self.catalogues['ru'], self.catalogues['en']
        self.assertEqual(sorted(set(russian) - set(english)), [], 'faqat ruschada bor')
        self.assertEqual(sorted(set(english) - set(russian)), [], 'faqat inglizchada bor')

    def test_no_dictionary_key_is_mangled_by_escaping(self):
        # Ilgari ikki kalit teskari sleshlar zanjiri bilan buzilgan edi va
        # hech qachon mos kelmagan — ya'ni matn hech bir tilda tarjima
        # qilinmagan, lekin buni hech narsa ko'rsatmagan.
        for lang, catalogue in self.catalogues.items():
            broken = [key for key in catalogue if '\\\\' in key]
            self.assertEqual(broken, [], f'{lang}: buzilgan kalitlar')


class ServerSpeaksTheRequestedLanguageTests(TestCase):
    """Server xabarlari Accept-Language ga bo'ysunishi kerak.

    Lug'atda tarjima bo'lsa-yu, `_()` chaqirilmasa — xabar baribir o'zbekcha
    keladi va buni hech narsa ko'rsatmaydi. Shuning uchun eng ko'p
    uchraydigan uch xabar shu yerda tekshiriladi.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.cashier = User.objects.create_user(
            'cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.osh = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.client = APIClient()
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def test_a_failed_login_answers_in_the_requested_language(self):
        response = self.client.post(
            '/api/v1/auth/login/', {'username': 'cashier', 'password': 'wrong'},
            format='json', HTTP_ACCEPT_LANGUAGE='ru')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['detail'], 'Неверный логин или пароль.')

    def test_a_conflict_answers_in_the_requested_language(self):
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': '',
            'lines': [{'dish': self.osh.id, 'quantity': 1, 'note': ''}],
        })
        self.client.force_authenticate(self.cashier)
        only = order.lines.first()
        # Oxirgi qatorni olib tashlab bo'lmaydi -> Conflict.
        response = self.client.delete(
            f'/api/v1/orders/{order.id}/lines/{only.id}/', HTTP_ACCEPT_LANGUAGE='ru')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(str(response.data['detail']), 'Это последняя строка. Отмените счёт целиком.')

    def test_a_validation_error_answers_in_english_too(self):
        self.client.force_authenticate(self.cashier)
        response = self.client.post('/api/v1/dish-prep/', {
            'lines': [{'dish': self.osh.id, 'quantity': 5}, {'dish': self.osh.id, 'quantity': 3}],
        }, format='json', HTTP_ACCEPT_LANGUAGE='en')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Enter each dish only once.', str(response.data))

    def test_uzbek_stays_the_default_when_nothing_is_asked_for(self):
        response = self.client.post(
            '/api/v1/auth/login/', {'username': 'cashier', 'password': 'wrong'}, format='json')
        self.assertEqual(response.data['detail'], 'Login yoki parol noto‘g‘ri.')


class PrintingStaysOutsideTheTransactionTests(TransactionTestCase):
    """Printer javob bermasa butun kassa to'xtab qolmasligi kerak.

    Talon chop etish tarmoq amali: ulanish 4, yuborish 6 soniya kutadi. Agar
    u tranzaksiya ichida bajarilsa, taom qatorlari `select_for_update` bilan
    qulflangan holda o'sha vaqt ushlab turiladi — SQLite'da esa butun baza
    yozuvga yopiladi. Ya'ni oshxona printeri o'chib qolsa, hech kim hech narsa
    sota olmaydi.

    Shuning uchun bu test chop etish chaqirilgan paytda tranzaksiya OCHIQ
    EMASLIGINI tekshiradi. TransactionTestCase kerak: oddiy TestCase har bir
    testni tranzaksiyaga o'raydi va tekshiruv ma'nosini yo'qotadi.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.cashier = User.objects.create_user(
            'cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.osh = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def test_the_kitchen_ticket_is_printed_after_the_transaction_closes(self):
        seen = []

        def watcher(order, lines=None, *, addition=False):
            seen.append(connection.in_atomic_block)
            return []

        with patch('operations.services.print_prep_tickets', watcher):
            order = create_order(self.cashier, {
                'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
                'lines': [{'dish': self.osh.id, 'quantity': 2, 'note': ''}],
            })
        self.assertEqual(seen, [False], 'talon tranzaksiya ichida chop etilyapti')
        self.assertEqual(order.total, Decimal('100000'))

    def test_the_addition_ticket_is_printed_after_the_transaction_closes(self):
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': '',
            'lines': [{'dish': self.osh.id, 'quantity': 1, 'note': ''}],
        })
        seen = []

        def watcher(order, lines=None, *, addition=False):
            seen.append(connection.in_atomic_block)
            return []

        with patch('operations.services.print_prep_tickets', watcher):
            append_order_lines(self.cashier, order.id, {
                'key': uuid4(), 'lines': [{'dish': self.osh.id, 'quantity': 1, 'note': ''}],
            })
        self.assertEqual(seen, [False], 'qo‘shimcha taloni tranzaksiya ichida chop etilyapti')

    def test_a_retried_request_does_not_print_the_ticket_twice(self):
        # Talon endi tranzaksiyadan tashqarida chiqadi, ya'ni takroriy so'rov
        # uni ikkinchi marta chiqarib yuborishi mumkin edi.
        key = uuid4()
        body = {'key': key, 'table': '', 'waiter': '', 'payment_method': 'cash',
                'lines': [{'dish': self.osh.id, 'quantity': 1, 'note': ''}]}
        printed = []
        with patch('operations.services.print_prep_tickets', lambda *a, **k: printed.append(1) or []):
            first = create_order(self.cashier, dict(body))
            second = create_order(self.cashier, dict(body))
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(printed), 1)

    def test_a_retried_addition_does_not_print_twice_either(self):
        order = create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': '',
            'lines': [{'dish': self.osh.id, 'quantity': 1, 'note': ''}],
        })
        batch = uuid4()
        printed = []
        with patch('operations.services.print_prep_tickets', lambda *a, **k: printed.append(1) or []):
            append_order_lines(self.cashier, order.id, {
                'key': batch, 'lines': [{'dish': self.osh.id, 'quantity': 1, 'note': ''}]})
            append_order_lines(self.cashier, order.id, {
                'key': batch, 'lines': [{'dish': self.osh.id, 'quantity': 1, 'note': ''}]})
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal('100000'))
        self.assertEqual(len(printed), 1)


class RecipeIsAnEstimateNotALawTests(TestCase):
    """Retsept ombordan ayiradi, lekin sotuvni HECH QACHON to'xtatmaydi.

    Bir taomga ba'zida retseptdan ko'proq, ba'zida kamroq ketadi — shuning
    uchun retsept bo'yicha hisoblangan qoldiq taxmin bo'lib qoladi. Mijoz
    oldida turgan kassir shu taxminiy raqam sababli pul ololmay qolishi mumkin
    emas. Haqiqiy sarfni admin kunlik kiritadi, superadmin esa ikkalasini
    solishtiradi.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.osh = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        # Omborda atigi 0.5 kg go'sht bor, har porsiyaga 0.2 kg ketadi.
        self.meat = Ingredient.objects.create(
            branch=self.branch, name='Go‘sht', unit='kg', quantity=Decimal('0.5'), unit_cost=Decimal('80000'))
        recipe = Recipe.objects.create(branch=self.branch, dish=self.osh, name='Osh', yield_quantity=Decimal('1'))
        RecipeLine.objects.create(
            recipe=recipe, ingredient=self.meat, quantity=Decimal('0.200'), batch_cost=Decimal('16000'))
        prepare(self.cashier, self.osh)
        self.client = APIClient()
        self.client.force_authenticate(self.cashier)

    def sell(self, quantity):
        return create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': 'cash',
            'lines': [{'dish': self.osh.id, 'quantity': quantity, 'note': ''}],
        })

    def test_a_sale_goes_through_even_when_the_recipe_wants_more_than_there_is(self):
        # 5 porsiya = 1 kg kerak, omborda 0.5 kg. Sotuv baribir o'tadi.
        order = self.sell(5)
        self.assertEqual(order.status, 'paid')
        self.assertEqual(order.total, Decimal('250000'))
        self.meat.refresh_from_db()
        # Qoldiq minusga tushadi — bu yashiriladigan emas, ko'rsatiladigan fakt.
        self.assertEqual(self.meat.quantity, Decimal('-0.500'))

    def test_the_shortage_is_written_to_the_activity_log(self):
        self.sell(5)
        entry = AuditEvent.objects.filter(action='stock.shortage').first()
        self.assertIsNotNone(entry, 'kamchilik jurnalga tushmadi')
        self.assertIn('Go‘sht', entry.description)
        self.assertIn('retsept 1 kg so‘radi', entry.description)
        self.assertIn('qoldiq 0.5 edi', entry.description)

    def test_a_sale_within_the_stock_writes_no_shortage(self):
        self.sell(2)  # 0.4 kg, omborda 0.5 kg bor
        self.meat.refresh_from_db()
        self.assertEqual(self.meat.quantity, Decimal('0.100'))
        self.assertFalse(AuditEvent.objects.filter(action='stock.shortage').exists())

    def test_the_cost_is_still_taken_from_the_recipe(self):
        # Retsept qat'iy emas, lekin tannarx hisobi o'zgarmaydi: 0.2 × 80 000.
        order = self.sell(1)
        line = order.lines.get()
        self.assertEqual(line.cost_per_unit, Decimal('16000.00'))
        self.assertEqual(line.cost_total, Decimal('16000.00'))

    def test_writing_stock_off_by_hand_is_still_refused_when_short(self):
        # Qo'lda chiqim — bu odamning qarori, xato yozuvdan himoya qoladi.
        response = self.client.post('/api/v1/stock/', {
            'key': str(uuid4()), 'ingredient': self.meat.id, 'kind': 'consumption',
            'quantity': '5', 'date': str(timezone.localdate()), 'note': 'Isrof',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.meat.refresh_from_db()
        self.assertEqual(self.meat.quantity, Decimal('0.500'))

    def test_the_owner_can_see_how_far_the_estimate_drifted(self):
        self.sell(5)
        owner = APIClient()
        owner.force_authenticate(self.owner)
        rows = owner.get('/api/v1/ingredients/').data['results']
        meat = next(row for row in rows if row['name'] == 'Go‘sht')
        # Manfiy qoldiq API orqali ham ko'rinadi — yashirilmaydi.
        self.assertEqual(Decimal(meat['quantity']), Decimal('-0.500'))


class StockHistoryIsForTheOwnerTests(TestCase):
    """Ombor harakatlari tarixi — egasining nazorat vositasi.

    Kassir kirim va chiqim kiritadi, bu uning kundalik ishi. Lekin tarixdan
    qaysi taomga qancha masalliq ketgani va retsept bilan haqiqiy sarf
    orasidagi farq ko'rinadi — bu egasining ko'zi. Ekrandan yashirish yetarli
    emas: so'rov ham rad etilishi kerak, aks holda manzilni qo'lda yozgan
    kassir baribir ko'radi.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.flour = Ingredient.objects.create(
            branch=self.branch, name='Un', unit='kg', quantity=Decimal('0'), unit_cost=Decimal('0'))
        self.client = APIClient()

    def receipt(self, client):
        return client.post('/api/v1/stock/', {
            'key': str(uuid4()), 'ingredient': self.flour.id, 'kind': 'receipt',
            'quantity': '10', 'cost_total': '60000',
            'date': str(timezone.localdate()), 'note': 'Bozordan',
        }, format='json')

    def test_the_cashier_can_still_record_stock(self):
        # Kirim kiritish kassirning kundalik ishi — u to'xtatilmaydi.
        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.receipt(self.client).status_code, 201)
        self.flour.refresh_from_db()
        self.assertEqual(self.flour.quantity, Decimal('10.000000'))

    def test_the_cashier_cannot_read_the_movement_history(self):
        self.client.force_authenticate(self.cashier)
        self.receipt(self.client)
        response = self.client.get('/api/v1/stock/')
        self.assertEqual(response.status_code, 403)
        self.assertIn('superadmin', str(response.data).lower())

    def test_the_owner_sees_the_whole_history(self):
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        self.receipt(cashier)

        self.client.force_authenticate(self.owner)
        response = self.client.get('/api/v1/stock/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['ingredient_name'], 'Un')

    def test_the_kitchen_reaches_neither(self):
        kitchen = APIClient()
        kitchen.force_authenticate(User.objects.create_user(
            'oshxona', password='test-only-long-password', role='kitchen', branch=self.branch))
        self.assertEqual(kitchen.get('/api/v1/stock/').status_code, 403)
        self.assertEqual(self.receipt(kitchen).status_code, 403)


class PlatformCommissionTests(TestCase):
    """Uzum va Yandex savdo summasining bir qismini o'zida ushlab qoladi.

    Mijoz to'lagan summa o'zgarmaydi — tushum to'liq yoziladi — lekin
    hisobimizga faqat qolgani tushadi. Shuning uchun ushlanma foyda
    zanjirida alohida qator bo'lib ayriladi, kun yakunida esa kassir
    platformadan qancha kutishini ko'rib turadi.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def sell(self, channel, method, quantity=2):
        return create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': method,
            'channel': channel,
            'lines': [{'dish': self.dish.id, 'quantity': quantity, 'note': ''}],
        })

    def set_share(self, channel, commission):
        return self.client.put(
            '/api/v1/channel-fees/', {'channel': channel, 'commission': commission}, format='json')

    def test_a_delivery_sale_freezes_the_platform_share(self):
        self.assertEqual(self.sell('uzum', 'uzum').channel_commission, Decimal('30'))
        self.assertEqual(self.sell('yandex', 'yandex').channel_commission, Decimal('30'))

    def test_hall_and_takeaway_keep_every_som(self):
        self.assertEqual(self.sell('hall', 'cash').channel_commission, Decimal('0'))
        self.assertEqual(self.sell('takeaway', 'cash').channel_commission, Decimal('0'))

    def test_the_owner_sets_the_share_and_the_next_sale_follows_it(self):
        self.assertEqual(self.set_share('uzum', '25').status_code, 200)
        self.assertEqual(self.sell('uzum', 'uzum').channel_commission, Decimal('25'))
        # Har platformaning o'z shartnomasi bor: Yandex tegilmaydi.
        self.assertEqual(self.sell('yandex', 'yandex').channel_commission, Decimal('30'))

    def test_changing_the_share_never_rewrites_a_past_sale(self):
        older = self.sell('uzum', 'uzum')        # 30% bilan sotilgan
        self.set_share('uzum', '10')
        newer = self.sell('uzum', 'uzum')        # endi 10%
        older.refresh_from_db()
        self.assertEqual(older.channel_commission, Decimal('30'))
        self.assertEqual(newer.channel_commission, Decimal('10'))
        # Hisobot ikkalasini o'z foizi bilan sanaydi: 30 000 + 10 000.
        data = self.client.get('/api/v1/finance/').data
        self.assertEqual(data['profit']['platform_fee'], '40000.00')

    def test_finance_keeps_the_revenue_whole_and_subtracts_the_share(self):
        self.sell('hall', 'cash')     # 100 000 — hech kim hech narsa ushlamaydi
        self.sell('uzum', 'uzum')     # 100 000 — 30 000 platformada qoladi
        data = self.client.get('/api/v1/finance/').data
        # Tushum mijoz to'lagan summa bo'lib qoladi.
        self.assertEqual(data['profit']['revenue'], '200000.00')
        self.assertEqual(data['profit']['platform_fee'], '30000.00')
        self.assertEqual(data['profit']['net_profit'], '170000.00')
        rows = {row['channel']: row for row in data['channels']}
        self.assertEqual(rows['uzum']['revenue'], '100000.00')
        self.assertEqual(rows['uzum']['fee'], '30000.00')
        self.assertEqual(rows['uzum']['net'], '70000.00')
        self.assertEqual(rows['hall']['fee'], '0.00')
        self.assertEqual(rows['hall']['net'], '100000.00')
        # Pul oqimi ham kamayadi: ushlangan pul hech qachon qo'lga tegmaydi.
        self.assertEqual(data['cash']['platform_fee'], '30000.00')
        self.assertEqual(data['cash']['net'], '170000.00')

    def test_the_monthly_trend_agrees_with_the_headline(self):
        self.sell('uzum', 'uzum')
        data = self.client.get('/api/v1/finance/').data
        current = next(row for row in data['trend'] if row['period'] == data['filters']['month'])
        self.assertEqual(current['platform_fee'], '30000.00')
        self.assertEqual(current['net_profit'], data['profit']['net_profit'])

    def test_the_shift_close_shows_what_the_platform_will_transfer(self):
        self.sell('hall', 'cash')
        self.sell('uzum', 'uzum')
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        rows = {row['method']: row for row in cashier.get('/api/v1/shift/').data['breakdown']}
        self.assertEqual(rows['uzum']['amount'], '100000.00')
        self.assertEqual(rows['uzum']['fee'], '30000.00')
        self.assertEqual(rows['uzum']['net'], '70000.00')
        # Naqd pulni hech kim ushlamaydi.
        self.assertEqual(rows['cash']['fee'], '0.00')
        self.assertEqual(rows['cash']['net'], '100000.00')

    def test_the_frozen_figures_survive_the_day_being_closed(self):
        self.sell('uzum', 'uzum')
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        closed = cashier.post('/api/v1/shift/', {'counted_cash': '0', 'note': ''}, format='json')
        self.assertEqual(closed.status_code, 201)
        rows = {row['method']: row for row in closed.data['breakdown']}
        self.assertEqual(rows['uzum']['net'], '70000.00')

    def test_only_the_superadmin_may_change_the_share(self):
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        self.assertEqual(cashier.get('/api/v1/channel-fees/').status_code, 403)
        self.assertEqual(
            cashier.put('/api/v1/channel-fees/', {'channel': 'uzum', 'commission': '0'}, format='json').status_code,
            403,
        )

    def test_the_share_must_stay_between_zero_and_a_hundred(self):
        self.assertEqual(self.set_share('uzum', '-1').status_code, 400)
        self.assertEqual(self.set_share('uzum', '101').status_code, 400)
        self.assertEqual(self.set_share('uzum', '0').status_code, 200)
        # Zal kanali uchun ushlanma tushunchasi yo'q.
        self.assertEqual(self.set_share('hall', '10').status_code, 400)

    def test_the_change_is_written_into_the_audit_log(self):
        self.set_share('yandex', '35')
        entry = AuditEvent.objects.filter(action='channel.fee').first()
        self.assertIsNotNone(entry)
        self.assertIn('30', entry.description)
        self.assertIn('35', entry.description)


class WaiterServiceChargeTests(TestCase):
    """Stolga xizmat haqi: hisob USTIGA qo'shiladi va ofitsiantniki bo'ladi.

    100 000 lik stol hisobiga 10% qo'shilsa mijoz 110 000 to'laydi. O'sha
    10 000 restoranning tushumi emas — u ofitsiant nomiga yig'ilgan pul va
    unga topshirilguncha kassada turadi.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.waiter = Waiter.objects.create(branch=self.branch, name='Fazliddin', commission=Decimal('10'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def sell(self, quantity=2, waiter=True, channel='hall', method='cash', table='5'):
        return create_order(self.cashier, {
            'key': uuid4(), 'table': table, 'waiter': '',
            'waiter_id': self.waiter.id if waiter else None,
            'channel': channel, 'payment_method': method,
            'lines': [{'dish': self.dish.id, 'quantity': quantity, 'note': ''}],
        })

    def hand_over(self, amount, key=None, client=None, method='cash'):
        return (client or self.client).post(f'/api/v1/waiters/{self.waiter.id}/payments/', {
            'key': str(key or uuid4()), 'amount': str(amount),
            'payment_method': method, 'paid_on': str(timezone.localdate()), 'note': '',
        }, format='json')

    def books(self):
        today = timezone.localdate()
        data = self.client.get(f'/api/v1/reports/waiters/?start={today}&end={today}').data
        return data['summary'], {row['name']: row for row in data['waiters']}

    def test_a_table_order_with_a_waiter_adds_the_charge_on_top(self):
        order = self.sell()                       # 100 000 lik hisob
        self.assertEqual(order.total, Decimal('100000'))
        self.assertEqual(order.service_charge, Decimal('10000'))
        # Mijoz to'laydigan summa — ikkalasining yig'indisi.
        self.assertEqual(order.payable, Decimal('110000'))

    def test_takeaway_and_delivery_never_carry_a_service_charge(self):
        # Olib ketishda ofitsiant xizmati yo'q, demak haq ham yo'q.
        self.assertEqual(self.sell(channel='takeaway', table='').service_charge, Decimal('0'))
        self.assertEqual(self.sell(channel='uzum', method='uzum', table='').service_charge, Decimal('0'))

    def test_a_table_without_a_waiter_carries_nothing_either(self):
        self.assertEqual(self.sell(waiter=False).service_charge, Decimal('0'))

    def test_the_charge_follows_dishes_added_to_an_open_bill(self):
        order = self.sell(quantity=2, method='')          # ochiq hisob
        self.assertEqual(order.service_charge, Decimal('10000'))
        append_order_lines(self.cashier, order.id, {
            'key': uuid4(), 'lines': [{'dish': self.dish.id, 'quantity': 1, 'note': ''}],
        })
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal('150000'))
        self.assertEqual(order.service_charge, Decimal('15000'))

    def test_a_discount_lowers_the_charge_as_well(self):
        order = self.sell(quantity=2, method='')
        self.client.post(
            f'/api/v1/orders/{order.id}/discount/',
            {'amount': '20000', 'reason': 'Doimiy mijoz'}, format='json')
        order.refresh_from_db()
        # Chegirmadan keyin hisob 80 000, xizmat haqi esa shundan 10%.
        self.assertEqual(order.total, Decimal('80000'))
        self.assertEqual(order.service_charge, Decimal('8000'))
        self.assertEqual(order.payable, Decimal('88000'))

    def test_removing_a_dish_lowers_the_charge(self):
        order = self.sell(quantity=2, method='')
        line = order.lines.first()
        self.client.post(f'/api/v1/orders/{order.id}/lines/', {
            'key': str(uuid4()), 'lines': [{'dish': self.dish.id, 'quantity': 1, 'note': ''}],
        }, format='json')
        self.client.delete(f'/api/v1/orders/{order.id}/lines/{line.id}/')
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal('50000'))
        self.assertEqual(order.service_charge, Decimal('5000'))

    def test_changing_the_rate_never_rewrites_a_past_bill(self):
        older = self.sell()
        self.client.patch(f'/api/v1/waiters/{self.waiter.id}/', {'commission': '5'}, format='json')
        newer = self.sell()
        older.refresh_from_db()
        self.assertEqual(older.service_charge, Decimal('10000'))
        self.assertEqual(newer.service_charge, Decimal('5000'))

    def test_the_charge_is_not_revenue_but_it_is_in_the_drawer(self):
        self.sell()                                   # 100 000 + 10 000
        finance = self.client.get('/api/v1/finance/').data
        # Tushum faqat taomlardan.
        self.assertEqual(finance['profit']['revenue'], '100000.00')
        self.assertEqual(finance['service']['collected'], '10000.00')
        self.assertEqual(finance['service']['owed'], '10000.00')
        # Pul esa kassada: mijoz 110 000 berdi.
        self.assertEqual(finance['cash']['in'], '110000.00')

        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        day = cashier.get('/api/v1/shift/').data
        self.assertEqual(day['revenue'], '100000.00')
        self.assertEqual(day['service'], '10000.00')
        self.assertEqual(day['expected_cash'], '110000.00')

    def test_the_balance_is_what_was_collected_minus_what_was_handed_over(self):
        self.sell()
        summary, rows = self.books()
        self.assertEqual(rows['Fazliddin']['today_fee'], '10000.00')
        self.assertEqual(rows['Fazliddin']['balance'], '10000.00')
        self.assertEqual(summary['owed'], '10000.00')

        self.assertEqual(self.hand_over(Decimal('6000')).status_code, 201)
        summary, rows = self.books()
        self.assertEqual(rows['Fazliddin']['paid'], '6000.00')
        self.assertEqual(rows['Fazliddin']['balance'], '4000.00')
        self.assertEqual(summary['owed'], '4000.00')

    def test_an_open_bill_owes_the_waiter_nothing_yet(self):
        # Pul hali olinmagan: ofitsiantga berish uchun ham hech narsa yo'q.
        self.sell(method='')
        summary, _rows = self.books()
        self.assertEqual(summary['owed'], '0.00')

    def test_handing_money_over_leaves_the_profit_alone(self):
        self.sell()
        before = self.client.get('/api/v1/finance/').data['profit']['net_profit']
        self.hand_over(Decimal('10000'))
        after = self.client.get('/api/v1/finance/').data
        self.assertEqual(after['profit']['net_profit'], before)
        # Xarajat ham yaratilmaydi: bu restoranning puli emas edi.
        self.assertEqual(Expense.objects.filter(branch=self.branch).count(), 0)
        # Lekin kassadan chiqadi.
        self.assertEqual(after['cash']['service_paid'], '10000.00')
        self.assertEqual(after['service']['owed'], '0.00')

    def test_the_drawer_drops_when_the_waiter_is_paid_in_cash(self):
        self.sell()
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        self.assertEqual(cashier.get('/api/v1/shift/').data['expected_cash'], '110000.00')
        self.hand_over(Decimal('10000'), client=cashier)
        self.assertEqual(cashier.get('/api/v1/shift/').data['expected_cash'], '100000.00')

    def test_the_same_key_never_pays_a_waiter_twice(self):
        self.sell()
        key = uuid4()
        self.assertEqual(self.hand_over(Decimal('5000'), key=key).status_code, 201)
        self.assertEqual(self.hand_over(Decimal('5000'), key=key).status_code, 200)
        self.assertEqual(WaiterPayment.objects.filter(waiter=self.waiter).count(), 1)
        self.assertEqual(self.hand_over(Decimal('7000'), key=key).status_code, 409)

    def test_the_kitchen_hands_over_nothing(self):
        kitchen = APIClient()
        kitchen.force_authenticate(User.objects.create_user(
            'oshxona', password='test-only-long-password', role='kitchen', branch=self.branch))
        self.assertEqual(self.hand_over(Decimal('1000'), client=kitchen).status_code, 403)

    def test_the_receipt_shows_the_charge_on_its_own_line(self):
        from operations.printing import receipt_bytes
        order = self.sell()
        text = receipt_bytes(order).decode('cp866', errors='ignore')
        self.assertIn('Xizmat haqi', text)
        self.assertIn('110 000', text)


class LostRaceTests(TestCase):
    """Bir vaqtda yozishda 409 qaytishi kerak, 500 emas.

    Har bir amalda «o'qi — tekshir — yoz» oynasi bor: ikkinchi kassir
    o'sha qatorni oraliqda yozib ulgursa, unique cheklov ishlaydi. Bu
    foydalanuvchi qayta urinib ko'radigan to'qnashuv, server nosozligi
    emas. Ilgari beshta yo'lda ham 500 chiqardi.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.day = timezone.localdate()
        # Yakshanbaga davomat yuritilmaydi, shuning uchun sinov shanbaga suriladi.
        while self.day.weekday() == 6:
            self.day -= timedelta(days=1)

    def test_shift_close_that_loses_the_race(self):
        from operations import shift as shift_module

        real = shift_module.day_figures

        def figures_then_race(*args, **kwargs):
            result = real(*args, **kwargs)
            ShiftClose.objects.get_or_create(
                branch=self.branch, date=timezone.localdate(),
                defaults={
                    'actor': self.owner, 'expected_cash': Decimal('0'),
                    'counted_cash': Decimal('0'), 'difference': Decimal('0'),
                    'revenue': Decimal('0'), 'orders': 0, 'breakdown': [],
                },
            )
            return result

        with patch('operations.shift.day_figures', side_effect=figures_then_race):
            response = self.client.post('/api/v1/shift/', {'counted_cash': '0', 'note': ''}, format='json')
        self.assertEqual(response.status_code, 409)

    def test_attendance_that_loses_the_race(self):
        from .models import Attendance
        Attendance.objects.create(
            branch=self.branch, employee=self.cashier, actor=self.owner,
            date=self.day, present=True, daily_wage=Decimal('0'),
        )
        with patch('users.payroll.Attendance.objects.select_for_update') as blind:
            blind.return_value.filter.return_value = Attendance.objects.none()
            response = self.client.post('/api/v1/attendance/', {
                'date': self.day.isoformat(),
                'rows': [{'employee': self.cashier.id, 'present': True}],
            }, format='json')
        self.assertEqual(response.status_code, 409)

    def test_salary_payment_that_loses_the_race(self):
        payload = {'key': str(uuid4()), 'amount': '50000', 'payment_method': 'cash',
                   'paid_on': self.day.isoformat()}
        self.client.post(f'/api/v1/staff/{self.cashier.id}/salary-payments/', payload, format='json')
        with patch('users.views.SalaryPayment.objects.filter') as blind:
            blind.return_value.first.return_value = None
            response = self.client.post(
                f'/api/v1/staff/{self.cashier.id}/salary-payments/', payload, format='json')
        self.assertEqual(response.status_code, 409)

    def test_waiter_payment_that_loses_the_race(self):
        waiter = Waiter.objects.create(branch=self.branch, name='Ali', commission=Decimal('10'))
        WaiterPayment.objects.create(
            branch=self.branch, waiter=waiter, actor=self.owner, key=uuid4(),
            amount=Decimal('1000'), payment_method='cash', paid_on=self.day,
        )
        # Hisobda pul bo'lishi kerak, aks holda to'lov balans tekshiruvida to'xtaydi.
        Order.objects.create(
            branch=self.branch, cashier=self.owner, key=uuid4(), request_hash='x',
            table='1', waiter_ref=waiter, waiter_commission=Decimal('10'),
            service_charge=Decimal('90000'), total=Decimal('900000'),
            status='paid', payment_method='cash', paid_at=timezone.now(),
        )
        key = str(uuid4())
        WaiterPayment.objects.create(
            branch=self.branch, waiter=waiter, actor=self.owner, key=key,
            amount=Decimal('5000'), payment_method='cash', paid_on=self.day,
        )
        with patch('operations.waiters.WaiterPayment.objects.filter') as blind:
            blind.return_value.first.return_value = None
            response = self.client.post(f'/api/v1/waiters/{waiter.id}/payments/', {
                'key': key, 'amount': '5000', 'payment_method': 'cash',
                'paid_on': self.day.isoformat(),
            }, format='json')
        self.assertEqual(response.status_code, 409)

    def test_daily_usage_that_loses_the_race(self):
        item = Ingredient.objects.create(
            branch=self.branch, name='Guruch', unit='kg',
            quantity=Decimal('10'), unit_cost=Decimal('100'))
        DailyUsage.objects.create(
            branch=self.branch, actor=self.owner, ingredient=item,
            date=self.day, quantity=Decimal('2'))
        with patch('operations.daily_usage.DailyUsage.objects.select_for_update') as blind:
            blind.return_value.filter.return_value = DailyUsage.objects.none()
            response = self.client.post('/api/v1/daily-usage/', {
                'date': self.day.isoformat(),
                'lines': [{'ingredient': item.id, 'quantity': '3'}],
            }, format='json')
        self.assertEqual(response.status_code, 409)


class CorrectingMistakesTests(TestCase):
    """Xato kiritilgan raqamni qaytarib olish yo'li bo'lishi kerak."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Main')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('40000'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def add_expense(self, amount='1000000'):
        return self.client.post('/api/v1/expenses/', {
            'key': str(uuid4()), 'category': 'Ijara', 'purpose': 'oy',
            'amount': amount, 'payment_method': 'cash',
            'date': timezone.localdate().isoformat(),
        }, format='json').data['id']

    def test_a_mistyped_expense_can_be_corrected(self):
        expense = self.add_expense('1000000')
        response = self.client.patch(f'/api/v1/expenses/{expense}/', {'amount': '100000'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Expense.objects.get(pk=expense).amount, Decimal('100000'))
        self.assertTrue(AuditEvent.objects.filter(action='expense.update').exists())

    def test_a_mistyped_expense_can_be_deleted(self):
        expense = self.add_expense()
        self.assertEqual(self.client.delete(f'/api/v1/expenses/{expense}/').status_code, 204)
        self.assertFalse(Expense.objects.filter(pk=expense).exists())
        self.assertTrue(AuditEvent.objects.filter(action='expense.remove').exists())

    def test_the_cashier_cannot_delete_an_expense(self):
        expense = self.add_expense()
        till = APIClient()
        till.force_authenticate(self.cashier)
        self.assertEqual(till.delete(f'/api/v1/expenses/{expense}/').status_code, 403)

    def test_a_salary_expense_stays_locked(self):
        self.client.post(f'/api/v1/staff/{self.cashier.id}/salary-payments/', {
            'key': str(uuid4()), 'amount': '50000', 'payment_method': 'cash',
            'paid_on': timezone.localdate().isoformat(),
        }, format='json')
        expense = SalaryPayment.objects.get().expense_id
        self.assertEqual(self.client.delete(f'/api/v1/expenses/{expense}/').status_code, 409)
        self.assertEqual(
            self.client.patch(f'/api/v1/expenses/{expense}/', {'amount': '1'}, format='json').status_code, 409)

    def test_a_mistyped_prep_batch_can_be_removed(self):
        self.client.post('/api/v1/dish-prep/', {
            'lines': [{'dish': self.dish.id, 'quantity': 200}],
        }, format='json')
        row = DishPrep.objects.get()
        response = self.client.delete(f'/api/v1/dish-prep/{row.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DishPrep.objects.exists())
        self.assertEqual(response.data['summary']['prepared'], 0)
        self.assertTrue(AuditEvent.objects.filter(action='prep.remove').exists())

    def test_yesterdays_prep_batch_is_left_alone(self):
        row = DishPrep.objects.create(
            branch=self.branch, dish=self.dish, actor=self.owner,
            date=timezone.localdate() - timedelta(days=1), quantity=20)
        self.assertEqual(self.client.delete(f'/api/v1/dish-prep/{row.id}/').status_code, 400)
        self.assertTrue(DishPrep.objects.filter(pk=row.id).exists())

    def test_two_dishes_cannot_share_a_name(self):
        response = self.client.post('/api/v1/dishes/', {
            'category': self.category.id, 'name': 'osh', 'price': '55000',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Dish.objects.filter(branch=self.branch).count(), 1)


class PasswordTests(TestCase):
    """Parolni almashtirish yo'li bo'lishi kerak — hisobni tashlab ketmasdan."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cook = User.objects.create_user('cook', password='test-only-long-password', role='kitchen', branch=self.branch)
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def test_the_owner_resets_a_staff_password(self):
        response = self.client.patch(f'/api/v1/staff/{self.cook.id}/', {
            'password': 'another-long-password',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.cook.refresh_from_db()
        self.assertTrue(self.cook.check_password('another-long-password'))

    def test_a_short_password_is_refused(self):
        response = self.client.patch(f'/api/v1/staff/{self.cook.id}/', {'password': 'qisqa'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.cook.refresh_from_db()
        self.assertTrue(self.cook.check_password('test-only-long-password'))

    def test_anyone_changes_their_own_password(self):
        kitchen = APIClient()
        kitchen.force_authenticate(self.cook)
        response = kitchen.post('/api/v1/auth/password/', {
            'current_password': 'test-only-long-password',
            'new_password': 'brand-new-long-password',
        }, format='json')
        self.assertEqual(response.status_code, 200)
        self.cook.refresh_from_db()
        self.assertTrue(self.cook.check_password('brand-new-long-password'))

    def test_the_old_password_is_required(self):
        kitchen = APIClient()
        kitchen.force_authenticate(self.cook)
        response = kitchen.post('/api/v1/auth/password/', {
            'current_password': 'wrong-password-here',
            'new_password': 'brand-new-long-password',
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.cook.refresh_from_db()
        self.assertTrue(self.cook.check_password('test-only-long-password'))

    def test_a_wrong_password_is_written_to_the_log(self):
        guest = APIClient()
        guest.post('/api/v1/auth/login/', {'username': 'cook', 'password': 'nope'}, format='json')
        self.assertTrue(AuditEvent.objects.filter(action='auth.failed').exists())

    def test_an_unknown_login_does_not_fill_the_log(self):
        guest = APIClient()
        guest.post('/api/v1/auth/login/', {'username': 'hech-kim', 'password': 'nope'}, format='json')
        self.assertFalse(AuditEvent.objects.filter(action='auth.failed').exists())


class FrozenNumbersTests(TestCase):
    """Bir marta yozilgan raqam keyingi kelishuvdan qayta hisoblanmasligi kerak."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user(
            'cashier', password='test-only-long-password', role='cashier',
            branch=self.branch, daily_wage=Decimal('100000'))
        self.day = timezone.localdate()
        while self.day.weekday() == 6:
            self.day -= timedelta(days=1)

    def test_re_marking_a_day_keeps_the_wage_that_was_agreed_then(self):
        from users.payroll import mark_attendance

        from .models import Attendance
        rows = [{'employee': self.cashier.id, 'present': True, 'note': ''}]
        mark_attendance(self.owner, {'date': self.day, 'rows': rows})
        self.cashier.daily_wage = Decimal('900000')
        self.cashier.save(update_fields=['daily_wage'])
        mark_attendance(self.owner, {'date': self.day, 'rows': rows})
        self.assertEqual(
            Attendance.objects.get(employee=self.cashier, date=self.day).daily_wage,
            Decimal('100000'),
        )

    def test_a_day_turned_from_absent_to_present_takes_todays_wage(self):
        from users.payroll import mark_attendance

        from .models import Attendance
        mark_attendance(self.owner, {'date': self.day, 'rows': [
            {'employee': self.cashier.id, 'present': False, 'note': ''}]})
        mark_attendance(self.owner, {'date': self.day, 'rows': [
            {'employee': self.cashier.id, 'present': True, 'note': ''}]})
        self.assertEqual(
            Attendance.objects.get(employee=self.cashier, date=self.day).daily_wage,
            Decimal('100000'),
        )


class ProfitChainTests(TestCase):
    """Bitta sahifadagi ikkita «sof foyda» bir xil bo'lishi shart."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Main')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('40000'))

    def test_the_monthly_chart_subtracts_waste_like_the_headline(self):
        from .finance import build_finance, monthly_trend
        prepare(self.owner, self.dish)
        client = APIClient()
        client.force_authenticate(self.owner)
        client.post('/api/v1/orders/', {
            'key': str(uuid4()), 'table': '', 'lines': [{'dish': self.dish.id, 'quantity': 1}],
            'payment_method': 'cash',
        }, format='json')
        item = Ingredient.objects.create(
            branch=self.branch, name='Guruch', unit='kg',
            quantity=Decimal('100'), unit_cost=Decimal('20000'))
        StockMovement.objects.create(
            branch=self.branch, ingredient=item, actor=self.owner, key=uuid4(),
            request_hash='x', kind='consumption', quantity=Decimal('5'),
            unit_cost=Decimal('20000'), cost_total=Decimal('100000'),
            date=timezone.localdate(), note='isrof',
        )
        today = timezone.localdate()
        headline = build_finance(self.branch, today.replace(day=1), today, today)
        this_month = monthly_trend(self.branch, today)[-1]
        self.assertEqual(this_month['net_profit'], headline['profit']['net_profit'])

    def test_a_refund_takes_its_cost_back_out_of_consumption(self):
        from .finance import build_finance
        item = Ingredient.objects.create(
            branch=self.branch, name='Guruch', unit='kg',
            quantity=Decimal('100'), unit_cost=Decimal('1000'))
        recipe = Recipe.objects.create(
            branch=self.branch, dish=self.dish, name='Osh', yield_quantity=Decimal('1'))
        RecipeLine.objects.create(
            recipe=recipe, ingredient=item, quantity=Decimal('2'), batch_cost=Decimal('2000'))
        prepare(self.owner, self.dish)
        client = APIClient()
        client.force_authenticate(self.owner)
        order = client.post('/api/v1/orders/', {
            'key': str(uuid4()), 'table': '', 'lines': [{'dish': self.dish.id, 'quantity': 1}],
            'payment_method': 'cash',
        }, format='json').data['id']
        client.post(f'/api/v1/orders/{order}/refund/', {'reason': 'mijoz qaytardi'}, format='json')
        today = timezone.localdate()
        report = build_finance(self.branch, today.replace(day=1), today, today)
        # Sotuv qaytarildi: sarflangan tannarx ham nolga qaytishi kerak.
        self.assertEqual(report['stock']['consumed'], '0.00')
        # Qaytarish xarid emas — ombor xaridiga qo'shilmaydi.
        self.assertEqual(report['cash']['stock_purchases'], '0.00')


class WaiterBalanceTests(TestCase):
    """Ofitsiantga yig'ilganidan ko'p pul berib bo'lmaydi."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.waiter = Waiter.objects.create(branch=self.branch, name='Ali', commission=Decimal('10'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)

    def hand_over(self, amount):
        return self.client.post(f'/api/v1/waiters/{self.waiter.id}/payments/', {
            'key': str(uuid4()), 'amount': amount, 'payment_method': 'cash',
            'paid_on': timezone.localdate().isoformat(),
        }, format='json')

    def earn(self, service):
        Order.objects.create(
            branch=self.branch, cashier=self.owner, key=uuid4(), request_hash='x',
            table='1', waiter_ref=self.waiter, waiter_commission=Decimal('10'),
            service_charge=service, total=service * 10, status='paid',
            payment_method='cash', paid_at=timezone.now(),
        )

    def test_nothing_earned_means_nothing_to_hand_over(self):
        self.assertEqual(self.hand_over('5000000').status_code, 400)
        self.assertFalse(WaiterPayment.objects.exists())

    def test_the_collected_amount_can_be_handed_over(self):
        self.earn(Decimal('50000'))
        self.assertEqual(self.hand_over('50000').status_code, 201)

    def test_one_som_over_the_balance_is_refused(self):
        self.earn(Decimal('50000'))
        self.assertEqual(self.hand_over('50001').status_code, 400)


class BackendTranslationTests(SimpleTestCase):
    """Server yuboradigan har bir xabar uch tilda bo'lishi shart.

    Tekshiruv manba kodini o'qiydi: yangi `_('…')` qo'shilsa-yu, tarjimasi
    yozilmasa, ruscha ekranda o'zbekcha xabar paydo bo'ladi. Ilgari
    shunday sakkizta xabar yig'ilib qolgan edi.
    """

    def test_every_message_has_russian_and_english(self):
        import ast

        from core.translations import EN, RU

        root = Path(settings.BASE_DIR)
        used = {}
        for path in root.rglob('*.py'):
            if 'migrations' in path.parts or path.name in ('tests.py', 'translations.py'):
                continue
            # utf-8-sig: tahrirlovchi qo'ygan BOM belgisi `ast` ni yiqitadi,
            # lekin Python uchun bu yaroqli fayl — tekshiruv shu sababdan
            # to'xtab qolmasligi kerak.
            for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                        and node.func.id == '_' and node.args
                        and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    used[node.args[0].value] = path.name

        self.assertEqual(sorted(key for key in used if key not in RU), [], 'ruscha tarjimasi yo‘q')
        self.assertEqual(sorted(key for key in used if key not in EN), [], 'inglizcha tarjimasi yo‘q')


@override_settings(
    TELEGRAM_BOT_TOKEN='test-token',
    TELEGRAM_CHAT_ID='111,222',
    TELEGRAM_WEBHOOK_SECRET='test-secret',
)
class TelegramCommandTests(TestCase):
    """Botdagi /backup buyrug'i.

    Eng muhimi kim chaqira olishi: webhook manzili internetda ochiq
    turadi, shuning uchun har bir qavat alohida tekshiriladi.
    """

    URL = '/api/v1/telegram/webhook/'

    def setUp(self):
        self.client = APIClient()
        self.sent = []
        self.backups = []

    def send(self, text, chat='111', secret='test-secret'):
        def remember(_token, target, message):
            self.sent.append((str(target), message))
            return True

        def fake_backup(**kwargs):
            self.backups.append(kwargs)
            return {'files': [], 'sent_to_telegram': True, 'note': '', 'delivered': 2,
                    'recipients': 2, 'removed_old': 0, 'created_at': timezone.now()}

        with patch('operations.telegram_bot.telegram_message', side_effect=remember), \
             patch('operations.telegram_bot.run_backup', side_effect=fake_backup), \
             patch('operations.telegram_bot.recent_backup', return_value=None):
            return self.client.post(
                self.URL,
                {'message': {'chat': {'id': int(chat)}, 'text': text}},
                format='json',
                headers={'X-Telegram-Bot-Api-Secret-Token': secret},
            )

    def test_the_backup_command_makes_a_backup(self):
        self.assertEqual(self.send('/backup').status_code, 200)
        self.assertEqual(len(self.backups), 1)

    def test_a_wrong_secret_is_ignored(self):
        self.assertEqual(self.send('/backup', secret='guessed').status_code, 200)
        self.assertEqual(self.backups, [], 'maxfiy so‘zsiz nusxa olinmasligi kerak')
        self.assertEqual(self.sent, [], 'begonaga javob ham yozilmaydi')

    def test_a_missing_secret_is_ignored(self):
        self.assertEqual(self.send('/backup', secret='').status_code, 200)
        self.assertEqual(self.backups, [])

    def test_a_stranger_cannot_start_a_backup(self):
        self.send('/backup', chat='999')
        self.assertEqual(self.backups, [], 'ro‘yxatda yo‘q chat nusxa ololmaydi')
        # Lekin o'z raqamini biladi — uni qo'shish uchun shu kerak.
        self.assertIn('999', self.sent[0][1])

    def test_the_second_allowed_chat_also_works(self):
        self.send('/backup', chat='222')
        self.assertEqual(len(self.backups), 1)

    def test_help_does_not_touch_the_database(self):
        self.send('/help')
        self.assertEqual(self.backups, [])
        self.assertIn('/backup', self.sent[0][1])

    def test_an_unknown_command_is_answered_not_run(self):
        self.send('/nimadir')
        self.assertEqual(self.backups, [])
        self.assertIn('Noma', self.sent[0][1])

    def test_a_repeat_within_the_cooldown_is_refused(self):
        """Telegram javobni kutmay so'rovni takrorlashi mumkin — har
        takror yangi nusxa yasamasligi kerak."""
        class Fresh:
            def stat(self):
                class Info:
                    st_size = 1024
                return Info()

        def remember(_token, target, message):
            self.sent.append((str(target), message))
            return True

        with patch('operations.telegram_bot.telegram_message', side_effect=remember), \
             patch('operations.telegram_bot.run_backup') as never, \
             patch('operations.telegram_bot.recent_backup', return_value=Fresh()):
            self.client.post(
                self.URL, {'message': {'chat': {'id': 111}, 'text': '/backup'}},
                format='json', headers={'X-Telegram-Bot-Api-Secret-Token': 'test-secret'})
        never.assert_not_called()


@override_settings(PRINT_MODE='agent', PRINT_AGENT_TOKEN='agent-token', RECEIPT_AUTO_PRINT=True)
class PrintQueueTests(TestCase):
    """Bulutdagi server va restorandagi printer orasidagi navbat.

    Eng muhim shart: bitta talon ikki marta chiqmasligi va yo'qolmasligi
    kerak. Qog'oz arzon, lekin ikki marta chiqqan oshxona taloni ikkinchi
    porsiyani pishirtiradi.
    """

    INIT = b'\x1b\x40'
    CUT = b'\x1d\x56\x42\x00'

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user(
            'owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Main')
        self.dish = Dish.objects.create(
            branch=self.branch, category=self.category, name='Osh', price=Decimal('40000'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.agent = APIClient()

    def sell(self):
        prepare(self.owner, self.dish)
        # Mijoz cheki `transaction.on_commit` orqali navbatga qo'yiladi:
        # savdo yozilmasa chek ham chiqmasligi kerak. `TestCase` esa
        # tranzaksiyani hech qachon yakunlamaydi, shuning uchun chaqiruvlar
        # ataylab ishga tushiriladi — aks holda sinov haqiqatdan farq qilardi.
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post('/api/v1/orders/', {
                'key': str(uuid4()), 'table': '5',
                'lines': [{'dish': self.dish.id, 'quantity': 1}],
                'payment_method': 'cash',
            }, format='json')

    def claim(self, stations=('kitchen', 'counter'), token='agent-token', branch='one'):
        return self.agent.post('/api/v1/print/claim/', {
            'agent': 'kassa-1', 'branch': branch, 'stations': list(stations),
        }, format='json', headers={'X-Print-Agent-Token': token})

    def ack(self, job_id, ok=True, error='', token='agent-token'):
        return self.agent.post('/api/v1/print/ack/', {
            'id': job_id, 'ok': ok, 'error': error,
        }, format='json', headers={'X-Print-Agent-Token': token})

    def test_a_sale_queues_a_ticket_instead_of_printing(self):
        response = self.sell()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(PrintJob.objects.filter(status='queued').exists())
        # Kassir printer javobini kutmaydi: ogohlantirish chiqmaydi.
        self.assertEqual(response.data['print_problems'], [])

    def test_the_agent_gets_the_bytes_it_needs(self):
        self.sell()
        jobs = self.claim().data['jobs']
        self.assertTrue(jobs)
        by_kind = {row['kind']: base64.b64decode(row['payload']) for row in jobs}
        for payload in by_kind.values():
            # ESC/POS oqimi INIT bilan boshlanadi va kesish bilan tugaydi.
            self.assertTrue(payload.startswith(self.INIT))
            self.assertTrue(payload.endswith(self.CUT))
        # Oshxona taloni narxsiz, mijoz cheki esa restoran nomi va summa
        # bilan chiqadi — ular bir xil emas.
        self.assertIn(b'OSHXONA', by_kind['prep'])
        self.assertNotIn(b'40 000', by_kind['prep'])
        self.assertIn(b'XONIM', by_kind['receipt'])
        self.assertIn(b'40 000', by_kind['receipt'])

    def test_a_claimed_ticket_is_not_handed_out_twice(self):
        self.sell()
        first = self.claim().data['jobs']
        second = self.claim().data['jobs']
        self.assertTrue(first)
        self.assertEqual(second, [], 'olingan talon ikkinchi marta berilmasligi kerak')

    def test_a_printed_ticket_leaves_the_queue(self):
        self.sell()
        job = self.claim().data['jobs'][0]
        self.ack(job['id'], ok=True)
        self.assertEqual(PrintJob.objects.get(pk=job['id']).status, 'done')

    def test_a_failed_ticket_comes_back_for_another_try(self):
        self.sell()
        job = self.claim().data['jobs'][0]
        self.ack(job['id'], ok=False, error='qog‘oz tugadi')
        again = PrintJob.objects.get(pk=job['id'])
        self.assertEqual(again.status, 'queued')
        self.assertEqual(again.attempts, 1)
        self.assertTrue(self.claim().data['jobs'], 'qayta urinish uchun berilishi kerak')

    def test_a_broken_printer_does_not_spin_forever(self):
        self.sell()
        job_id = PrintJob.objects.first().id
        for _attempt in range(6):
            self.claim()
            self.ack(job_id, ok=False, error='printer o‘chgan')
        stuck = PrintJob.objects.get(pk=job_id)
        self.assertEqual(stuck.status, 'failed')
        self.assertNotIn(
            job_id, [row['id'] for row in self.claim().data['jobs']],
            'navbat tiqilib qolmasligi kerak')

    def test_an_abandoned_ticket_returns_to_the_queue(self):
        """Agent olib ketdi-yu, kompyuter o'chdi. Talon yo'qolmasligi kerak."""
        self.sell()
        job = self.claim().data['jobs'][0]
        PrintJob.objects.filter(pk=job['id']).update(
            claimed_at=timezone.now() - timedelta(seconds=600))
        back = [row['id'] for row in self.claim().data['jobs']]
        self.assertIn(job['id'], back, 'ijara tugagach navbatga qaytadi')

    def test_the_agent_only_gets_its_own_stations(self):
        self.sell()
        rows = self.claim(stations=['kitchen']).data['jobs']
        self.assertTrue(rows)
        self.assertTrue(all(row['station'] == 'kitchen' for row in rows))

    def test_another_branch_is_not_served(self):
        self.sell()
        self.assertEqual(self.claim(branch='boshqa').data['jobs'], [])

    def test_a_wrong_token_is_refused(self):
        self.sell()
        self.assertEqual(self.claim(token='guessed').status_code, 403)
        self.assertEqual(self.ack(1, token='guessed').status_code, 403)

    @override_settings(PRINT_AGENT_TOKEN='')
    def test_without_a_token_the_queue_is_closed(self):
        self.assertEqual(self.claim(token='').status_code, 403)


class PaymentMethodBreakdownTests(TestCase):
    """Har bir to'lov yo'li alohida ko'rinadi va ustiga bosilsa ajratib beradi.

    Egasi bank bilan hisob-kitobni shu kesim bo'yicha qiladi: terminaldan
    qancha tushganini kartadan ajratib ko'ra olmasa, bankning hisobotini
    tizimning raqami bilan solishtirib bo'lmaydi.
    """

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Osh', price=Decimal('50000'))
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        prepare(self.cashier, *Dish.objects.filter(branch=self.branch))

    def sell(self, method, quantity=1):
        return create_order(self.cashier, {
            'key': uuid4(), 'table': '', 'waiter': '', 'payment_method': method,
            'lines': [{'dish': self.dish.id, 'quantity': quantity, 'note': ''}],
        })

    def board(self, query=''):
        today = timezone.localdate()
        return self.client.get(f'/api/v1/sales/board/?start={today}&end={today}{query}')

    def test_the_terminal_is_a_payment_method_of_its_own(self):
        order = self.sell('terminal')
        self.assertEqual(order.payment_method, 'terminal')
        rails = {item['method'] for item in self.client.get('/api/v1/auth/me/').data['payment_methods']}
        self.assertIn('terminal', rails)
        # Kartadan ajralib turadi: ikkalasi bir xil qatorga qo'shilib ketmaydi.
        rows = {row['method']: row for row in self.client.get('/api/v1/finance/').data['methods']}
        self.assertEqual(rows['terminal']['revenue'], '50000.00')
        self.assertEqual(rows['card']['revenue'], '0.00')

    def test_every_method_stays_on_the_list_even_with_no_sales(self):
        self.sell('cash')
        rows = {row['method']: row for row in self.client.get('/api/v1/finance/').data['methods']}
        # Savdosi yo'q yo'l ham nol bo'lib turadi: yo'q qator «tekshirilmagan»
        # degani emas.
        self.assertEqual(sorted(rows), ['card', 'cash', 'click', 'terminal', 'uzum', 'yandex'])
        self.assertEqual(rows['cash']['revenue'], '50000.00')
        self.assertEqual(rows['click']['orders'], 0)

    def test_the_board_shows_one_method_when_asked(self):
        self.sell('cash', 2)          # 100 000
        self.sell('terminal')         # 50 000
        everything = self.board().data
        self.assertEqual(everything['summary']['revenue'], '150000.00')
        self.assertEqual(len(everything['checks']), 2)

        only = self.board('&method=terminal').data
        self.assertEqual(only['summary']['revenue'], '50000.00')
        self.assertEqual(only['filters']['method'], 'terminal')
        # Cheklar ro'yxati ham ajraladi: jami bilan ro'yxat bir-biriga mos
        # kelmasa, egasi qaysi raqamga ishonishni bilmaydi.
        self.assertEqual([row['payment_method'] for row in only['checks']], ['terminal'])
        self.assertEqual(sorted(row['method'] for row in only['methods']), ['terminal'])

    def test_the_dish_breakdown_follows_the_method_filter(self):
        self.sell('cash', 3)
        self.sell('terminal', 1)
        only = self.board('&method=terminal').data
        self.assertEqual([row['quantity'] for row in only['dishes']], [1])
        self.assertEqual(only['summary']['items'], 1)

    def test_a_method_that_does_not_exist_is_refused(self):
        self.assertEqual(self.board('&method=payme').status_code, 400)
