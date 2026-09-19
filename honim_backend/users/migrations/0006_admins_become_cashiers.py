"""Mavjud «admin» hisoblarini kassirga o'tkazadi.

Hisobni o'chirib bo'lmaydi: AuditEvent.actor va boshqa bog'lanishlar PROTECT,
ya'ni o'chirish tarixni buzardi. Shuning uchun rol almashtiriladi — kim nima
qilgani jurnalda o'z joyida qoladi.
"""
from django.db import migrations


def admins_to_cashiers(apps, schema_editor):
    User = apps.get_model('users', 'User')
    User.objects.filter(role='admin').update(role='cashier')


def cashiers_stay(apps, schema_editor):
    """Orqaga qaytarish: kimning admin bo'lganini bilib bo'lmaydi, shuning
    uchun hech narsa qilinmaydi — bu zararsiz."""


class Migration(migrations.Migration):

    dependencies = [('users', '0005_alter_user_role')]

    operations = [migrations.RunPython(admins_to_cashiers, cashiers_stay)]
