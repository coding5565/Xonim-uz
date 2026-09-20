# Serverga qo'yish

Xonim umumiy serverda bitta loyiha sifatida turadi: Traefik domen bo'yicha
marshrutlaydi, har loyihaning o'z bazasi va o'z papkasi bor
(`~/apps/<loyiha>`). Bu papkadagi fayllar shu qoidaga moslangan.

```
Traefik ──HTTPS──> web (nginx) ──/api──> app (gunicorn) ──> db (PostgreSQL)
                     └── SPA, /media, /static
```

Nega uchta konteyner: baza tashqi tarmoqqa umuman chiqmaydi, ilova esa
faqat nginx orqali ko'rinadi. Traefik faqat `web` konteynerini biladi.

## Birinchi marta qo'yish

```bash
# 1. Manbani serverga olib chiqish (ish stolidagi kompyuterdan)
git archive --format=tar main | ssh -i <kalit> thompson@<ip> \
  'mkdir -p ~/apps/xonim/src && tar -x -C ~/apps/xonim/src'

# 2. Sozlamalar
cd ~/apps/xonim/src/deploy
cp .env.example .env
nano .env            # DOMAIN, DJANGO_SECRET_KEY, POSTGRES_PASSWORD

# 3. Ko'tarish
docker compose up -d --build
docker compose logs -f app

# 4. Birinchi filial va superadmin
docker compose exec app python manage.py create_owner \
    --branch "Xonim Restaurant" --slug xonim --username owner
# Parol ekranga BIR MARTA chiqadi va hech qayerda saqlanmaydi.
```

## Yangilash

```bash
git archive --format=tar main | ssh -i <kalit> thompson@<ip> \
  'rm -rf ~/apps/xonim/src && mkdir -p ~/apps/xonim/src && tar -x -C ~/apps/xonim/src'
cd ~/apps/xonim/src/deploy && docker compose up -d --build
```

Migratsiya va `collectstatic` konteyner ko'tarilganda o'zi bajariladi
(`entrypoint.sh`). Migratsiya yiqilsa ilova ko'tarilmaydi — bu ataylab:
yarim ko'chirilgan baza ustida ishlagan ilova ma'lumotni buzadi.

## Domen almashtirish

Haqiqiy domen olinganda A-yozuvni shu serverga yo'naltiring, so'ng `.env`
dagi uch qatorni almashtiring va qayta ko'taring:

```
DOMAIN=crm.example.uz
DJANGO_ALLOWED_HOSTS=crm.example.uz
CSRF_TRUSTED_ORIGINS=https://crm.example.uz
```

Traefik yangi sertifikatni o'zi oladi (domen shu serverga resolve bo'lishi shart).

## Zaxira nusxa

Baza `xonim_db_data` nomli Docker diskida. Kunlik nusxa:

```bash
mkdir -p ~/backups
docker exec xonim_db pg_dump -U xonim xonim | gzip > ~/backups/xonim_$(date +%F).sql.gz
```

Tiklash:

```bash
gunzip -c ~/backups/xonim_2026-09-20.sql.gz | docker exec -i xonim_db psql -U xonim -d xonim
```

Rasmlar alohida diskda (`xonim_media_files`) — ular ham nusxalanishi kerak.

## Bilib qo'yish kerak

- **Chek printeri ishlamaydi.** Bulutdagi server restoran ichidagi USB
  printerga yeta olmaydi. `RECEIPT_PRINTER` bo'sh qoldirilgan, shuning
  uchun kassa ekranida «talon chiqmadi» ogohlantirishi ko'rinadi. Chek
  chiqarish restoran ichidagi kompyuterga o'rnatilganda ishlaydi.
- **`DJANGO_HTTPS=0` faqat vaqtincha.** U cookie himoyasini o'chiradi va
  parollar ochiq matnda yuriladi. Sertifikat bor bo'lishi bilan `1` ga
  qaytaring.
- **RAM.** VM 4GB ga sozlangan, lekin host uni ~2-3GB gacha siqadi. Bu
  serverda boshqa loyihalar ham paydo bo'lsa, `GUNICORN_WORKERS` ni
  kamaytiring yoki hostingdan to'liq 4GB so'rang.
