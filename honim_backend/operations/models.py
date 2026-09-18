from decimal import Decimal

from django.db import models
from django.db.models import Q
from users.models import Branch, User

# Single source of truth for how a sale was settled. Adding a provider here is
# enough for the till, the summary, the dashboard and the reports to pick it up.
SALE_PAYMENT_METHODS = [
    ('cash', 'Naqd'),
    ('card', 'Karta'),
    ('uzum', 'Uzum'),
    ('click', 'Click'),
    ('yandex', 'Yandex'),
]
SALE_PAYMENT_LABELS = dict(SALE_PAYMENT_METHODS)
SALE_PAYMENT_CHOICES = [method for method, _ in SALE_PAYMENT_METHODS]

# Hisob holati. «cancelled» — to'lovsiz bekor qilingan, «refunded» — to'langandan
# keyin pul qaytarilgan. Ikkalasi ham tushumga KIRMAYDI, lekin tarixda qoladi:
# yozuvni o'chirish nazoratni yo'q qilardi.
ORDER_STATUSES = [
    ('open', 'Ochiq'),
    ('paid', 'To‘langan'),
    ('cancelled', 'Bekor qilingan'),
    ('refunded', 'Qaytarilgan'),
]
ORDER_STATUS_LABELS = dict(ORDER_STATUSES)
# Yopilgan, ya'ni stolni bo'shatadigan holatlar.
CLOSED_STATUSES = ['paid', 'cancelled', 'refunded']


class TableZone(models.TextChoices):
    """Zaldagi joylashuv. Kassir ekrani shu bo'yicha chiziladi."""

    HALL_LEFT = 'hall_left', 'Ichkari — chap tomon'
    HALL_RIGHT = 'hall_right', 'Ichkari — o‘ng tomon'
    OUTSIDE = 'outside', 'Tashqari'


class TableSeating(models.TextChoices):
    DIVAN = 'divan', 'Divan'
    CHAIR = 'chair', 'Stulli'


class Table(models.Model):
    """Zaldagi stol. Kassir ekranining asosi: bo'sh yoki ochiq hisobi bor."""

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='tables')
    number = models.PositiveIntegerField()
    name = models.CharField(max_length=40, blank=True)
    seats = models.PositiveIntegerField(default=4)
    zone = models.CharField(max_length=12, choices=TableZone.choices, default=TableZone.HALL_RIGHT)
    seating = models.CharField(max_length=8, choices=TableSeating.choices, default=TableSeating.CHAIR)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ['zone', 'number', 'id']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'number'], name='table_branch_number'),
            models.CheckConstraint(condition=Q(number__gt=0), name='table_positive_number'),
        ]

    @property
    def label(self):
        return self.name or f'{self.number}-stol'


class Order(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    cashier = models.ForeignKey(User, on_delete=models.PROTECT)
    # Matnli `table` maydoni saqlanib qoldi: cheklar, talonlar va hisobotlar shunga
    # tayanadi. table_ref esa stol xaritasi uchun, olib ketishda bo'sh bo'ladi.
    table_ref = models.ForeignKey(Table, on_delete=models.PROTECT, null=True, blank=True, related_name='orders')
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    table = models.CharField(max_length=40, blank=True)
    waiter = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, default='open', choices=ORDER_STATUSES)
    total = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=10, blank=True, choices=SALE_PAYMENT_METHODS)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True)
    preparation_status = models.CharField(max_length=12, default='queued', choices=[('queued', 'Yangi'), ('preparing', 'Tayyorlanmoqda'), ('ready', 'Tayyor'), ('served', 'Topshirildi')])
    started_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    served_at = models.DateTimeField(null=True, blank=True)
    # Bekor qilish yoki qaytarish izi. Sababsiz bekor qilib bo'lmaydi —
    # keyin nima uchun qilinganini aniqlash uchun.
    void_reason = models.CharField(max_length=200, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(User, on_delete=models.PROTECT, null=True, blank=True, related_name='voided_orders')

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'key'], name='order_idempotency'),
            models.CheckConstraint(condition=Q(total__gt=0), name='order_positive_total'),
            # Bekor qilingan yoki qaytarilgan hisobda sabab ham, vaqt ham bo'lishi shart.
            models.CheckConstraint(
                condition=~Q(status__in=['cancelled', 'refunded']) | (Q(voided_at__isnull=False) & ~Q(void_reason='')),
                name='order_void_needs_reason',
            ),
        ]


class OrderLine(models.Model):
    order = models.ForeignKey(Order, related_name='lines', on_delete=models.PROTECT)
    dish = models.ForeignKey('catalog.Dish', on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    note = models.CharField(max_length=200, blank=True)
    # Set when the guest ordered more after the bill was opened. Lines from the
    # first order keep it empty, and the key makes a retried add a no-op.
    batch_key = models.UUIDField(null=True, blank=True, db_index=True)
    added_at = models.DateTimeField(null=True, blank=True)
    # Snapshot of recipe cost at the moment of sale. It keeps old reports correct
    # after ingredients or recipes are updated later.
    cost_per_unit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cost_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        # Receipts and the kitchen ticket must show the first order before the additions.
        ordering = ['id']


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


class ShiftClose(models.Model):
    """Kun yakuni: kassada qancha pul bo'lishi kerak edi va qancha chiqdi.

    Kutilgan naqd pul yopilish paytida MUZLATILADI. Keyin o'sha kunga
    tegishli biror yozuv o'zgarsa ham, yopilgan kun hisobi o'zgarmaydi —
    aks holda solishtirish ma'nosini yo'qotardi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    date = models.DateField()
    # Naqd savdodan kunlik naqd xarajat ayirilgan qiymat.
    expected_cash = models.DecimalField(max_digits=14, decimal_places=2)
    counted_cash = models.DecimalField(max_digits=14, decimal_places=2)
    difference = models.DecimalField(max_digits=14, decimal_places=2)
    revenue = models.DecimalField(max_digits=14, decimal_places=2)
    orders = models.PositiveIntegerField(default=0)
    # To'lov turlari kesimi o'sha kun holatida saqlanadi.
    breakdown = models.JSONField(default=dict, blank=True)
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        constraints = [
            # Bir kunni ikki marta yopib bo'lmaydi.
            models.UniqueConstraint(fields=['branch', 'date'], name='shift_one_close_per_day'),
            models.CheckConstraint(condition=Q(counted_cash__gte=0), name='shift_nonnegative_count'),
        ]


class Ingredient(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    unit = models.CharField(max_length=10, choices=[('kg', 'kg'), ('l', 'l'), ('dona', 'dona')])
    quantity = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    minimum = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    # O'rtacha tortilgan tannarx: har kirimda qayta hisoblanadi. Sarf shu narxda
    # baholanadi, shuning uchun eski partiya narxi keyingi sarfga ta'sir qiladi.
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    @property
    def stock_value(self):
        return (self.quantity * self.unit_cost).quantize(Decimal('0.01'))

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
    # Narx harakat paytida muzlatiladi: keyin tannarx o'zgarsa ham tarix buzilmaydi.
    # Kirimda foydalanuvchi kiritadi, sarfda o'sha paytdagi o'rtacha tannarxdan olinadi.
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)
    cost_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    date = models.DateField()
    note = models.CharField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'key'], name='stock_idempotency'),
            models.CheckConstraint(condition=Q(quantity__gt=0), name='stock_positive_movement'),
            models.CheckConstraint(condition=Q(cost_total__gte=0), name='stock_nonnegative_cost'),
        ]
        indexes = [models.Index(fields=['branch', 'ingredient', 'date'], name='stock_branch_item_date_idx')]


class DailyUsage(models.Model):
    """Admin kechqurun kiritadigan HAQIQIY sarf.

    Bu yozuv ombordan hech narsa ayirmaydi. Sabab: taom sotilganda retsept
    bo'yicha allaqachon ayriladi, shuning uchun bu yerda ham ayirilsa bitta
    mahsulot ikki marta chiqib ketardi.

    Uning vazifasi boshqa: tizim hisoblagan (nazariy) sarf bilan haqiqatda
    ketgan miqdorni solishtirish. Farq kattalashsa — ortiqcha solinyapti,
    isrof bo'lyapti yoki yo'qolyapti.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name='daily_usage')
    date = models.DateField()
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'ingredient__name']
        constraints = [
            # Bir kunda bir mahsulot uchun bitta yozuv: qayta kiritilsa
            # ustiga yoziladi, qo'shilmaydi.
            models.UniqueConstraint(fields=['branch', 'ingredient', 'date'], name='daily_usage_once_per_day'),
            models.CheckConstraint(condition=Q(quantity__gt=0), name='daily_usage_positive'),
        ]
        indexes = [models.Index(fields=['branch', 'date'], name='daily_usage_branch_date_idx')]


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
