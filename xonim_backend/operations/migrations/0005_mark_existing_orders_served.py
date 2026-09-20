from django.db import migrations


def mark_existing_orders_served(apps, schema_editor):
    Order = apps.get_model('operations', 'Order')
    Order.objects.filter(preparation_status='queued').update(preparation_status='served')


class Migration(migrations.Migration):
    dependencies = [('operations', '0004_order_preparation_status_order_ready_at_and_more')]
    operations = [migrations.RunPython(mark_existing_orders_served, migrations.RunPython.noop)]
