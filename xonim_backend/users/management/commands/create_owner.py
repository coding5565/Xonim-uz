"""Serverdagi birinchi filial va superadminni yaratadi.

`seed_demo` ataylab faqat mahalliy ishlaydi: u namuna menyu va taxminiy
narxlar yozadi, bunday ma'lumot haqiqiy bazaga tushmasligi kerak. Lekin
bo'sh bazaga birinchi marta kirishning ham yo'li bo'lishi shart — aks
holda tizim ko'tariladi-yu, unga hech kim kira olmaydi.

Buyruq takroran ishlatilsa hech narsa buzilmaydi: mavjud filial va xodim
qayta yaratilmaydi, parol esa faqat so'ralganda almashtiriladi.
"""
import secrets

from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from users.models import Branch, User


class Command(BaseCommand):
    help = 'Create the first branch and its owner account (safe to re-run).'

    def add_arguments(self, parser):
        parser.add_argument('--branch', default='Xonim Restaurant', help='Filial nomi')
        parser.add_argument('--slug', default='', help='Mijoz menyusi manzili uchun; bo‘sh bo‘lsa nomdan olinadi')
        parser.add_argument('--username', default='owner', help='Superadmin logini')
        parser.add_argument('--password', default='', help='Bo‘sh bo‘lsa kuchli parol o‘ylab topiladi')
        parser.add_argument('--name', default='Restoran egasi', help='Ekranda ko‘rinadigan ism')
        parser.add_argument(
            '--reset-password', action='store_true',
            help='Xodim allaqachon bor bo‘lsa ham parolni almashtirish',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        slug = options['slug'] or slugify(options['branch']) or 'xonim'
        branch, fresh_branch = Branch.objects.get_or_create(
            slug=slug, defaults={'name': options['branch']},
        )

        password = options['password'] or secrets.token_urlsafe(12)
        if options['password']:
            try:
                password_validation.validate_password(password)
            except ValidationError as failure:
                raise CommandError('; '.join(failure.messages)) from None

        person = User.objects.filter(username=options['username']).first()
        if person:
            if person.branch_id and person.branch_id != branch.id:
                raise CommandError(
                    f'«{person.username}» boshqa filialga biriktirilgan. Boshqa login tanlang.')
            if not options['reset_password']:
                self.stdout.write(self.style.WARNING(
                    f'«{person.username}» allaqachon bor — parol tegilmadi. '
                    f'Almashtirish uchun --reset-password bering.'))
                return
            person.set_password(password)
            person.branch = branch
            person.role = User.Role.OWNER
            person.is_active = True
            person.save(update_fields=['password', 'branch', 'role', 'is_active'])
            action = 'parol almashtirildi'
        else:
            User.objects.create_user(
                username=options['username'], password=password,
                first_name=options['name'], role=User.Role.OWNER, branch=branch,
            )
            action = 'yaratildi'

        self.stdout.write(self.style.SUCCESS(
            f'Filial: {branch.name} ({branch.slug}){" — yangi" if fresh_branch else ""}'))
        self.stdout.write(self.style.SUCCESS(f'Superadmin: {options["username"]} — {action}'))
        if not options['password']:
            # Parol FAQAT shu yerda bir marta ko'rsatiladi: u hech qayerga
            # yozilmaydi, bazada esa faqat xesh saqlanadi.
            self.stdout.write(self.style.WARNING(f'Parol: {password}'))
            self.stdout.write('Bu parol boshqa hech qayerda saqlanmaydi — hoziroq ko‘chirib oling.')
