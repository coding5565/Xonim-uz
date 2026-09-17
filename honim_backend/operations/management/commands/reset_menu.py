from django.core.management.base import BaseCommand
from django.db import transaction

from catalog.models import Category, Dish
from operations.models import Order, OrderLine
from users.models import Branch


MENU = [
    ('Mantilar', [('O‘rama manti', 13000, '1 dona'), ('Bozor manti', 7500, '1 dona'), ('Qovoq manti', 7000, '1 dona'), ('Ko‘k manti', 7000, '1 dona'), ('Oddiy manti', 10000, '1 dona')]),
    ('Milliy taomlar', [('Tuxum barak', 40000, '1 porsiya'), ('Uyg‘ur', 11000, '1 porsiya'), ('Qurtoba', 65000, '1 porsiya'), ('Mastava', 35000, '1 porsiya'), ('Chuchvara', 35000, '1 porsiya'), ('Ugra', 35000, '1 porsiya')]),
    ('Non va xamir', [('Non', 6000, '1 dona'), ('Qatlama', 12000, '1 dona')]),
    ('Salatlar', [('Sveji salat', 20000, '1 porsiya'), ('Shakarob', 15000, '1 porsiya')]),
    ('Qo‘shimchalar', [('Sous', 3000, '1 dona')]),
]


class Command(BaseCommand):
    help = 'Menyuni ko‘rsatilgan mahsulotlar bilan yangilaydi va avvalgi namunaviy buyurtmalarni tozalaydi.'

    @transaction.atomic
    def handle(self, *args, **options):
        for branch in Branch.objects.all():
            # Old dishes are protected by their order lines; reset only order data
            # that belongs to the previous demo menu, keeping staff and finance data.
            OrderLine.objects.filter(order__branch=branch).delete()
            Order.objects.filter(branch=branch).delete()
            Dish.objects.filter(branch=branch).delete()
            Category.objects.filter(branch=branch).delete()
            for position, (category_name, dishes) in enumerate(MENU, 1):
                category = Category.objects.create(branch=branch, name=category_name, position=position)
                for name, price, portion in dishes:
                    Dish.objects.create(branch=branch, category=category, name=name, price=price, portion=portion, available=True)
            self.stdout.write(self.style.SUCCESS(f'{branch.name}: {sum(len(dishes) for _, dishes in MENU)} ta taom qo‘shildi.'))
