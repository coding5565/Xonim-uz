from datetime import datetime, time, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import uuid4
from zipfile import ZipFile
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from users.models import Branch, User
from catalog.models import Category, Dish
from .models import Order, Expense, Ingredient, SalaryPayment, StockMovement
from .services import create_order, move_stock, Conflict


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
