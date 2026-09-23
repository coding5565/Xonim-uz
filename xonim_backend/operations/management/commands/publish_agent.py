"""Chop etish agentining yangi versiyasini chiqaradi.

Yig'ilgan .exe serverga ko'chiriladi, so'ng shu buyruq chaqiriladi.
Shundan keyin restorandagi agentlar soat ichida o'zlarini yangilaydi —
hech kimning borib o'rnatishi shart emas.

    python manage.py publish_agent /tmp/xonim-agent.exe --version 1.1
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from operations.agent_release import publish


class Command(BaseCommand):
    help = 'Publish a new print-agent build so installed agents can update themselves.'

    def add_arguments(self, parser):
        parser.add_argument('path', help='Yig‘ilgan .exe fayl')
        parser.add_argument('--version', required=True, help='Masalan: 1.1')
        parser.add_argument('--notes', default='', help='Nima o‘zgardi')

    def handle(self, *args, **options):
        source = Path(options['path'])
        if not source.exists():
            raise CommandError(f'Fayl topilmadi: {source}')
        if source.suffix.lower() != '.exe':
            raise CommandError('Faqat .exe chiqariladi.')

        manifest = publish(source, options['version'], options['notes'])
        self.stdout.write(self.style.SUCCESS(f'Versiya {manifest["version"]} chiqarildi'))
        self.stdout.write(f'  fayl:   {manifest["file"]}')
        self.stdout.write(f'  hajmi:  {manifest["size"] / 1024 / 1024:.1f} MB')
        self.stdout.write(f'  sha256: {manifest["sha256"][:16]}…')
        self.stdout.write('Agentlar bir soat ichida o‘zlarini yangilaydi.')
