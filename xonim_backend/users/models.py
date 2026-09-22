from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q


class Branch(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Superadmin'
        CASHIER = 'cashier', 'Kassir'
        KITCHEN = 'kitchen', 'Oshxona'
        # «Admin» roli olib tashlandi: kundalik ishlari kassirga, nazorati
        # superadminga o'tdi. Eski hisoblar migratsiya bilan kassirga
        # o'tkaziladi — o'chirilmaydi, chunki jurnal ularga bog'langan.

    role = models.CharField(max_length=12, choices=Role.choices, default=Role.CASHIER)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, null=True)
    phone = models.CharField(max_length=30, blank=True)


class Employee(models.Model):
    """Restoranda ishlaydigan odam. Tizimga kirishi SHART EMAS.

    Oshpaz, farrosh, yordamchi — ularning ko'pchiligi hech qachon tizimga
    kirmaydi, lekin ularga ham haq yoziladi va pul beriladi. Ilgari xodim
    faqat login bilan birga yaratilardi: har bir farroshga parol o'ylab
    topishga to'g'ri kelardi va ishlatilmagan hisoblar tizimda qolib
    ketardi.

    Lavozim erkin matn: restoran o'z odamlarini o'zi ataydi va ro'yxatga
    sig'maydigan lavozim doim topiladi.

    Tizimga kiradiganlar uchun `account` orqali login biriktiriladi —
    kassir ham xodim, ham foydalanuvchi bo'ladi, lekin bu ikki narsa
    alohida qolаdi.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name='employees')
    name = models.CharField(max_length=120)
    # Erkin matn: «Oshpaz», «Farrosh», «Ofitsiant» — ro'yxat emas.
    position = models.CharField(max_length=60, blank=True)
    # Kunlik haq. Oylik emas: hafta olti kun ishlanadi va haq har kuni
    # davomatga qarab yig'iladi, shuning uchun kelishuvning birligi ham kun.
    daily_wage = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    phone = models.CharField(max_length=30, blank=True)
    hired_at = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=300, blank=True)
    active = models.BooleanField(default=True)
    # Tizimga kiradigan xodimning hisobi. Bo'sh bo'lsa — u faqat ishlaydi.
    account = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='employee')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-active', 'name']
        constraints = [
            # Bir filialda bir xil ism ikki marta bo'lsa, davomatda kimni
            # belgilaganini ajratib bo'lmaydi.
            models.UniqueConstraint(fields=['branch', 'name'], name='employee_branch_name'),
            models.CheckConstraint(condition=Q(daily_wage__gte=0), name='employee_wage_not_negative'),
        ]


# Harakat turlarining o'zbekcha nomlari. Ro'yxatda yo'q kalit xom holida
# ko'rsatiladi, shuning uchun yangi harakat qo'shilsa ham jurnal buzilmaydi.
AUDIT_LABELS = {
    'order.create': 'Buyurtma ochildi',
    'order.append': 'Buyurtmaga qo‘shildi',
    'order.pay': 'To‘lov qabul qilindi',
    'order.line_remove': 'Hisobdan taom olib tashlandi',
    'order.cancel': 'Hisob bekor qilindi',
    'order.discount': 'Chegirma qo‘llandi',
    'order.refund': 'To‘lov qaytarildi',
    'shift.close': 'Kun yakunlandi',
    'order.print': 'Chek qayta chop etildi',
    'print.failed': 'Chop etishda muammo',
    'kitchen.preparing': 'Oshxona: tayyorlanmoqda',
    'kitchen.ready': 'Oshxona: tayyor',
    'kitchen.served': 'Oshxona: berildi',
    'stock.ingredient': 'Yangi masalliq qo‘shildi',
    'prep.record': 'Taom tayyorlandi',
    'prep.writeoff': 'Tayyor taom hisobdan chiqarildi',
    'prep.oversell': 'Tayyorlangandan ko‘p sotildi',
    'stock.price': 'Masalliq narxi o‘zgardi',
    'usage.create': 'Kunlik sarf kiritildi',
    'usage.update': 'Kunlik sarf o‘zgartirildi',
    'usage.remove': 'Kunlik sarf o‘chirildi',
    'stock.receipt': 'Omborga kirim',
    'stock.consumption': 'Ombordan chiqim',
    'stock.sale_consumption': 'Savdo bo‘yicha sarf',
    'stock.refund': 'Qaytarilgan masalliq',
    'stock.shortage': 'Qoldiqdan ko‘p sarflandi',
    'prep.remove': 'Tayyorlangan yozuv o‘chirildi',
    'expense.create': 'Xarajat kiritildi',
    'expense.update': 'Xarajat tuzatildi',
    'expense.remove': 'Xarajat o‘chirildi',
    'salary.pay': 'Ish haqi berildi',
    'attendance.mark': 'Davomat belgilandi',
    'staff.create': 'Xodim qo‘shildi',
    'staff.update': 'Xodim ma’lumoti o‘zgardi',
    'catalog.create': 'Menyuga qo‘shildi',
    'catalog.update': 'Menyu o‘zgartirildi',
    'recipe.create': 'Retsept yaratildi',
    'recipe.update': 'Retsept yangilandi',
    'table.create': 'Stol qo‘shildi',
    'channel.fee': 'Platforma ulushi o‘zgardi',
    'waiter.create': 'Ofitsiant qo‘shildi',
    'waiter.update': 'Ofitsiant ma’lumoti o‘zgardi',
    'waiter.pay': 'Ofitsiantga ulush berildi',
    'partner.create': 'Hamkor qo‘shildi',
    'partner.update': 'Hamkor ma’lumoti o‘zgardi',
    'partner.price': 'Hamkor narxlari yangilandi',
    'partner.send': 'Hamkorga jo‘natildi',
    'partner.report': 'Hamkor hisoboti kiritildi',
    'partner.settle': 'Hamkordan pul olindi',
    'partner.cancel': 'Hamkor jo‘natmasi bekor qilindi',
    'partner.void': 'Hamkor to‘lovi bekor qilindi',
    'waiter.remove': 'Ofitsiant olib tashlandi',
    'table.update': 'Stol o‘zgartirildi',
    'table.remove': 'Stol olib tashlandi',
    'auth.login': 'Tizimga kirdi',
    'auth.logout': 'Tizimdan chiqdi',
    'auth.failed': 'Parol noto‘g‘ri kiritildi',
    'auth.password': 'Parol almashtirildi',
    'backup.create': 'Zaxira nusxa olindi',
    'backup.failed': 'Zaxira nusxa olinmadi',
}

# Jurnalda guruhlash uchun: har harakat qaysi bo'limga tegishli.
AUDIT_GROUPS = {
    'order': 'Savdo',
    'shift': 'Kun yakuni',
    'print': 'Chop etish',
    'kitchen': 'Oshxona',
    'stock': 'Ombor',
    'channel': 'Platformalar',
    'prep': 'Tayyor taomlar',
    'usage': 'Kunlik sarf',
    'expense': 'Xarajat',
    'salary': 'Ish haqi',
    'attendance': 'Davomat',
    'staff': 'Xodimlar',
    'catalog': 'Menyu',
    'recipe': 'Retsept',
    'table': 'Stollar',
    'waiter': 'Ofitsiantlar',
    'partner': 'Hamkorlar',
    'auth': 'Kirish-chiqish',
    'backup': 'Zaxira nusxa',
}


def audit_label(action):
    return AUDIT_LABELS.get(action, action)


def audit_group(action):
    return AUDIT_GROUPS.get(action.split('.')[0], 'Boshqa')


class AuditEvent(models.Model):
    """Har bir harakat abadiy saqlanadi — hech qachon o‘chirilmaydi.

    Indekslar sana va harakat turi bo‘yicha filtrga mo‘ljallangan: jurnal
    o‘n minglab qatorga yetganda ham sahifalash tez ishlashi kerak.
    """

    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    description = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
        indexes = [
            models.Index(fields=['branch', '-created_at', '-id'], name='audit_branch_recent_idx'),
            models.Index(fields=['branch', 'action', '-created_at'], name='audit_branch_action_idx'),
        ]
