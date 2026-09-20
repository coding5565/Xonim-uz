"""WSGI kirish nuqtasi — gunicorn shu obyektni yuklaydi.

`runserver` faqat ishlab chiqish uchun: u bitta oqimda ishlaydi, statik
fayllarni o'zi beradi va xatolarni brauzerga chiqaradi. Serverda esa
gunicorn turadi va bu fayl unga ilovani ko'rsatadi.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = get_wsgi_application()
