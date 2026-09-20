"""Kelishuv birligi oydan kunga o'tadi.

Hafta olti kun ishlanadi va haq har kuni davomatga qarab yig'iladi, shuning
uchun xodim kartasida turadigan raqam ham kunlik bo'lishi kerak. Eski oylik
summalar yo'qotilmaydi: ular oyiga 26 ish kuni hisobidan kunlikka
o'tkaziladi. Bu taxminiy raqam — superadmin har bir xodimning haqiqiy
kunlik summasini kiritib chiqishi kerak.
"""
from decimal import Decimal

from django.db import migrations, models

WORK_DAYS_PER_MONTH = Decimal('26')


def monthly_becomes_daily(apps, schema_editor):
    User = apps.get_model('users', 'User')
    for person in User.objects.exclude(salary=0):
        person.daily_wage = (person.salary / WORK_DAYS_PER_MONTH).quantize(Decimal('0.01'))
        person.save(update_fields=['daily_wage'])


def daily_becomes_monthly(apps, schema_editor):
    User = apps.get_model('users', 'User')
    for person in User.objects.exclude(daily_wage=0):
        person.salary = (person.daily_wage * WORK_DAYS_PER_MONTH).quantize(Decimal('0.01'))
        person.save(update_fields=['salary'])


class Migration(migrations.Migration):

    dependencies = [('users', '0006_admins_become_cashiers')]

    operations = [
        migrations.AddField(
            model_name='user',
            name='daily_wage',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.RunPython(monthly_becomes_daily, daily_becomes_monthly),
        migrations.RemoveField(model_name='user', name='salary'),
    ]
