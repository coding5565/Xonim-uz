import os
import secrets
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Local secrets stay in .env (ignored by Git). Production uses real environment
# variables, which always take priority over this development-only file.
for env_line in (BASE_DIR / '.env').read_text(encoding='utf-8').splitlines() if (BASE_DIR / '.env').exists() else []:
    if '=' in env_line and not env_line.lstrip().startswith('#'):
        env_key, env_value = env_line.split('=', 1)
        os.environ.setdefault(env_key.strip(), env_value.strip())

DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError('DJANGO_SECRET_KEY is required in production')
    secret_path = BASE_DIR / '.local-secret'
    if not secret_path.exists():
        secret_path.write_text(secrets.token_urlsafe(64), encoding='utf-8')
    SECRET_KEY = secret_path.read_text(encoding='utf-8').strip()
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.staticfiles', 'rest_framework', 'users', 'catalog', 'operations']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.locale.LocaleMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'core.urls'
AUTH_USER_MODEL = 'users.User'
# Loyiha PostgreSQL'da ishlaydi — mahalliy sinovda ham, serverda ham.
#
# Nega bitta baza: SQLite bilan Postgres bir xil kodni boshqacha bajaradi.
# SQLite butun sonlarni bo'lganda kasr qismini tashlaydi (chegirma taqsimoti
# 122 999 va 123 000 bo'lib ikki xil chiqqan edi), CHECK cheklovlarini
# yumshoqroq tekshiradi va o'nlik sonlarni suzuvchi son sifatida saqlaydi.
# Ya'ni mahalliy sinov serverda takrorlanmasligi mumkin — eng yomon xato turi.
#
# SQLite faqat ataylab so'ralganda yoqiladi; jim qolib unga tushib qolish yo'q.
if os.environ.get('USE_SQLITE') == '1':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3', 'OPTIONS': {'timeout': 20}}}
else:
    POSTGRES_PASSWORD = os.environ.get('POSTGRES_PASSWORD')
    if not POSTGRES_PASSWORD:
        raise RuntimeError(
            'POSTGRES_PASSWORD o‘rnatilmagan. Mahalliy sinov uchun uni muhit '
            'o‘zgaruvchisiga qo‘ying yoki SQLite bilan ishlash uchun USE_SQLITE=1 bering.'
        )
    DATABASES = {'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('POSTGRES_DB', 'honim'),
        'USER': os.environ.get('POSTGRES_USER', 'honim'),
        'PASSWORD': POSTGRES_PASSWORD,
        'HOST': os.environ.get('POSTGRES_HOST', '127.0.0.1'),
        'PORT': os.environ.get('POSTGRES_PORT', '5432'),
        # Ulanishni qayta ishlatish: kassa ekrani har 15 soniyada so'rov
        # yuboradi, har safar yangi ulanish ochish ortiqcha kechikish.
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
    }}
PASSWORD_HASHERS = ['django.contrib.auth.hashers.Argon2PasswordHasher', 'django.contrib.auth.hashers.PBKDF2PasswordHasher']
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]
REST_FRAMEWORK = {'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework.authentication.SessionAuthentication'], 'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'], 'DEFAULT_THROTTLE_CLASSES': ['rest_framework.throttling.UserRateThrottle', 'rest_framework.throttling.AnonRateThrottle'], 'DEFAULT_THROTTLE_RATES': {'user': '600/min', 'anon': '100/min', 'login': '10/min'}, 'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination', 'PAGE_SIZE': 100, 'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer']}
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', 'http://127.0.0.1:5173,http://localhost:5173').split(',')
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 43200
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024
# Chek printeri. Bo'sh qoldirilsa chop etish o'chiq bo'ladi (CI va serverda shunday).
# Windows navbati nomi ("POS80") yoki tarmoq manzili ("192.168.0.50:9100").
RECEIPT_PRINTER = os.environ.get('RECEIPT_PRINTER', '')
# Oshxona printeri. Odatda tarmoqda: "192.168.0.202:9100".
KITCHEN_PRINTER = os.environ.get('KITCHEN_PRINTER', '')
RECEIPT_AUTO_PRINT = os.environ.get('RECEIPT_AUTO_PRINT', '1') == '1'
RECEIPT_OPEN_DRAWER = os.environ.get('RECEIPT_OPEN_DRAWER', '0') == '1'
# Testlar hech qachon haqiqiy printerga yozmasligi kerak: qog'oz sarflanadi va
# tarmoq printeri kutib turgani uchun to'plam sekinlashadi.
if 'test' in sys.argv:
    RECEIPT_PRINTER = ''
    KITCHEN_PRINTER = ''
    RECEIPT_AUTO_PRINT = False
TIME_ZONE = 'Asia/Tashkent'
USE_TZ = True
LANGUAGE_CODE = 'uz'
USE_I18N = True
# Panel uchta tilda. Tarjimalar core/translations.py da — gettext emas,
# oddiy lug'at, shuning uchun .mo kompilyatsiya qilish shart emas.
LANGUAGES = [('uz', 'O‘zbekcha'), ('ru', 'Русский'), ('en', 'English')]
STATIC_URL = '/static/'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
