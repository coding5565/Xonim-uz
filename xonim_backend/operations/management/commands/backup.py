"""Zaxira nusxa olib, Telegramga yuboradi. Cron shu buyruqni chaqiradi.

Sahifadagi «nusxa olish» tugmasi ham aynan shu mantiqni ishlatadi
(`operations/backups.py`), shuning uchun jadval bo'yicha va qo'lda
olingan nusxa bir xil bo'ladi.
"""
from django.core.management.base import BaseCommand, CommandError

from operations.backups import BackupError, run_backup


class Command(BaseCommand):
    help = 'Back up the database and uploaded images, then send them to Telegram.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--source', default='cron', choices=['cron', 'manual'],
            help='Xabar matnida ko‘rinadi: jadval bo‘yicha yoki qo‘lda',
        )

    def handle(self, *args, **options):
        try:
            result = run_backup(source=options['source'])
        except BackupError as failure:
            raise CommandError(str(failure)) from None

        for item in result['files']:
            self.stdout.write(f'  {item["name"]}  {item["size"]}')
        if result['sent_to_telegram']:
            self.stdout.write(self.style.SUCCESS('Telegramga yuborildi.'))
        elif result['note']:
            self.stdout.write(self.style.WARNING(result['note']))
        else:
            self.stdout.write(self.style.WARNING('Telegramga to‘liq yuborilmadi.'))
        if result['removed_old']:
            self.stdout.write(f'Eski nusxalar o‘chirildi: {result["removed_old"]} ta')
