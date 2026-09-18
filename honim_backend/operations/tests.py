from datetime import datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from users.models import AuditEvent, Branch, User
from catalog.models import Category, Dish
from .models import DailyUsage, Order, OrderLine, Expense, Ingredient, Recipe, RecipeLine, SalaryPayment, ShiftClose, StockMovement, Table
from .money import money, percent, quantity, share
from .services import append_order_lines, create_order, move_stock, Conflict


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

    def test_cashier_cannot_edit_menu_or_access_finance(self):
        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.client.post('/api/v1/categories/', {'name': 'No'}).status_code, 403)
        self.assertEqual(self.client.get('/api/v1/dashboard/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/expenses/').status_code, 403)
        self.assertEqual(self.client.get('/api/v1/staff/').status_code, 403)

    def test_only_owner_creates_admin_and_password_is_never_returned(self):
        response = self.client.post('/api/v1/staff/', {
            'name': 'Filial admini', 'username': 'branch_admin',
            'role': 'admin', 'password': 'Safe-test-password-48!'
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertNotIn('password', response.data)
        created = User.objects.get(username='branch_admin')
        self.assertTrue(created.check_password('Safe-test-password-48!'))
        self.assertEqual(created.branch, self.branch)
        self.client.force_authenticate(created)
        self.assertEqual(self.client.post('/api/v1/staff/', {
            'name': 'No', 'username': 'no_admin',
            'role': 'admin', 'password': 'Safe-test-password-49!'
        }, format='json').status_code, 403)

    def test_owner_updates_employee_and_salary_payment_hits_finance_once(self):
        employee = User.objects.create_user(
            'manager', password='Safe-test-password-51!', first_name='Menejer',
            role='admin', branch=self.branch, salary=Decimal('3500000')
        )
        detail = f'/api/v1/staff/{employee.id}/'
        response = self.client.patch(detail, {
            'phone': '+998901234567', 'salary': '4000000', 'active': True,
            'hired_at': str(timezone.localdate()), 'notes': 'Bosh admin'
        }, format='json')
        self.assertEqual(response.status_code, 200)
        employee.refresh_from_db()
        self.assertEqual(employee.salary, Decimal('4000000'))
        self.assertEqual(employee.phone, '+998901234567')

        period = timezone.localdate().strftime('%Y-%m')
        payload = {
            'period': period, 'amount': '4000000', 'payment_method': 'card',
            'paid_on': str(timezone.localdate()), 'note': 'To‘liq oylik'
        }
        pay_url = f'/api/v1/staff/{employee.id}/salary-payments/'
        self.assertEqual(self.client.post(pay_url, payload, format='json').status_code, 201)
        self.assertEqual(self.client.post(pay_url, payload, format='json').status_code, 409)
        self.assertEqual(SalaryPayment.objects.filter(employee=employee).count(), 1)
        expense = Expense.objects.get(category='Ish haqi')
        self.assertEqual(expense.amount, Decimal('4000000'))
        self.assertEqual(expense.recipient, 'Menejer')
        dashboard = self.client.get('/api/v1/dashboard/').data
        self.assertEqual(Decimal(dashboard['expenses']), Decimal('4000000'))

        self.client.force_authenticate(self.cashier)
        self.assertEqual(self.client.patch(detail, {'salary': '1'}, format='json').status_code, 403)
        self.assertEqual(self.client.get(pay_url).status_code, 403)

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

        # Stolni faqat admin qo'sha oladi, kassir ro'yxatni ko'radi xolos.
        self.assertEqual(self.client.post('/api/v1/tables/', {'number': 99}, format='json').status_code, 403)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.post('/api/v1/tables/', {'number': 99}, format='json').status_code, 201)
        self.assertEqual(self.client.post('/api/v1/tables/', {'number': 99}, format='json').status_code, 400)

    def test_prep_tickets_split_by_station_and_carry_no_prices(self):
        from catalog.models import Station
        from operations import printing

        drinks = Category.objects.create(branch=self.branch, name='Ichimliklar', station=Station.COUNTER)
        water = Dish.objects.create(branch=self.branch, category=drinks, name='Suv', price=5000)
        # Kategoriyasi kassa, lekin o'zi oshxonada damlanadi - alohida qiymat kategoriyadan ustun.
        tea = Dish.objects.create(branch=self.branch, category=drinks, name='Choy', price=8000, station=Station.KITCHEN)

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
        self.assertIn('HONIM', text)
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
        self.assertEqual(listed, {'cash', 'card', 'uzum', 'click', 'yandex'})

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
            self.assertIn('Tort'.encode(), workbook.read('xl/worksheets/sheet4.xml'))

        admin = User.objects.create_user('report_admin', password='Safe-test-password-52!', role='admin', branch=self.branch)
        self.client.force_authenticate(admin)
        self.assertEqual(self.client.get(url).status_code, 200)
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
        self.client.patch('/api/v1/tables/%s/' % table['id'], {'seats': 6}, format='json')
        self.client.delete('/api/v1/tables/%s/' % table['id'])
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
    """Oyliklar bo'limi: kelishilgan va to'langan summa hech qachon aralashmasin."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.other = Branch.objects.create(name='Two', slug='two')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch, salary=Decimal('9000000'))
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch, salary=Decimal('3000000'), first_name='Kassir')
        self.admin = User.objects.create_user('admin', password='test-only-long-password', role='admin', branch=self.branch, salary=Decimal('5000000'), first_name='Admin')
        self.client = APIClient()
        self.client.force_authenticate(self.owner)
        self.month = timezone.localdate().replace(day=1)

    def pay(self, employee, amount, period=None, method='cash'):
        return self.client.post(f'/api/v1/staff/{employee.id}/salary-payments/', {
            'period': (period or self.month).strftime('%Y-%m'),
            'amount': str(amount),
            'payment_method': method,
            'paid_on': str(timezone.localdate()),
            'note': '',
        }, format='json')

    def test_empty_month_shows_the_whole_wage_bill_as_unpaid(self):
        data = self.client.get('/api/v1/payroll/').data
        # Superadmin o'z oyligini bu yerda yuritmaydi, shuning uchun fondga kirmaydi.
        self.assertEqual(data['summary']['agreed'], '8000000.00')
        self.assertEqual(data['summary']['paid'], '0.00')
        self.assertEqual(data['summary']['remaining'], '8000000.00')
        self.assertEqual(data['summary']['paid_count'], 0)
        self.assertEqual(data['summary']['staff_count'], 2)
        self.assertEqual({row['status'] for row in data['employees']}, {'unpaid'})
        self.assertNotIn('owner', [row['username'] for row in data['employees']])

    def test_paid_partial_and_unpaid_are_told_apart(self):
        self.assertEqual(self.pay(self.cashier, Decimal('3000000')).status_code, 201)
        self.assertEqual(self.pay(self.admin, Decimal('2000000')).status_code, 201)
        data = self.client.get('/api/v1/payroll/').data
        rows = {row['username']: row for row in data['employees']}
        self.assertEqual(rows['cashier']['status'], 'paid')
        self.assertEqual(rows['cashier']['difference'], '0.00')
        # Kelishilgandan kam berilgan bo'lsa, farqi qarz bo'lib qoladi.
        self.assertEqual(rows['admin']['status'], 'partial')
        self.assertEqual(rows['admin']['difference'], '3000000.00')
        self.assertEqual(data['summary']['paid'], '5000000.00')
        self.assertEqual(data['summary']['remaining'], '3000000.00')
        self.assertEqual(data['summary']['paid_count'], 2)

    def test_payment_methods_and_lifetime_totals_are_grouped_not_split(self):
        self.pay(self.cashier, Decimal('3000000'), method='cash')
        self.pay(self.admin, Decimal('5000000'), method='card')
        previous = (self.month - timedelta(days=1)).replace(day=1)
        self.pay(self.cashier, Decimal('2500000'), period=previous, method='cash')

        data = self.client.get('/api/v1/payroll/').data
        methods = {row['method']: row for row in data['summary']['by_method']}
        self.assertEqual(methods['cash']['amount'], '3000000.00')
        self.assertEqual(methods['card']['amount'], '5000000.00')

        # Umriy jamlanma bitta xodim uchun bitta qator bo'lishi kerak —
        # Meta.ordering GROUP BY'ni bo'lib yuborsa, ikkita qator chiqardi.
        lifetime = {row['name']: row for row in data['lifetime']}
        self.assertEqual(lifetime['Kassir']['total'], '5500000.00')
        self.assertEqual(lifetime['Kassir']['months'], 2)
        self.assertEqual(lifetime['Admin']['total'], '5000000.00')
        self.assertEqual(data['all_time'], {'total': '10500000.00', 'payments': 3})

    def test_month_filter_and_trend_cover_the_history(self):
        previous = (self.month - timedelta(days=1)).replace(day=1)
        self.pay(self.cashier, Decimal('2500000'), period=previous)
        data = self.client.get(f'/api/v1/payroll/?month={previous:%Y-%m}').data
        self.assertEqual(data['month'], previous.strftime('%Y-%m'))
        self.assertEqual(data['summary']['paid'], '2500000.00')
        self.assertIn(previous.strftime('%Y-%m'), data['months'])

        self.assertEqual(len(data['trend']), 12)
        point = next(row for row in data['trend'] if row['period'] == previous.strftime('%Y-%m'))
        self.assertEqual(point['total'], '2500000.00')
        # To'lovsiz oylar nol bilan to'ldiriladi, grafikda bo'shliq qolmaydi.
        self.assertEqual(sum(1 for row in data['trend'] if row['total'] == '0.00'), 11)

    def test_overpaying_one_employee_does_not_hide_another_debt(self):
        # Kassirga kelishilgandan ko'p, adminga umuman berilmadi.
        self.pay(self.cashier, Decimal('6000000'))
        data = self.client.get('/api/v1/payroll/').data
        rows = {row['username']: row for row in data['employees']}
        self.assertEqual(rows['cashier']['status'], 'paid')
        self.assertEqual(rows['admin']['status'], 'unpaid')
        # Qarz har xodim bo'yicha alohida: adminning 5 000 000 qarzi
        # kassirga ortiqcha berilgan pul bilan yopilmaydi.
        self.assertEqual(data['summary']['remaining'], '5000000.00')
        self.assertEqual(data['summary']['paid'], '6000000.00')
        # Ortiqcha to'lov manfiy farq bo'lib chiqmaydi.
        self.assertEqual(rows['cashier']['difference'], '0.00')

    def test_employee_without_an_agreed_salary_is_not_called_unpaid(self):
        nobody = User.objects.create_user('yangi', password='test-only-long-password', role='kitchen', branch=self.branch, first_name='Yangi')
        data = self.client.get('/api/v1/payroll/').data
        rows = {row['username']: row for row in data['employees']}
        # Oyligi kiritilmagan xodim «to'lanmagan» emas, «kelishilmagan».
        self.assertEqual(rows['yangi']['status'], 'no_agreement')
        self.assertEqual(rows['yangi']['difference'], '0.00')
        # Qarzga ham, qamrovga ham kirmaydi.
        self.assertEqual(data['summary']['remaining'], '8000000.00')
        self.assertEqual(data['summary']['expected'], 2)
        self.assertEqual(data['summary']['without_agreement'], 1)
        self.assertEqual(nobody.salary, Decimal('0'))

    def test_coverage_counts_how_many_agreed_staff_were_paid(self):
        self.pay(self.cashier, Decimal('4500000'))
        summary = self.client.get('/api/v1/payroll/').data['summary']
        self.assertEqual(summary['expected'], 2)
        self.assertEqual(summary['covered'], 1)

    def test_other_branches_and_other_roles_stay_out(self):
        stranger = User.objects.create_user('stranger', password='test-only-long-password', role='cashier', branch=self.other, salary=Decimal('7000000'))
        self.assertNotIn('stranger', [row['username'] for row in self.client.get('/api/v1/payroll/').data['employees']])
        self.assertEqual(stranger.branch, self.other)

        for role in ('admin', 'cashier', 'kitchen'):
            client = APIClient()
            client.force_authenticate(User.objects.create_user(f'{role}-x', password='test-only-long-password', role=role, branch=self.branch))
            self.assertEqual(client.get('/api/v1/payroll/').status_code, 403)

    def test_future_and_broken_months_are_refused(self):
        future = (self.month.replace(day=28) + timedelta(days=10)).replace(day=1)
        self.assertEqual(self.client.get(f'/api/v1/payroll/?month={future:%Y-%m}').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/payroll/?month=2026-13').status_code, 400)
        self.assertEqual(self.client.get('/api/v1/payroll/?month=sentabr').status_code, 400)

    def test_salary_payment_also_lands_in_expenses_exactly_once(self):
        self.pay(self.cashier, Decimal('3000000'))
        # Moliya hisobida oylik xarajatlar ichida turadi — ustiga qo'shilmasligi kerak.
        expenses = Expense.objects.filter(branch=self.branch, category='Ish haqi')
        self.assertEqual(expenses.count(), 1)
        self.assertEqual(expenses.first().amount, Decimal('3000000'))
        self.assertEqual(
            self.client.get('/api/v1/payroll/').data['summary']['paid'],
            str(expenses.first().amount),
        )


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
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch, salary=Decimal('3000000'), first_name='Kassir')
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
        self.client.post(f'/api/v1/staff/{self.cashier.id}/salary-payments/', {
            'period': timezone.localdate().strftime('%Y-%m'), 'amount': '3000000',
            'payment_method': 'cash', 'paid_on': str(timezone.localdate()), 'note': '',
        }, format='json')

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
        self.client.post(f'/api/v1/staff/{self.cashier.id}/salary-payments/', {
            'period': timezone.localdate().strftime('%Y-%m'), 'amount': '3000000',
            'payment_method': 'cash', 'paid_on': str(timezone.localdate()), 'note': '',
        }, format='json')
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
        self.admin = User.objects.create_user('admin', password='test-only-long-password', role='admin', branch=self.branch, first_name='Admin')
        self.cashier = User.objects.create_user('cashier', password='test-only-long-password', role='cashier', branch=self.branch)
        self.category = Category.objects.create(branch=self.branch, name='Taom')
        self.dish = Dish.objects.create(branch=self.branch, category=self.category, name='Manti', price=Decimal('12000'))
        # 1 kg kartoshka 5 000 so'm, 1 kg go'sht 80 000 so'm.
        self.potato = Ingredient.objects.create(branch=self.branch, name='Kartoshka', unit='kg', quantity=Decimal('100'), unit_cost=Decimal('5000'))
        self.meat = Ingredient.objects.create(branch=self.branch, name='Go‘sht', unit='kg', quantity=Decimal('50'), unit_cost=Decimal('80000'))
        self.client = APIClient()
        self.client.force_authenticate(self.admin)
        self.today = timezone.localdate()

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
        # Admin esa 2 kg go'sht va 4 kg kartoshka ketgan deb yozdi.
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

    def test_only_managers_write_and_only_owner_compares(self):
        cashier = APIClient()
        cashier.force_authenticate(self.cashier)
        self.assertEqual(cashier.get('/api/v1/daily-usage/').status_code, 403)
        self.assertEqual(cashier.post('/api/v1/daily-usage/', {'date': str(self.today), 'lines': []}, format='json').status_code, 403)
        # Admin kiritadi, lekin solishtirishni ko'rmaydi — bu superadmin nazorati.
        self.assertEqual(self.client.get('/api/v1/daily-usage/compare/').status_code, 403)
        owner = APIClient()
        owner.force_authenticate(self.owner)
        self.assertEqual(owner.get('/api/v1/daily-usage/compare/').status_code, 200)


class FullSetupFlowTests(TestCase):
    """Egasi aytgan tartib: masalliq -> narx -> taom + retsept -> sotuv -> kunlik hisobot."""

    def setUp(self):
        self.branch = Branch.objects.create(name='One', slug='one')
        self.owner = User.objects.create_user('owner', password='test-only-long-password', role='owner', branch=self.branch)
        self.admin = User.objects.create_user('admin', password='test-only-long-password', role='admin', branch=self.branch, first_name='Admin')
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
            'selling_price': 12000, 'active': True,
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
                'selling_price': 12000, 'active': True,
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
            'selling_price': 12000, 'active': True,
            'lines': [{'ingredient': meat['id'], 'quantity': 0.020}],
        }, format='json')
        self.client.post('/api/v1/stock/', {
            'key': str(uuid4()), 'ingredient': meat['id'], 'kind': 'receipt',
            'quantity': '10', 'cost_total': '800000', 'date': str(timezone.localdate()), 'note': 'x',
        }, format='json')
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
