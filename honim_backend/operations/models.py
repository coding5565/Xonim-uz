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


# Buyurtma qayerdan kelgani. To'lov usulidan farqli: zaldagi mijoz ham Uzum
# ilovasi bilan to'lashi mumkin, lekin u yetkazib berish buyurtmasi emas.
SALE_CHANNELS = [
    ('hall', 'Zal'),
    ('takeaway', 'Olib ketish'),
    ('uzum', 'Uzum'),
    ('yandex', 'Yandex'),
]
SALE_CHANNEL_LABELS = dict(SALE_CHANNELS)
# Yetkazib berish platformalari — puli kassaga tushmaydi, hisobga o'tadi.
DELIVERY_CHANNELS = ['uzum', 'yandex']


class Waiter(models.Model):
    """Ofitsiant va uning hisobdan oladigan ulushi.

    Ulush foizda yuriladi: ko'proq sotgan ko'proq oladi. Foizni superadmin
    belgilaydi, kassir esa buyurtmaga ofitsiantni bog'laydi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='waiters')
    name = models.CharField(max_length=80)
    phone = models.CharField(max_length=30, blank=True)
    # Hisob summasidan necha foiz. 0 bo'lsa ulush hisoblanmaydi.
    commission = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'name'], name='waiter_branch_name'),
            models.CheckConstraint(
                condition=Q(commission__gte=0) & Q(commission__lte=100),
                name='waiter_commission_range',
            ),
        ]


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
    # Matnli `waiter` eski yozuvlar uchun qoladi; yangi buyurtmalar
    # ofitsiant kartasiga bog'lanadi va ulush shundan hisoblanadi.
    waiter = models.CharField(max_length=100, blank=True)
    waiter_ref = models.ForeignKey(Waiter, on_delete=models.PROTECT, null=True, blank=True, related_name='orders')
    # Sotuv paytidagi foiz muzlatiladi: keyin foiz o'zgarsa ham
    # o'tgan buyurtmadagi ulush o'zgarmaydi.
    waiter_commission = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    channel = models.CharField(max_length=10, default='hall', choices=SALE_CHANNELS)
    status = models.CharField(max_length=10, default='open', choices=ORDER_STATUSES)
    # `total` — mijoz to'laydigan summa, ya'ni chegirma AYRILGANDAN keyingi
    # qiymat. Tushum shu maydondan hisoblanadi, shuning uchun chegirma
    # avtomatik ravishda tushumni kamaytiradi va alohida ayirish shart emas.
    total = models.DecimalField(max_digits=14, decimal_places=2)
    discount = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    discount_reason = models.CharField(max_length=120, blank=True)
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
            models.CheckConstraint(condition=Q(discount__gte=0), name='order_nonnegative_discount'),
            # Bekor qilingan yoki qaytarilgan hisobda sabab ham, vaqt ham bo'lishi shart.
            models.CheckConstraint(
                condition=~Q(status__in=['cancelled', 'refunded']) | (Q(voided_at__isnull=False) & ~Q(void_reason='')),
                name='order_void_needs_reason',
            ),
        ]
        # Deyarli har bir so'rov filial + sana bo'yicha kesadi: tayyor taomlar
        # qoldig'i (created_at) har sotuvda, hisobotlar esa (paid_at) bo'yicha.
        # Indekssiz ular buyurtmalar jadvalini boshdan-oxir ko'zdan kechiradi.
        indexes = [
            models.Index(fields=['branch', 'created_at'], name='order_branch_created_idx'),
            models.Index(fields=['branch', 'paid_at'], name='order_branch_paid_idx'),
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
    # Olti xona: bitta porsiyaga ketadigan ziravor grammning mingdan biriga
    # teng bo'lishi mumkin (24 ta mantiga 1 g -> bittasiga 0.0000417 kg).
    # Uch xonada bu nolga aylanib, ombordan umuman ayrilmay qolardi.
    quantity = models.DecimalField(max_digits=14, decimal_places=6, default=0)
    minimum = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    # O'rtacha tortilgan tannarx: har kirimda qayta hisoblanadi. Sarf shu narxda
    # baholanadi, shuning uchun eski partiya narxi keyingi sarfga ta'sir qiladi.
    unit_cost = models.DecimalField(max_digits=14, decimal_places=4, default=0)

    class Meta:
        ordering = ['name']
        # Qoldiq manfiy bo'lishiga ruxsat beriladi: retsept bo'yicha ayirish
        # TAXMIN, sotuvni to'xtatmasligi kerak. Ba'zida taomga retseptdan ko'p
        # ketadi va kassir shu sababli pul ololmay qolishi mumkin emas. Manfiy
        # qoldiq esa superadminga «hisob haqiqatdan ajralib ketdi» degan
        # signal bo'ladi. Qo'lda chiqim yozishda tekshiruv o'z joyida qoladi
        # (services.move_stock), ya'ni xato kiritishdan himoya yo'qolmaydi.
        constraints = [models.UniqueConstraint(fields=['branch', 'name'], name='ingredient_branch_name')]

    @property
    def stock_value(self):
        return (self.quantity * self.unit_cost).quantize(Decimal('0.01'))


class StockMovement(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    kind = models.CharField(max_length=18, choices=[('receipt', 'Kirim'), ('consumption', 'Kunlik sarf'), ('sale_consumption', 'Sotuv bo‘yicha sarf')])
    # Sotuvda ayriladigan miqdor retsept ulushidan chiqadi va u juda
    # mayda bo'lishi mumkin — ombor maydoni bilan bir xil aniqlikda.
    quantity = models.DecimalField(max_digits=14, decimal_places=6)
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


class DishPrep(models.Model):
    """Bugun oshxonada nechta porsiya tayyorlangani.

    Bir kunda bir taomga bir nechta yozuv bo'ladi — ertalab 20 ta, tushda
    yana 15 ta. Ular qo'shiladi, ustiga yozilmaydi: shunda kun davomida
    nima qo'shilgani ham ko'rinib turadi.

    Diqqat: bu yozuv ombordan masalliq AYIRMAYDI. Masalliq sotuv paytida
    retsept bo'yicha ayriladi va shundayligicha qoladi — aks holda bitta
    porsiya ikki marta hisobdan chiqardi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    dish = models.ForeignKey('catalog.Dish', on_delete=models.PROTECT, related_name='preps')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    date = models.DateField()
    quantity = models.PositiveIntegerField()
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        constraints = [models.CheckConstraint(condition=Q(quantity__gt=0), name='dish_prep_positive')]
        indexes = [models.Index(fields=['branch', 'date'], name='dish_prep_branch_date_idx')]


class AssistantChat(models.Model):
    """Saqlangan AI suhbati. Har foydalanuvchi faqat o'zinikini ko'radi."""

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='assistant_chats')
    # Sarlavha birinchi savoldan olinadi — foydalanuvchi qo'lda yozmaydi.
    title = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at', '-id']
        indexes = [models.Index(fields=['branch', 'actor', '-updated_at'], name='chat_owner_recent_idx')]


class AssistantMessage(models.Model):
    """Suhbatdagi bitta gap. Grafiklar javob bilan birga saqlanadi."""

    chat = models.ForeignKey(AssistantChat, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=[('user', 'Savol'), ('assistant', 'Javob')])
    text = models.TextField()
    charts = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']


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
    # Sotuv narxi bu yerda saqlanmaydi: u menyudagi taomning narxi. Ikki joyda
    # turgan narx muqarrar ravishda bir-biridan uzoqlashardi.
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
