"""Xodim endi alohida yozuv: tizimga kirishi shart emas.

Ilgari har bir xodim login bilan birga yaratilardi — oshpazga ham, farroshga
ham parol o'ylab topishga to'g'ri kelardi. Endi xodim o'z yozuviga ega bo'ladi,
login esa faqat kerak bo'lganda biriktiriladi.

Tartib muhim: avval yangi jadval yaratiladi, keyin mavjud hisoblardan xodim
yozuvlari ko'chiriladi va faqat shundan keyin foydalanuvchidagi ortiqcha
maydonlar olib tashlanadi. Aks holda kunlik haq va ishga kirgan sana
ko'chirilmasdan o'chib ketardi.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def users_become_employees(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Employee = apps.get_model('users', 'Employee')
    for person in User.objects.filter(branch__isnull=False).order_by('id'):
        # Superadmin ham xodim sifatida yoziladi: ish haqi bo'limi uni
        # ro'yxatdan chiqarib tashlaydi, lekin uning hisobi bog'lanmay
        # qolsa keyin davomat yozuvlari egasiz bo'lardi.
        name = person.first_name or person.username
        if Employee.objects.filter(branch_id=person.branch_id, name=name).exists():
            # Bir xil ism ikki hisobda bo'lsa, loginni qo'shib ajratamiz:
            # davomatda kimni belgilaganini aniq bilish kerak.
            name = f'{name} ({person.username})'
        Employee.objects.create(
            branch_id=person.branch_id,
            name=name,
            position=dict(person._meta.get_field('role').choices).get(person.role, person.role),
            daily_wage=person.daily_wage,
            phone=person.phone,
            hired_at=person.hired_at,
            notes=person.notes,
            active=person.is_active,
            account=person,
        )


def employees_become_users(apps, schema_editor):
    User = apps.get_model('users', 'User')
    Employee = apps.get_model('users', 'Employee')
    for employee in Employee.objects.filter(account__isnull=False).select_related('account'):
        User.objects.filter(pk=employee.account_id).update(
            daily_wage=employee.daily_wage, hired_at=employee.hired_at, notes=employee.notes,
        )
    Employee.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0008_branch_named_xonim'),
    ]

    operations = [
        migrations.CreateModel(
            name='Employee',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=120)),
                ('position', models.CharField(blank=True, max_length=60)),
                ('daily_wage', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('phone', models.CharField(blank=True, max_length=30)),
                ('hired_at', models.DateField(blank=True, null=True)),
                ('notes', models.CharField(blank=True, max_length=300)),
                ('active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('account', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='employee', to=settings.AUTH_USER_MODEL)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='employees', to='users.branch')),
            ],
            options={
                'ordering': ['-active', 'name'],
                'constraints': [models.UniqueConstraint(fields=('branch', 'name'), name='employee_branch_name'), models.CheckConstraint(condition=models.Q(('daily_wage__gte', 0)), name='employee_wage_not_negative')],
            },
        ),
        migrations.RunPython(users_become_employees, employees_become_users),
        migrations.RemoveField(model_name='user', name='daily_wage'),
        migrations.RemoveField(model_name='user', name='hired_at'),
        migrations.RemoveField(model_name='user', name='notes'),
    ]
