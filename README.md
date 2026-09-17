# Honim — restoran boshqaruv tizimi

Holat: ishlaydigan mahalliy MVP yaratildi. Kategoriya/taom, kassir savdosi, buyurtmalar, xarajatlar, ombor sarfi, superadmin dashboardi va faqat ko‘rish uchun QR menyu mavjud. To‘liq restoran CRM bosqichma-bosqich davom etadi.

Frontend: Vue 3 + TypeScript. Backend: Django REST Framework. Asosiy ma'lumotlar bazasi: PostgreSQL.

## Localhostda ishga tushirish

PowerShell orqali loyiha papkasida:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\start-local.ps1
```

So‘ng `http://127.0.0.1:5173` manzilini oching. Mahalliy sinov login/paroli `.local-access.txt` faylida yaratiladi. Ushbu maxfiy fayl Git'ga kiritilmaydi.

Mahalliy sinov SQLite bilan ishlaydi; production rejimi PostgreSQL talab qiladi. Printer/fiskal qurilma, retsept tannarxi, oylik va offline bulut sinxronlash hali ulanmagan.

## Hujjatlar

- [Texnik topshiriq va biznes qoidalari](docs/01-texnik-topshiriq.md)
- [Arxitektura va papkalar tuzilishi](docs/02-arxitektura.md)
- [Ma'lumotlar modeli va API](docs/03-model-va-api.md)
- [O'rganilgan loyihalar va manbalar](docs/04-tadqiqot.md)
- [Amalga oshirish rejasi va ochiq savollar](docs/05-reja-va-savollar.md)
- [Superadmin moliya paneli: grafiklar va hisoblash qoidalari](docs/06-superadmin-moliya.md)
- [Superadmin, admin, kassir va QR menyu ekranlari](docs/07-ekranlar-va-amallar.md)
- [Ish kuni, holatlar, uzilishlar va vakolatlar](docs/08-ish-kuni-va-holatlar.md)

Tayanch loyiha: `C:/Users/user/Desktop/Turon_talim`. U o'qib o'rganildi, o'zgartirilmadi. Quyidagi qarorlar dastlabki taklif bo'lib, savollarga javoblar asosida aniqlashtiriladi. Mutlaq xavfsizlik yoki xatosizlik va'da qilinmaydi; sifat qabul mezonlari va tekshiruvlar bilan baholanadi.
