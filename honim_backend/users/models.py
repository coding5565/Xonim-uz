from django.contrib.auth.models import AbstractUser
from django.db import models


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
    salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    hired_at = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=300, blank=True)


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
    'prep.oversell': 'Tayyorlangandan ko‘p sotildi',
    'stock.price': 'Masalliq narxi o‘zgardi',
    'usage.create': 'Kunlik sarf kiritildi',
    'usage.update': 'Kunlik sarf o‘zgartirildi',
    'usage.remove': 'Kunlik sarf o‘chirildi',
    'stock.receipt': 'Omborga kirim',
    'stock.consumption': 'Ombordan chiqim',
    'stock.sale_consumption': 'Savdo bo‘yicha sarf',
    'expense.create': 'Xarajat kiritildi',
    'salary.pay': 'Oylik to‘landi',
    'staff.create': 'Xodim qo‘shildi',
    'staff.update': 'Xodim ma’lumoti o‘zgardi',
    'catalog.create': 'Menyuga qo‘shildi',
    'catalog.update': 'Menyu o‘zgartirildi',
    'recipe.create': 'Retsept yaratildi',
    'recipe.update': 'Retsept yangilandi',
    'table.create': 'Stol qo‘shildi',
    'waiter.create': 'Ofitsiant qo‘shildi',
    'waiter.update': 'Ofitsiant ma’lumoti o‘zgardi',
    'waiter.remove': 'Ofitsiant olib tashlandi',
    'table.update': 'Stol o‘zgartirildi',
    'table.remove': 'Stol olib tashlandi',
    'auth.login': 'Tizimga kirdi',
    'auth.logout': 'Tizimdan chiqdi',
}

# Jurnalda guruhlash uchun: har harakat qaysi bo'limga tegishli.
AUDIT_GROUPS = {
    'order': 'Savdo',
    'shift': 'Kun yakuni',
    'print': 'Chop etish',
    'kitchen': 'Oshxona',
    'stock': 'Ombor',
    'prep': 'Tayyor taomlar',
    'usage': 'Kunlik sarf',
    'expense': 'Xarajat',
    'salary': 'Oylik',
    'staff': 'Xodimlar',
    'catalog': 'Menyu',
    'recipe': 'Retsept',
    'table': 'Stollar',
    'waiter': 'Ofitsiantlar',
    'auth': 'Kirish-chiqish',
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
