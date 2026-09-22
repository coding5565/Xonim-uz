"""Davomat va ish haqi endi xodimga bog'lanadi, foydalanuvchiga emas.

Tizimga kirmaydigan xodim ham davomatga tushadi va pul oladi, shuning uchun
bu yozuvlar login bilan bog'lanib qololmaydi.

Hech bir qator yo'qolmaydi: avval yangi ustun qo'shiladi, mavjud qatorlar
foydalanuvchining xodim yozuviga ko'chiriladi, keyin eski ustun olib
tashlanadi. Ko'chirish `users.0009` yaratgan bog'lanishga tayanadi — har bir
foydalanuvchining o'z xodim yozuvi bor.
"""
import django.db.models.deletion
from django.db import migrations, models


def point_at_employees(apps, schema_editor):
    Employee = apps.get_model('users', 'Employee')
    by_account = {row.account_id: row.id for row in Employee.objects.filter(account__isnull=False)}
    for name in ('Attendance', 'SalaryPayment'):
        model = apps.get_model('operations', name)
        for row in model.objects.all().only('id', 'employee_id'):
            model.objects.filter(pk=row.pk).update(employee_ref_id=by_account.get(row.employee_id))


def point_back_at_users(apps, schema_editor):
    Employee = apps.get_model('users', 'Employee')
    accounts = {row.id: row.account_id for row in Employee.objects.all()}
    for name in ('Attendance', 'SalaryPayment'):
        model = apps.get_model('operations', name)
        for row in model.objects.all().only('id', 'employee_ref_id'):
            account = accounts.get(row.employee_ref_id)
            if account is None:
                raise RuntimeError(
                    'Logini yo‘q xodimning yozuvi bor — orqaga qaytarib bo‘lmaydi.')
            model.objects.filter(pk=row.pk).update(employee_id=account)


class Migration(migrations.Migration):

    dependencies = [
        ('operations', '0030_zero_the_carried_balances'),
        ('users', '0009_employee'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendance',
            name='employee_ref',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='attendances', to='users.employee'),
        ),
        migrations.AddField(
            model_name='salarypayment',
            name='employee_ref',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, related_name='salary_payments', to='users.employee'),
        ),
        migrations.RunPython(point_at_employees, point_back_at_users),
        migrations.RemoveConstraint(model_name='attendance', name='attendance_one_row_per_day'),
        migrations.RemoveField(model_name='attendance', name='employee'),
        migrations.RemoveField(model_name='salarypayment', name='employee'),
        migrations.RenameField(model_name='attendance', old_name='employee_ref', new_name='employee'),
        migrations.RenameField(model_name='salarypayment', old_name='employee_ref', new_name='employee'),
        migrations.AlterField(
            model_name='attendance',
            name='employee',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='attendances', to='users.employee'),
        ),
        migrations.AlterField(
            model_name='salarypayment',
            name='employee',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='salary_payments', to='users.employee'),
        ),
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.UniqueConstraint(fields=('branch', 'employee', 'date'), name='attendance_one_row_per_day'),
        ),
    ]
