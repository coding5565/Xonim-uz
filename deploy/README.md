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

**Bu buyruq o'zgarmaydi.** Versiya avtomatik yangilanadi — quyiga qarang.

## Versiya va «nimalar qo'shildi»

CRM ichida, yuqori o'ng burchakda ishlab turgan versiya ko'rinadi. Ustiga
bosilsa «Yangilanishlar» sahifasi ochiladi va o'sha versiyada nima
o'zgargani yozilib turadi.

Buning ostida ikkita ALOHIDA narsa bor va ularni aralashtirmaslik kerak:

| | Nima | Kim yozadi |
|---|---|---|
| **Muhr** | commit izi (`a1b2c3d`) va sanasi | hech kim — `git archive` o'zi yozadi |
| **Izohlar** | versiya raqami va o'zgarishlar ro'yxati | dasturchi, kod bilan bitta commitda |

### Muhr qanday ishlaydi

Serverga kod `git archive` orqali boradi, ya'ni u yerda `.git` **yo'q** —
na tarix, na teg. Shuning uchun commit izi arxiv yasalayotgan paytda
fayl ichiga yoziladi (`.gitattributes` dagi `export-subst`):

```
xonim_backend/core/build_stamp.py     <- backend tasviri ko'radi
xonim_frontend/src/build-stamp.ts     <- frontend tasviri ko'radi
```

Ikkita fayl, chunki har bir Docker tasviri faqat o'z papkasini
ko'chiradi. Ikkalasi ham bo'lgani foydali: ular farq qilsa, demak
brauzerdagi sahifa eskirgan va CRM buni o'zi aytadi.

**Do'st hech narsa qilmaydi.** Yuqoridagi buyruqni ishlatsa, muhr o'zi
joylashadi. Uni unutib bo'lmaydi.

> `%(describe:tags)` ataylab ISHLATILMAYDI. O'lchab ko'rilgan: u arxivdagi
> faqat BIRINCHI faylda almashadi, ikkinchisida `%(describe:tags)` bo'lib
> literal qolib ketadi va ekranda o'shanday ko'rinardi. `%s` (commit
> sarlavhasi) ham ishlatilmaydi: ichida qo'shtirnoq bo'lsa faylni
> sintaksis xatosiga aylantiradi. Buni test qulflab turadi.

### Chiqish oldidan dasturchi nima qiladi

1. `xonim_backend/core/releases.py` faylining BOSHIGA yangi yozuv
   qo'shadi: `version`, `released`, uch tilli `title`, va har bir
   o'zgarish uchun `kind` (`yangi` / `tuzatish` / `yaxshi`), `roles`
   (kimga ko'rsatiladi) va `uz` / `ru` / `en` matni.
2. Shu o'zgarishni kod bilan **bitta commitda** yuboradi.
3. `git push`.

Xolos. Teg qo'yish shart emas, versiya faylini alohida yangilash ham
shart emas.

**Unutilsa nima bo'ladi.** Izoh yozilmasa ham muhr baribir o'zgaradi,
ya'ni versiya yangilangani ko'rinib turadi — faqat «bu versiya uchun
izoh yozilmagan» deb yozadi. Yolg'on raqam hech qachon chiqmaydi.

**Eski versiyaga qaytarilsa.** `releases.py` kod bilan birga yuradi,
shuning uchun eski versiya qaytarilganda kelajakdagi izohlar ham
o'z-o'zidan yo'qoladi. Alohida tekshiruv kerak emas.

**Lokal ishlab chiqishda** muhr bo'sh bo'ladi (`git archive` yasalmagan),
va CRM «Ishlab chiqish nusxasi» deb ko'rsatadi — `$Format:%h$` degan
matn ekranga hech qachon chiqmaydi.

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
