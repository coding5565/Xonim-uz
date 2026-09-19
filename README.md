# Honim — restoran boshqaruv tizimi

[![CI](https://github.com/coding5565/Xonim-uz/actions/workflows/ci.yml/badge.svg)](https://github.com/coding5565/Xonim-uz/actions/workflows/ci.yml)

Haqiqiy restoran uchun yozilgan kassa va boshqaruv tizimi: savdo, oshxona,
ombor, moliya va nazorat — bitta joyda. O'zbek tilida, rus va ingliz tillari
to'liq qo'llab-quvvatlanadi.

> **In short:** a restaurant POS and management system built for a working
> restaurant in Uzbekistan — point of sale, kitchen tickets, stock, payroll and
> financial reporting. Django REST Framework + React, PostgreSQL, 183 tests.
> Interface in Uzbek, Russian and English.

---

## Nima qila oladi

**Kassa**
Zal (stol xaritasi bilan), olib ketish, Uzum va Yandex — har biri alohida
kiriladi va alohida hisoblanadi. Chegirma, ofitsiant ulushi, chek chop etish,
to'lovni qaytarish. Tarmoq uzilsa takroriy so'rov ikkinchi hisob ochmaydi.

**Oshxona**
Tayyorlangan porsiyalar hisobi: oshxona ertalab partiya pishiradi, talon esa
«shuni yig'inglar» degan signal. Tayyori yo'q taom sotilmaydi.

**Ombor va retsept**
Masalliq narxi bitta joyda kiritiladi, retsept shundan hisoblanadi. Sotuvda
masalliq retsept bo'yicha ayriladi — lekin bu taxmin, sotuvni to'xtatmaydi.
Admin haqiqiy sarfni kiritadi, superadmin ikkalasini solishtiradi.

**Moliya**
Foyda zanjiri: tushum → tannarx → yalpi foyda → xarajat → sof foyda. Har bir
raqam bosiladi va qayerdan kelgani ochiladi. Tannarx qamrovi ko'rsatkichi soxta
marjani fosh qiladi.

**Nazorat**
Har bir amal jurnalga tushadi — kim, qachon, nima uchun. Yozuvni o'chirib
bo'lmaydi. Kun yakuni: kassadagi naqd sanaladi va tizim hisobi bilan
solishtiriladi.

**Oyliklar, xodimlar, ofitsiantlar, QR menyu** ham bor.

---

## Texnologiya

| Qatlam | Nima |
|---|---|
| Backend | Django 5.2 + Django REST Framework |
| Frontend | React 19 + TypeScript + Vite |
| Baza | PostgreSQL 17 |
| Autentifikatsiya | Sessiya + CSRF, Argon2 parol xeshi |
| Chek printeri | ESC/POS (Windows spooler yoki TCP 9100) |

---

## Ishga tushirish

Kerak: Python 3.12, Node 22, PostgreSQL 17.

```bash
# 1. Baza
createdb -O honim honim

# 2. Backend
cd honim_backend
pip install -r requirements.lock
export DJANGO_SECRET_KEY=...            # ixtiyoriy kalit
export POSTGRES_DB=honim POSTGRES_USER=honim POSTGRES_PASSWORD=...
python manage.py migrate
python manage.py runserver 127.0.0.1:8000

# 3. Frontend (alohida terminal)
cd honim_frontend
npm ci
npm run dev
```

So'ng `http://127.0.0.1:5173`.

Windowsda ikkalasini birdan ishga tushirish uchun `start-local.ps1` bor.
Mahalliy sinov login/paroli `.local-access.txt` faylida yaratiladi — u Git'ga
kiritilmaydi.

---

## Tekshirish

```bash
cd honim_backend && python manage.py test   # 183 ta test
ruff check honim_backend                    # Python linteri

cd honim_frontend && npm run typecheck      # TypeScript
npm run lint                                # ESLint
npm run build                               # yig'ish
```

Hammasi har push'da GitHub Actions'da ham ishlaydi, testlar PostgreSQL bilan.

---

## Diqqat qilingan joylar

Restoran tizimida xato pul degani, shuning uchun bir nechta qaror ataylab
qabul qilingan:

- **Pul faqat `Decimal`** — hech qayerda suzuvchi son yo'q. Tannarx va
  ofitsiant foizi sotuv paytida hisobga muzlatiladi, keyin narx o'zgarsa ham
  o'tgan hisobotlar o'zgarmaydi.
- **Takroriy so'rov ikkinchi hisob ochmaydi** — har bir buyurtma va ombor
  harakatida idempotentlik kaliti bor. Tarmoq javobni yo'qotsa, kassir qayta
  bosadi va bir xil natija oladi.
- **Chek chop etish tranzaksiyadan tashqarida** — printer javob bermasa
  (4+6 soniya kutish) hisob qatorlari qulflangan holda turmasligi kerak.
- **Jurnalni o'chirib bo'lmaydi** — `PROTECT` bog'liqliklari yozuvni ushlab
  turadi; bekor qilingan hisob ham tarixda qoladi, faqat holati o'zgaradi.
- **Bir xil raqam hamma joyda bir xil** — buni alohida test qo'riqlaydi: bir
  kunni boshidan oxirigacha yuritib, Dashboard, Sotuv, Moliya, Smena va
  Hisobotlar bir xil summani ko'rsatishini tekshiradi.
- **Uch til testda tekshiriladi** — server yuboradigan har bir yorliqning
  tarjimasi borligini, ikki lug'at bir xil kalitlarga egaligini va sanoq
  shakllari to'g'ri ishlatilganini testlar tasdiqlaydi.
- **PostgreSQL mahalliy sinovda ham** — SQLite bir xil kodni boshqacha
  bajaradi (butun sonlarni bo'lganda kasrni tashlaydi), ya'ni mahalliy yashil
  natija serverda takrorlanmasligi mumkin.

---

## Hujjatlar

- [Texnik topshiriq va biznes qoidalari](docs/01-texnik-topshiriq.md)
- [Arxitektura va papkalar tuzilishi](docs/02-arxitektura.md)
- [Ma'lumotlar modeli va API](docs/03-model-va-api.md)
- [O'rganilgan loyihalar va manbalar](docs/04-tadqiqot.md)
- [Amalga oshirish rejasi va ochiq savollar](docs/05-reja-va-savollar.md)
- [Superadmin moliya paneli](docs/06-superadmin-moliya.md)
- [Ekranlar va amallar](docs/07-ekranlar-va-amallar.md)
- [Ish kuni, holatlar va vakolatlar](docs/08-ish-kuni-va-holatlar.md)

`docs/01`–`docs/08` loyihalash bosqichida yozilgan. Ularning ba'zilarida
frontend uchun Vue taklif qilingan — yakuniy tanlov React bo'ldi, qolgan
qarorlar kuchida qoldi.

---

## Holat

Tizim haqiqiy restoranda ishlatish uchun yozilmoqda. Hozircha yo'q: fiskal
qurilma integratsiyasi, offline rejim va bulut sinxronizatsiyasi, frontend
testlari.

Mutlaq xatosizlik va'da qilinmaydi — sifat testlar, linterlar va CI bilan
o'lchanadi.
