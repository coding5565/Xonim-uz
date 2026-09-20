from django.db import migrations, models


def rename_duplicates(apps, schema_editor):
    """Mavjud bazadagi bir xil nomli taomlarni ajratadi.

    Cheklov qo'yilishidan oldin nomlar yagona bo'lishi shart. Eski yozuv
    tegilmaydi, keyingilariga « (2)», « (3)» qo'shiladi — shunda menyudagi
    tarix ham, chekdagi nom ham yo'qolmaydi.
    """
    Dish = apps.get_model('catalog', 'Dish')
    seen = set()
    for dish in Dish.objects.order_by('branch_id', 'id').iterator():
        marker = (dish.branch_id, dish.name.casefold())
        if marker not in seen:
            seen.add(marker)
            continue
        suffix = 2
        while (dish.branch_id, f'{dish.name} ({suffix})'.casefold()) in seen:
            suffix += 1
        dish.name = f'{dish.name} ({suffix})'[:120]
        seen.add((dish.branch_id, dish.name.casefold()))
        dish.save(update_fields=['name'])


class Migration(migrations.Migration):

    dependencies = [('catalog', '0003_category_station_dish_station')]

    operations = [
        migrations.RunPython(rename_duplicates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='dish',
            constraint=models.UniqueConstraint(fields=('branch', 'name'), name='dish_branch_name'),
        ),
    ]
