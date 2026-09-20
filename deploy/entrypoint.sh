#!/bin/sh
# Konteyner har ko'tarilganda: migratsiya -> statik fayllar -> gunicorn.
#
# `set -e` muhim: migratsiya yiqilsa ilova ko'tarilmasligi kerak. Yarim
# ko'chirilgan baza ustida ishlagan ilova ma'lumotni buzadi, va buni keyin
# ajratish qiyin bo'ladi.
set -e

echo "[xonim] baza kutilmoqda..."
python - <<'PY'
import os
import sys
import time

import psycopg

dsn = (
    f"host={os.environ.get('POSTGRES_HOST', 'db')} "
    f"port={os.environ.get('POSTGRES_PORT', '5432')} "
    f"dbname={os.environ.get('POSTGRES_DB', 'xonim')} "
    f"user={os.environ.get('POSTGRES_USER', 'xonim')} "
    f"password={os.environ.get('POSTGRES_PASSWORD', '')}"
)
# Compose healthcheck allaqachon kutadi, lekin baza qayta ishga tushganda
# ilova undan oldin ko'tarilishi mumkin — shuning uchun o'zimiz ham kutamiz.
for attempt in range(60):
    try:
        with psycopg.connect(dsn, connect_timeout=3):
            sys.exit(0)
    except Exception as error:  # noqa: BLE001 - qaysi xato bo'lishidan qat'i nazar kutamiz
        last = error
        time.sleep(2)
print(f'[xonim] bazaga ulanib bo\'lmadi: {last}', file=sys.stderr)
sys.exit(1)
PY

echo "[xonim] migratsiya..."
python manage.py migrate --noinput

echo "[xonim] statik fayllar..."
python manage.py collectstatic --noinput --clear

echo "[xonim] gunicorn ishga tushmoqda"
# --forwarded-allow-ips: Traefik va nginx orqasida turibmiz, X-Forwarded-*
# sarlavhalariga ishonamiz (tashqaridan to'g'ridan-to'g'ri kirish yo'q).
exec gunicorn core.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout 60 \
    --graceful-timeout 30 \
    --max-requests 1000 \
    --max-requests-jitter 100 \
    --forwarded-allow-ips '*' \
    --access-logfile - \
    --error-logfile -
