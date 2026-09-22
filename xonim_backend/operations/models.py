from decimal import Decimal

from django.db import models
from django.db.models import F, Q

from users.models import Branch, Employee, User

# Single source of truth for how a sale was settled. Adding a provider here is
# enough for the till, the summary, the dashboard and the reports to pick it up.
SALE_PAYMENT_METHODS = [
    ('cash', 'Naqd'),
    ('card', 'Karta'),
    # Bank terminali kartadan alohida yuriladi: pul bir xil yo'ldan kelsa
    # ham, egasi qaysi qurilmadan qancha tushganini ajratib ko'rishni
    # so'radi — hisob-kitob bank bilan shu bo'yicha solishtiriladi.
    ('terminal', 'Terminal'),
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
# Platforma odatda ushlab qoladigan ulush. Yangi filialda shu qiymatdan
# boshlanadi, keyin shartnomaga qarab superadmin o'zgartiradi.
DEFAULT_PLATFORM_COMMISSION = Decimal('30')


class ChannelFee(models.Model):
    """Yetkazib berish platformasi hisobdan ushlab qoladigan ulush.

    Uzum va Yandex buyurtma summasidan foiz oladi, qolgani restoran hisobiga
    tushadi. Foiz shartnoma bo'yicha o'zgarishi mumkin, shuning uchun u kodda
    emas, shu yerda turadi va superadmin tahrirlaydi.

    Diqqat: bu yerdagi foiz FAQAT yangi sotuvlarga qo'llanadi. Har bir
    buyurtma o'z foizini `Order.channel_commission` da muzlatib oladi — aks
    holda bugun foizni o'zgartirish o'tgan oyning hisobotini qayta yozib
    yuborardi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='channel_fees')
    channel = models.CharField(max_length=10, choices=SALE_CHANNELS)
    commission = models.DecimalField(max_digits=5, decimal_places=2, default=DEFAULT_PLATFORM_COMMISSION)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['channel']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'channel'], name='channel_fee_unique'),
            models.CheckConstraint(
                condition=Q(commission__gte=0) & Q(commission__lte=100),
                name='channel_fee_range',
            ),
        ]


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
    # Xizmat haqi: hisob summasining ustiga QO'SHILADI va butunlay
    # ofitsiantniki bo'ladi. 100 000 lik hisobga 10% qo'shilsa mijoz 110 000
    # to'laydi, 10 000 esa ofitsiant hisobiga o'tadi. Shuning uchun u
    # restoran tushumi EMAS: `total` tushum bo'lib qoladi, bu esa alohida.
    service_charge = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    channel = models.CharField(max_length=10, default='hall', choices=SALE_CHANNELS)
    # Platforma ushlab qolgan foiz, sotuv paytida muzlatiladi. Zal va olib
    # ketishda nol: u yerda hech kim hech narsa ushlamaydi.
    channel_commission = models.DecimalField(max_digits=5, decimal_places=2, default=0)
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
            models.CheckConstraint(condition=Q(service_charge__gte=0), name='order_nonnegative_service'),
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

    @property
    def payable(self):
        """Mijoz to'laydigan summa: hisob + ofitsiant xizmat haqi."""
        return self.total + self.service_charge


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
    # Bonus qatori: mijozga tekin berilgan porsiya. `price` nol bo'ladi,
    # shuning uchun hisob, tushum va o'rtacha chek o'z-o'zidan to'g'ri
    # qoladi — hech bir mavjud yig'indini o'zgartirish shart emas.
    bonus = models.BooleanField(default=False)
    # Sotuv paytidagi menyu narxi. Oddiy qatorda `price` bilan bir xil,
    # bonus qatorida esa «qanchalik pul tekin ketdi» degan savolga javob
    # beradigan yagona raqam.
    menu_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        # Receipts and the kitchen ticket must show the first order before the additions.
        ordering = ['id']


class BonusRule(models.Model):
    """Aksiya: shu kanalda shu taom buyurtma qilinsa, ustiga tekin qo‘shiladi.

    Uzum bilan shartnoma bo‘yicha mijoz «Bozor honim» buyurtma qilsa, nechta
    olganidan qat’i nazar ustiga bittasi tekin ketadi: 1 ta olsa 2 ta, 10 ta
    olsa 11 ta. Buyurtmada u taom bo‘lmasa, bonus ham yo‘q.

    Qoida kodda emas, shu yerda turadi va superadmin tahrirlaydi: aksiya
    tugashi, taom nomi o‘zgarishi yoki boshqa kanalga ko‘chishi mumkin.

    Diqqat: qoida o‘zgarsa o‘tgan buyurtmalar o‘zgarmaydi — bonus sotuv
    paytida oddiy qator bo‘lib yozilib qoladi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='bonus_rules')
    channel = models.CharField(max_length=10, choices=SALE_CHANNELS)
    dish = models.ForeignKey('catalog.Dish', on_delete=models.PROTECT, related_name='bonus_rules')
    # Nechta tekin ketishi. Mijoz nechta olganiga bog‘liq emas.
    free_quantity = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['channel', 'dish__name']
        constraints = [
            # Bir kanalda bir taomga bitta qoida: ikkitasi bo‘lsa nechta
            # tekin ketishi qaysi qator birinchi o‘qilganiga bog‘liq bo‘lardi.
            models.UniqueConstraint(fields=['branch', 'channel', 'dish'], name='bonus_rule_unique'),
            models.CheckConstraint(condition=Q(free_quantity__gt=0), name='bonus_rule_positive'),
        ]


class StaffMeal(models.Model):
    """Hodim o‘z oshxonamizdan yegan ovqat.

    Pul olinmaydi va bu hech kimning oyligiga ta’sir qilmaydi — yozuv faqat
    «oyiga qancha ketyapti» degan savolga javob berish uchun. Lekin ovqat
    haqiqatda chiqadi, shuning uchun masalliq ombordan ayiriladi va tannarx
    foydadan chiqib ketadi.

    Kim yegani izohda yoziladi: ro‘yxatdan tanlash shart emas, mehmon
    kelishi ham, bir kishi boshqasi uchun olishi ham mumkin.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    dish = models.ForeignKey('catalog.Dish', on_delete=models.PROTECT, related_name='staff_meals')
    # Nom va narx yozuv paytida muzlatiladi: taom keyin qayta nomlansa yoki
    # qimmatlashsa ham o‘tgan oyning hisoboti o‘zgarmaydi.
    name = models.CharField(max_length=120)
    quantity = models.PositiveIntegerField()
    menu_price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_per_unit = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cost_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    # Kim yegani. Bo‘sh qoldirib bo‘lmaydi — yozuvning butun ma’nosi shunda.
    note = models.CharField(max_length=200)
    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'key'], name='staff_meal_idempotency'),
            models.CheckConstraint(condition=Q(quantity__gt=0), name='staff_meal_positive'),
        ]
        indexes = [models.Index(fields=['branch', 'date'], name='staff_meal_branch_date_idx')]


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


# Hafta olti kun: yakshanba dam olish kuni va unga haq yozilmaydi.
WORK_DAYS_PER_WEEK = 6
# Python hafta kunlari: dushanba 0 ... yakshanba 6.
REST_WEEKDAY = 6


class Attendance(models.Model):
    """Xodim shu kuni ishga keldimi.

    Haq shu yerdan yig'iladi: belgilangan har bir kelgan kun xodimning
    balansiga kunlik summasini qo'shadi. Kunlik summa qatorga MUZLATILADI —
    keyin kelishuv o'zgarsa ham o'tgan kunlar qayta hisoblanmaydi.

    Yakshanba bu yerga tushmaydi: dam olish kuniga haq hisoblanmaydi.

    Kun belgilanmagan bo'lsa hech narsa yozilmaydi. «Belgilanmagan» bilan
    «kelmagan» bir xil narsa emas — birinchisi hali so'ralmagan savol,
    ikkinchisi esa javob, shuning uchun kelmagan kun ham qator bo'lib
    saqlanadi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='attendances')
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='marked_attendances')
    date = models.DateField()
    present = models.BooleanField(default=True)
    # Kelgan kun uchun yoziladigan haq. Kelmagan kunda nol bo'lib qoladi.
    daily_wage = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'employee_id']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'employee', 'date'], name='attendance_one_row_per_day'),
            models.CheckConstraint(condition=Q(daily_wage__gte=0), name='attendance_wage_not_negative'),
        ]
        indexes = [models.Index(fields=['branch', 'date'], name='attendance_branch_date_idx')]


class SalaryPayment(models.Model):
    """Xodimga berilgan pul. Istalgan kuni, istalgan summada.

    Oylik bir marta to'liq beriladigan narsa emas: haq har kuni yig'ilib
    boradi, pul esa kerak bo'lganda beriladi — hafta oxirida, avans sifatida
    yoki bir necha bo'lib. Shuning uchun bu yerda «qaysi oy uchun» degan
    qat'iy bog'lanish yo'q; `period` faqat hisobotni oyga bo'lish uchun
    saqlanadi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    employee = models.ForeignKey(Employee, on_delete=models.PROTECT, related_name='salary_payments')
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='processed_salary_payments')
    expense = models.OneToOneField(Expense, on_delete=models.PROTECT, related_name='salary_payment')
    # Ikki marta bosilgan tugma ikki marta pul bermasligi uchun.
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64, blank=True)
    period = models.DateField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=[('cash', 'Naqd'), ('card', 'Karta')])
    paid_on = models.DateField()
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_on', '-id']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'key'], name='salary_payment_idempotency'),
            models.CheckConstraint(condition=Q(amount__gt=0), name='salary_payment_positive_amount'),
        ]


class WaiterPayment(models.Model):
    """Ofitsiantga berilgan pul.

    Bu restoranning xarajati EMAS: pul mijozdan ofitsiant nomiga yig'ilgan
    va shu yerda unga topshiriladi. Shuning uchun Expense yaratilmaydi —
    aks holda hech qachon tushum bo'lmagan pul foydadan ikki marta
    ayirilardi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    waiter = models.ForeignKey(Waiter, on_delete=models.PROTECT, related_name='payments')
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='waiter_payments')
    # Ikki marta bosilgan tugma ikki marta pul bermasligi uchun.
    key = models.UUIDField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=[('cash', 'Naqd'), ('card', 'Karta')])
    paid_on = models.DateField()
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-paid_on', '-id']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'key'], name='waiter_payment_idempotency'),
            models.CheckConstraint(condition=Q(amount__gt=0), name='waiter_payment_positive_amount'),
        ]



# --- Hamkorlar -----------------------------------------------------------
# Maktab va universitetga taom arzonroq narxda jo'natiladi; ular kun davomida
# sotadi va kechqurun hisob beradi. Shuning uchun bu pul darhol tushum bo'lib
# kelmaydi — avval QARZ bo'lib turadi.

PARTNER_KINDS = [
    ('school', 'Maktab'),
    ('university', 'Universitet'),
    ('office', 'Ofis'),
    ('other', 'Boshqa'),
]
PARTNER_KIND_LABELS = dict(PARTNER_KINDS)

# «sent» — egasi aytgan PENDING: ovqat ketdi, hisobot ham, pul ham yo'q.
PARTNER_DELIVERY_STATUSES = [
    ('sent', 'Jo‘natildi'),
    ('reported', 'Hisobot berildi'),
    ('settled', 'Yopildi'),
    ('cancelled', 'Bekor qilingan'),
]
PARTNER_STATUS_LABELS = dict(PARTNER_DELIVERY_STATUSES)

# Maktab Uzum emas: yetkazib berish platformalari bu yerda yo'q, chunki
# ularda ushlanma bor va puli kassaga tushmaydi. Hamkor esa naqd, karta,
# terminal yoki Click bilan to'g'ridan-to'g'ri to'laydi.
PARTNER_PAYMENT_METHODS = [
    ('cash', 'Naqd'),
    ('card', 'Karta'),
    ('terminal', 'Terminal'),
    ('click', 'Click'),
]


class Partner(models.Model):
    """Maktab yoki universitet — biz taom yetkazib beradigan hamkor.

    Mijoz emas: mijoz pulni darhol to'laydi, hamkor esa kun davomida sotadi
    va kechqurun hisob beradi. Shuning uchun uning puli tushum bo'lib
    darhol kelmaydi — u avval qarz bo'lib turadi.

    O'chirilmaydi, faqat faolsizlantiriladi: jo'natmalar tarixi unga
    bog'langan. Ochiq jo'natmasi bor hamkorni faolsizlantirib ham
    bo'lmaydi — qarz ekrandan yo'qolib, hech kim uni so'ramay qolardi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='partners')
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=12, choices=PARTNER_KINDS, default='school')
    contact = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=200, blank=True)
    note = models.CharField(max_length=300, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'name'], name='partner_branch_name'),
        ]


class PartnerPrice(models.Model):
    """Shartnoma narxi: shu hamkor shu taomni qanchadan oladi.

    Narx aynan HAMKOR + TAOM juftligida turadi. Taomda tursa hamma hamkorga
    bir xil bo'lardi; hamkorda foiz bo'lib tursa «somsa arzon, ichimlik
    to'liq narxda» degan shartnomani yoza olmasdik.

    Bu ro'yxat faqat jo'natish paytida nusxa olinadi va qatorga muzlatiladi:
    ertaga narxni o'zgartirish kechagi jo'natmani qayta yozmaydi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name='prices')
    dish = models.ForeignKey('catalog.Dish', on_delete=models.PROTECT, related_name='partner_prices')
    price = models.DecimalField(max_digits=12, decimal_places=2)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['dish__name']
        constraints = [
            models.UniqueConstraint(fields=['partner', 'dish'], name='partner_price_once'),
            models.CheckConstraint(condition=Q(price__gt=0), name='partner_price_positive'),
        ]


class PartnerDelivery(models.Model):
    """Bitta jo'natma: ertalab hamkorga berib yuborilgan taomlar.

    Tayyor taomlar qoldig'iga TEGMAYDI: bu ovqat alohida pishiriladi va
    shundayligicha ketadi. Shuning uchun DishPrep hisobidan ayirilmaydi va
    tayyor porsiya yo'qligi jo'natishni to'xtatmaydi.

    Ombor esa jo'natish paytida ayriladi: go'sht oshxonadan CHIQDI, maktab
    uni sotgan-sotmagani go'shtga bog'liq emas. Shu sababli tannarx ham
    jo'natish kuniga yoziladi.

    Holat raqamlardan KELIB CHIQADI, qo'lda yozilmaydi:
        hisobot yo'q            -> sent      (egasi aytgan «pending»)
        berilgan < hisoblangan  -> reported  (qarz bor)
        berilgan >= hisoblangan -> settled   (yopildi)
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name='deliveries')
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='partner_deliveries')
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64)
    # Ish kuni: ertalab ketib kechqurun hisob berilgani BITTA kun. Tushum
    # ham, tannarx ham shu kunga yoziladi.
    date = models.DateField()
    status = models.CharField(max_length=10, default='sent', choices=PARTNER_DELIVERY_STATUSES)
    # Jo'natilganning to'liq qiymati hamkor narxida. Tushum EMAS — hali sotilmagan.
    total = models.DecimalField(max_digits=14, decimal_places=2)
    # Jo'natilganning retsept tannarxi, o'sha paytda muzlatilgan. Foyda
    # zanjiriga shu kiradi: ovqat chiqqan, demak xarajat bo'lgan.
    cost_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    # Hisobotdan keyin ma'lum bo'ladigan qarz: sotilganlar narxi.
    due_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    # Shu jo'natma bo'yicha tushgan pul.
    settled_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reported_at = models.DateTimeField(null=True, blank=True)
    reported_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name='reported_deliveries')
    closed_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=200, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name='cancelled_deliveries')

    class Meta:
        ordering = ['-date', '-id']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'key'], name='partner_delivery_idempotency'),
            models.CheckConstraint(condition=Q(total__gt=0), name='partner_delivery_positive_total'),
            models.CheckConstraint(
                condition=Q(cost_total__gte=0) & Q(due_total__gte=0) & Q(settled_total__gte=0),
                name='partner_delivery_nonnegative_money'),
            # Hisobot kelmagan jo'natma hech narsa qarz emas.
            models.CheckConstraint(
                condition=~Q(status='sent') | Q(due_total=0),
                name='partner_delivery_sent_owes_nothing'),
            # «Yopildi» degani pul to'liq kelgan degani — bog'liqlik bazada turadi.
            models.CheckConstraint(
                condition=~Q(status='settled') | Q(settled_total__gte=F('due_total')),
                name='partner_delivery_settled_is_paid'),
            models.CheckConstraint(
                condition=~Q(status__in=['reported', 'settled']) | Q(reported_at__isnull=False),
                name='partner_delivery_report_has_time'),
            models.CheckConstraint(
                condition=~Q(status='cancelled')
                | (Q(cancelled_at__isnull=False) & ~Q(cancel_reason='')),
                name='partner_delivery_cancel_needs_reason'),
        ]
        indexes = [
            models.Index(fields=['branch', 'date'], name='partner_delivery_date_idx'),
            models.Index(fields=['branch', 'status', 'date'], name='partner_delivery_status_idx'),
        ]

    @property
    def remaining(self):
        """Shu jo'natma bo'yicha qolgan qarz."""
        return self.due_total - self.settled_total


class PartnerDeliveryLine(models.Model):
    """Jo'natmadagi bitta taom: nechta ketdi va nechta sotildi.

    Narx ham, tannarx ham jo'natish paytida muzlatiladi. Sotilmagan
    porsiyalar hech qayerga qaytmaydi: ularning tannarxi qoladi, tushumi
    esa yo'q — egasi buni aynan shunday ko'rishi kerak, chunki bu «ertaga
    kamroq yuboring» degan signal. Masalliq ham qaytmaydi: maktabdan
    sovigan porsiya qaytadi, un va go'sht emas.
    """

    delivery = models.ForeignKey(PartnerDelivery, related_name='lines', on_delete=models.PROTECT)
    dish = models.ForeignKey('catalog.Dish', on_delete=models.PROTECT)
    name = models.CharField(max_length=120)
    # Hamkor narxi — shartnoma ro'yxatidan olinadi va shu yerda muzlaydi.
    price = models.DecimalField(max_digits=12, decimal_places=2)
    # O'sha kungi menyu narxi: «qanchaga arzon berdik» degan savolga javob
    # beradi. Hech qanday hisobga kirmaydi, faqat taqqoslash uchun.
    menu_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))
    quantity = models.PositiveIntegerField()
    cost_per_unit = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    cost_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
    # Hisobotda to'ldiriladi. Qayta hisobot berilsa USTIGA yoziladi, qo'shilmaydi.
    sold_quantity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['id']
        constraints = [
            models.UniqueConstraint(fields=['delivery', 'dish'], name='partner_line_dish_once'),
            models.CheckConstraint(condition=Q(quantity__gt=0), name='partner_line_positive_quantity'),
            models.CheckConstraint(condition=Q(price__gt=0), name='partner_line_positive_price'),
            # Berilganidan ko'pini sotib bo'lmaydi.
            models.CheckConstraint(
                condition=Q(sold_quantity__lte=F('quantity')), name='partner_line_sold_fits'),
        ]

    @property
    def unsold_quantity(self):
        return self.quantity - self.sold_quantity


class PartnerSettlement(models.Model):
    """Hamkordan tushgan pul. Har to'lov BITTA jo'natmani yopishga ketadi.

    Ofitsiant to'lovidan farqi: u yerda pul restorandan CHIQADI va tushum
    emas edi. Bu yerda pul KIRADI va haqiqiy tushum — shuning uchun kun
    yakunidagi kassa hisobiga ham kiradi.

    `delivery` majburiy: egasi «pul berishsa yopiladi» dedi, demak hech
    narsani yopmaydigan bo'sh pul bo'lishi mumkin emas.

    Bekor qilish o'chirish orqali emas, `voided_at` bilan: pul kelgani
    tarixda qolishi kerak. Barcha yig'indilar bekor qilinmaganini oladi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    partner = models.ForeignKey(Partner, on_delete=models.PROTECT, related_name='settlements')
    delivery = models.ForeignKey(PartnerDelivery, on_delete=models.PROTECT, related_name='settlements')
    actor = models.ForeignKey(User, on_delete=models.PROTECT, related_name='partner_settlements')
    key = models.UUIDField()
    request_hash = models.CharField(max_length=64, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PARTNER_PAYMENT_METHODS)
    paid_on = models.DateField()
    note = models.CharField(max_length=250, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    void_reason = models.CharField(max_length=200, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        User, on_delete=models.PROTECT, null=True, blank=True, related_name='voided_settlements')

    class Meta:
        ordering = ['-paid_on', '-id']
        constraints = [
            models.UniqueConstraint(fields=['branch', 'key'], name='partner_settlement_idempotency'),
            models.CheckConstraint(condition=Q(amount__gt=0), name='partner_settlement_positive_amount'),
            models.CheckConstraint(
                condition=Q(voided_at__isnull=True) | ~Q(void_reason=''),
                name='partner_settlement_void_needs_reason'),
        ]
        indexes = [models.Index(fields=['branch', 'paid_on'], name='partner_settlement_paid_idx')]

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
            # Farq har doim «sanalgan − kutilgan»ga teng. Uni dastur hisoblaydi,
            # lekin uchta raqam bir-biriga bog'liq bo'lgani uchun bog'liqlik
            # bazada ham turishi kerak: aks holda kelajakdagi xato tuzatib
            # bo'lmaydigan nomutanosib yozuv qoldirardi.
            models.CheckConstraint(
                condition=Q(difference=F('counted_cash') - F('expected_cash')),
                name='shift_difference_matches',
            ),
        ]


class PrintJob(models.Model):
    """Chop etishga navbat turgan talon.

    Nega navbat: tizim bulutdagi serverda ishlaydi, printer esa restoran
    ichida USB'da turadi — serverdan unga to'g'ridan-to'g'ri yo'l yo'q.
    Shuning uchun server ESC/POS baytlarini shu yerga qo'yadi, restorandagi
    agent esa ularni olib o'z printeriga yuboradi.

    Shundan kelib chiqadigan foyda: internet uzilsa ham kassa to'xtamaydi.
    Talon navbatda turadi va aloqa tiklangach chiqadi. Kassir esa printer
    javobini kutib o'tirmaydi — server javobni darhol qaytaradi.
    """

    STATUSES = [
        ('queued', 'Navbatda'),
        ('printing', 'Agent oldi'),
        ('done', 'Chiqdi'),
        ('failed', 'Chiqmadi'),
    ]

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='print_jobs')
    # Qaysi printerga: oshxona yoki kassa. Agent o'z sozlamasida bu nomni
    # haqiqiy qurilmaga bog'laydi.
    station = models.CharField(max_length=10)
    kind = models.CharField(max_length=12)
    # Tayyor ESC/POS baytlari. Serverda hosil qilinadi: talonning ko'rinishi
    # bitta joyda qolsin, agent esa faqat yetkazib beruvchi bo'lsin.
    payload = models.BinaryField()
    order = models.ForeignKey(Order, on_delete=models.CASCADE, null=True, blank=True, related_name='print_jobs')
    status = models.CharField(max_length=10, default='queued', choices=STATUSES)
    attempts = models.PositiveIntegerField(default=0)
    error = models.CharField(max_length=300, blank=True)
    # Kim olgani va qachon: ijara muddati o'tsa topshiriq navbatga qaytadi.
    agent = models.CharField(max_length=60, blank=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['id']
        indexes = [
            # Agent har soniyada shu kesimni so'raydi.
            models.Index(fields=['branch', 'status', 'station'], name='print_queue_idx'),
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
    # Ishlatilmay qolgan mahsulot ro'yxatdan yo'qoladi, lekin tarixi qoladi.
    # Butunlay o'chirish faqat hech qachon ishlatilmagan yozuvga ruxsat
    # etiladi — aks holda o'tgan oyning ombor hisoboti nomsiz qatorlarga
    # to'lib ketardi.
    archived = models.BooleanField(default=False)

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
    # «refund» — qaytarilgan buyurtma masallig'i omborga qaytgani. U kirim
    # EMAS: xarid bo'lmagan, shuning uchun xarajat hisobiga ham tushmaydi.
    kind = models.CharField(max_length=18, choices=[('receipt', 'Kirim'), ('consumption', 'Kunlik sarf'), ('sale_consumption', 'Sotuv bo‘yicha sarf'), ('refund', 'Qaytarish'), ('partner_sale', 'Hamkorga jo‘natildi'), ('staff_meal', 'Hodimlar ovqati')])
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
    """Tayyor porsiyalar hisobi: kirim va chiqim yozuvlari.

    Bir kunda bir taomga bir nechta yozuv bo'ladi — ertalab 20 ta, tushda
    yana 15 ta. Ular qo'shiladi, ustiga yozilmaydi: shunda kun davomida
    nima qo'shilgani ham ko'rinib turadi.

    Miqdor MANFIY ham bo'lishi mumkin. Qoldiq kundan kunga o'tadigan
    bo'lgach, uni kamaytiradigan yo'l kerak bo'ldi: dushanbadagi manti
    jumagacha «bor» bo'lib turavermasligi uchun egasi qolganini hisobdan
    chiqaradi. Chiqim ham shu jadvalga yoziladi — tarix bitta joyda
    qolsin.

    Diqqat: bu yozuv ombordan masalliq AYIRMAYDI. Masalliq sotuv paytida
    retsept bo'yicha ayriladi va shundayligicha qoladi — aks holda bitta
    porsiya ikki marta hisobdan chiqardi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    dish = models.ForeignKey('catalog.Dish', on_delete=models.PROTECT, related_name='preps')
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    date = models.DateField()
    quantity = models.IntegerField()
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        # Nol yozuvning ma'nosi yo'q: u na qo'shadi, na ayiradi, faqat
        # tarixni chalg'itadi.
        constraints = [models.CheckConstraint(condition=~Q(quantity=0), name='dish_prep_not_zero')]
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
