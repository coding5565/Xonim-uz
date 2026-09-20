"""Davomat jadvali va ochiq balansli ish haqi to'lovi.

Ilgari bir xodimga bir oyda bitta to'lov yozilardi. Endi haq har kuni
davomatdan yig'iladi, pul esa istalgan kuni, istalgan summada beriladi —
shuning uchun «bir oyga bitta to'lov» cheklovi olib tashlanadi va uning
o'rniga takroriy yuborishdan himoya qiladigan amal kaliti qo'yiladi.
"""
import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('operations', '0023_order_channel_commission_channelfee'),
        ('users', '0006_admins_become_cashiers'),
    ]

    operations = [
        migrations.CreateModel(
            name='Attendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('present', models.BooleanField(default=True)),
                ('daily_wage', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('note', models.CharField(blank=True, max_length=200)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('actor', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='marked_attendances', to=settings.AUTH_USER_MODEL)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='users.branch')),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='attendances', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-date', 'employee_id'],
            },
        ),
        migrations.RemoveConstraint(
            model_name='salarypayment',
            name='salary_one_payment_per_period',
        ),
        migrations.AlterModelOptions(
            name='salarypayment',
            options={'ordering': ['-paid_on', '-id']},
        ),
        migrations.AddField(
            model_name='salarypayment',
            name='key',
            field=models.UUIDField(default=uuid.uuid4),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='salarypayment',
            name='request_hash',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddConstraint(
            model_name='salarypayment',
            constraint=models.UniqueConstraint(fields=('branch', 'key'), name='salary_payment_idempotency'),
        ),
        migrations.AddIndex(
            model_name='attendance',
            index=models.Index(fields=['branch', 'date'], name='attendance_branch_date_idx'),
        ),
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.UniqueConstraint(fields=('branch', 'employee', 'date'), name='attendance_one_row_per_day'),
        ),
        migrations.AddConstraint(
            model_name='attendance',
            constraint=models.CheckConstraint(condition=models.Q(('daily_wage__gte', 0)), name='attendance_wage_not_negative'),
        ),
    ]
