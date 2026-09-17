from django.db import models
from django.db.models import Q
from users.models import Branch, User


class Order(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    cashier = models.ForeignKey(User, on_delete=models.PROTECT)
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    table = models.CharField(max_length=40, blank=True)
    waiter = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, default='open', choices=[('open', 'Ochiq'), ('paid', 'To‘langan')])
    total = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=10, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True)
    preparation_status = models.CharField(max_length=12, default='queued', choices=[('queued', 'Yangi'), ('preparing', 'Tayyorlanmoqda'), ('ready', 'Tayyor'), ('served', 'Topshirildi')])
    started_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [models.UniqueConstraint(fields=['branch', 'key'], name='order_idempotency'), models.CheckConstraint(condition=Q(total__gt=0), name='order_positive_total')]


class OrderLine(models.Model):
    order = models.ForeignKey(Order, related_name='lines', on_delete=models.PROTECT)
    dish = models.ForeignKey('catalog.Dish', on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    note = models.CharField(max_length=200, blank=True)
    # Snapshot of recipe cost at the moment of sale. It keeps old reports correct
    # after ingredients or recipes are updated later.
    cost_per_unit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cost_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)


class Expense(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    category = models.CharField(max_length=80)
    purpose = models.CharField(max_length=250)
    recipient = models.CharField(max_length=120, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=[('cash', 'Naqd'), ('card', 'Karta'), ('unpaid', 'To‘lanmagan')])
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        constraints = [models.UniqueConstraint(fields=['branch', 'key'], name='expense_idempotency'), models.CheckConstraint(condition=Q(amount__gt=0), name='expense_positive_amount')]


class SalaryPayment(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    employee = models.ForeignKey(User, on_delete=models.PROTECT, related_name='salary_payments')
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='processed_salary_payments')
    expense = models.OneToOneField(Expense, on_delete=models.PROTECT, related_name='salary_payment')
    period = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=[('cash', 'Naqd'), ('card', 'Karta')])
    paid_on = models.DateField()
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-period', '-id']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'employee', 'period'], name='salary_one_payment_per_period'),
            models.CheckConstraint(condition=Q(amount__gt=0), name='salary_payment_positive_amount'),
        ]


class Ingredient(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    unit = models.CharField(max_length=10, choices=[('kg', 'kg'), ('l', 'l'), ('dona', 'dona')])
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    minimum = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    class Meta:
        ordering = ['name']
        constraints = [models.CheckConstraint(condition=Q(quantity__gte=0), name='stock_nonnegative'), models.UniqueConstraint(fields=['branch', 'name'], name='ingredient_branch_name')]


class StockMovement(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    kind = models.CharField(max_length=18, choices=[('receipt', 'Kirim'), ('consumption', 'Kunlik sarf'), ('sale_consumption', 'Sotuv bo‘yicha sarf')])
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    date = models.DateField()
    note = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['branch', 'key'], name='stock_idempotency'), models.CheckConstraint(condition=Q(quantity__gt=0), name='stock_positive_movement')]


class Recipe(models.Model):
    """A batch calculation; it may be saved before its menu dish is created."""
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    dish = models.OneToOneField('catalog.Dish', on_delete=models.PROTECT, null=True, blank=True, related_name='recipe')
    name = models.CharField(max_length=120)
    yield_quantity = models.DecimalField(max_digits=12, decimal_places=3)
    yield_unit = models.CharField(max_length=20, default='porsiya')
    selling_price = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'name'], name='recipe_branch_name'),
            models.CheckConstraint(condition=Q(yield_quantity__gt=0), name='recipe_positive_yield'),
        ]


class RecipeLine(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='lines')
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    # Cost is kept on a line because the user may use a different batch cost for
    # the same ingredient in different calculations.
    batch_cost = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['recipe', 'ingredient'], name='recipe_ingredient_once'),
            models.CheckConstraint(condition=Q(quantity__gt=0), name='recipe_line_positive_quantity'),
            models.CheckConstraint(condition=Q(batch_cost__gte=0), name='recipe_line_nonnegative_cost'),
        ]
