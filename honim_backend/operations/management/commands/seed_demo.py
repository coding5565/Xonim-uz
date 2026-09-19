import secrets
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from catalog.models import Category, Dish
from operations.models import Ingredient
from users.models import Branch, User


class Command(BaseCommand):
    help = 'Create local sample menu and one owner. Never resets existing data.'

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo initialization is local-only.')
        branch, _ = Branch.objects.get_or_create(slug='honim', defaults={'name': 'Honim Restaurant'})
        if not User.objects.filter(username='owner').exists():
            password = secrets.token_urlsafe(15)
            User.objects.create_user(username='owner', password=password, first_name='Restoran egasi', role='owner', branch=branch)
            Path(settings.BASE_DIR.parent / '.local-access.txt').write_text(f'Local development only\nLogin: owner\nParol: {password}\nURL: http://127.0.0.1:5173\n', encoding='utf-8')
        data = [
            ('Milliy taomlar', [('To‘y oshi', 'Lazer guruch, mol go‘shti, sariq sabzi va no‘xat.', '45000', '350 g'), ('Manti', 'Qo‘lda tugilgan, mol go‘shti va piyozli.', '32000', '5 dona'), ('Qozon kabob', 'Yumshoq mol go‘shti va qizartirilgan kartoshka.', '68000', '400 g'), ('Chuchvara', 'Uy usulida tayyorlangan chuchvara, qaymoq bilan.', '35000', '300 g')]),
            ('Salatlar', [('Achchiq-chuchuk', 'Pomidor, piyoz va yangi rayhon.', '18000', '200 g'), ('Bahor salati', 'Yangi bodring, ko‘katlar va qaymoq.', '22000', '200 g')]),
            ('Ichimliklar', [('Ko‘k choy', 'Xushbo‘y, yangi damlangan ko‘k choy.', '8000', '0.7 l'), ('Limonad', 'Limon, yalpiz va muz bilan.', '24000', '0.4 l')]),
            ('Non va shirinlik', [('Issiq non', 'Tandirdan yangi uzilgan non.', '6000', '1 dona'), ('Asalli tort', 'Asal qatlamlari va yengil qaymoq.', '28000', '120 g')]),
        ]
        for index, (name, dishes) in enumerate(data):
            category, _ = Category.objects.get_or_create(branch=branch, name=name, defaults={'position': index})
            for title, description, price, portion in dishes:
                Dish.objects.get_or_create(branch=branch, category=category, name=title, defaults={'description': description, 'price': price, 'portion': portion})
        for name, unit, minimum in [('Guruch', 'kg', 10), ('Mol go‘shti', 'kg', 5), ('Sabzi', 'kg', 5), ('O‘simlik yog‘i', 'l', 3)]:
            Ingredient.objects.get_or_create(branch=branch, name=name, defaults={'unit': unit, 'minimum': minimum})
        self.stdout.write(self.style.SUCCESS('Namuna menyu tayyor. Kirish: .local-access.txt. Savdo va ombor boshlang‘ich summalari 0.'))
