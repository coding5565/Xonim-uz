"""Uzluksiz qoldiqqa o'tishdan oldin eski qoldiqni nolga tushiradi.

Ilgari qoldiq har kuni noldan boshlanardi, shuning uchun o'tgan kunlarning
yozuvlari hech qachon bugunga qo'shilmasdi. Uzluksiz hisobga o'tilganda esa
ular birdan «bor» bo'lib qoladi: ikki kun oldin pishirilgan manti bugun
sotuvga tayyor ko'rinardi va oshxona qo'riqchisi mavjud bo'lmagan porsiyalar
uchun yo'l ochib berardi.

Shuning uchun kechagi kunga teskari yozuv qo'yiladi: har bir taomning
kechagi qoldig'i nolga tushadi. Bugungi yozuvlarga tegilmaydi — ular
haqiqiy va o'z kuchida qoladi. Egasi ertalab haqiqiy qoldiqni kiritadi.
"""
from datetime import datetime, time, timedelta

from django.db import migrations
from django.db.models import Min, Sum
from django.utils import timezone

CONSUMING_STATUSES = ['open', 'paid', 'refunded']
NOTE = 'Uzluksiz qoldiqqa o‘tish — eski qoldiq nolga tushirildi'


def zero_yesterday(apps, schema_editor):
    DishPrep = apps.get_model('operations', 'DishPrep')
    OrderLine = apps.get_model('operations', 'OrderLine')
    User = apps.get_model('users', 'User')

    yesterday = timezone.localdate() - timedelta(days=1)
    scope = DishPrep.objects.filter(date__lte=yesterday)
    rows = scope.values('branch_id', 'dish_id').annotate(
        intake=Sum('quantity'), first=Min('date'),
    ).order_by()
    for row in rows:
        since = timezone.make_aware(datetime.combine(row['first'], time.min))
        until = timezone.make_aware(datetime.combine(yesterday + timedelta(days=1), time.min))
        sold = OrderLine.objects.filter(
            order__branch_id=row['branch_id'],
            order__created_at__gte=since,
            order__created_at__lt=until,
            order__status__in=CONSUMING_STATUSES,
            dish_id=row['dish_id'],
        ).aggregate(total=Sum('quantity'))['total'] or 0
        balance = (row['intake'] or 0) - sold
        if not balance:
            continue
        actor = User.objects.filter(branch_id=row['branch_id']).order_by('id').first()
        if not actor:
            continue
        DishPrep.objects.create(
            branch_id=row['branch_id'], dish_id=row['dish_id'], actor=actor,
            date=yesterday, quantity=-balance, note=NOTE,
        )


def undo(apps, schema_editor):
    DishPrep = apps.get_model('operations', 'DishPrep')
    DishPrep.objects.filter(note=NOTE).delete()


class Migration(migrations.Migration):

    dependencies = [('operations', '0029_dish_prep_allows_write_off')]

    operations = [migrations.RunPython(zero_yesterday, undo)]
