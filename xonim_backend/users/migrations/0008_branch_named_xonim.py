"""Filial nomi to'g'irlanadi: restoran «XONIM», «HONIM» emas.

Nom va slug bazada saqlanadi, shuning uchun kodni tuzatishning o'zi
yetmaydi: mavjud qator ham yangilanishi kerak. Slug — ochiq menyu
manzilining bir qismi (`/api/v1/public/menu/<slug>/`), demak u
o'zgarganda mijoz menyusi havolasi ham yangilanadi.
"""
from django.db import migrations


def branch_becomes_xonim(apps, schema_editor):
    Branch = apps.get_model('users', 'Branch')
    Branch.objects.filter(slug='honim').update(slug='xonim', name='Xonim Restaurant')


def branch_becomes_honim(apps, schema_editor):
    Branch = apps.get_model('users', 'Branch')
    Branch.objects.filter(slug='xonim').update(slug='honim', name='Honim Restaurant')


class Migration(migrations.Migration):

    dependencies = [('users', '0007_daily_wage')]

    operations = [migrations.RunPython(branch_becomes_xonim, branch_becomes_honim)]
