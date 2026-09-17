# Arxitektura va loyiha strukturasi

## Qaror

Modulli monolit: bitta DRF backend, bitta PostgreSQL va aniq domen chegaralari. Pul, ombor va buyurtmani bitta tranzaksiyada muvofiqlashtirish osonlashadi. Fon vazifalari alohida workerda; kelajakda zarurat bo'lsa xizmatlarni ajratish mumkin.

Vue 3 + TypeScript + Vite + Vue Router + Pinia taklif qilinadi. Turon'dagi pages/layouts/components/composables/stores ajratilishi saqlanadi, Nuxt majburiy emas. Agar aynan Nuxt kerak bo'lsa frontendning ishga tushish qatlami almashtiriladi; domenlar o'zgarmaydi.

Django 5.2 LTS va unga mos DRF liniyasi konservativ boshlang'ich tanlov. Eng yangi major har doim eng mos tanlov emas. O'rnatishda o'sha kundagi qo'llab-quvvatlanadigan patchlar va Python/PostgreSQL mosligi tekshiriladi, aniq versiyalar lock fayllariga yoziladi. Hozir dependencylar o'rnatilmagan.

## Taklif etilgan daraxt

Quyidagi kod papkalari reja; hozir README va docs fayllari yaratilgan.

```text
Honim.uz/
├── honim_backend/
│   ├── manage.py
│   ├── pyproject.toml
│   ├── uv.lock
│   ├── core/
│   │   ├── settings/{base,local,test,production}.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   ├── wsgi.py
│   │   └── celery.py
│   ├── common/             # vaqt, pul turlari, xato formati; biznes logikasi emas
│   ├── users/              # autentifikatsiya, rollar, sessiyalar
│   ├── branches/           # filial, filial a'zoligi, biznes kuni
│   ├── catalog/            # kategoriya, taom, porsiya, narx, rasm
│   ├── dining/             # zal va stollar
│   ├── orders/             # buyurtma, satr, chegirma, holat o'tishlari
│   ├── kitchen/            # tayyorlash navbati va topshiriq
│   ├── recipes/            # retsept versiyalari, ishlab chiqarish
│   ├── inventory/          # partiya, rezerv, harakat, inventarizatsiya
│   ├── purchasing/         # yetkazib beruvchi, xarid, qabul
│   ├── payments/           # to'lov, qaytarish, provayder adapteri
│   ├── finance/            # kassa, smena, xarajat, hisob registrlari
│   ├── staff/              # xodim, davomat
│   ├── payroll/            # oylik, avans, hisob-kitob davri
│   ├── reporting/          # o'qish modellari va eksport
│   ├── public_menu/        # anonim faqat o'qish API
│   ├── printing/           # chek nusxasi, printerlar, ish navbati
│   ├── audit/              # amal tarixi
│   ├── notifications/      # qoldiq va operatsion ogohlantirishlar
│   └── tests/integration/
├── honim_frontend/
│   ├── package.json
│   ├── package-lock.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── public/
│   └── src/
│       ├── app/{main.ts,App.vue,router.ts}
│       ├── assets/styles/{tokens.css,base.css}
│       ├── layouts/{OwnerLayout,AdminLayout,PosLayout,PublicLayout}.vue
│       ├── pages/{auth,owner,admin,pos,menu}/
│       ├── modules/{catalog,orders,inventory,finance,payroll}/
│       ├── components/{ui,forms,tables,feedback}/
│       ├── composables/
│       ├── stores/         # sessiya, filial, UI; server hisobining nusxasi emas
│       ├── api/{client.ts,generated/}
│       ├── types/
│       ├── i18n/
│       └── tests/
├── infra/{docker,nginx,backup}/
├── tests/e2e/
├── docs/
├── .github/workflows/ci.yml
├── .env.example
└── README.md
```

Har backend domenida `models.py`, `services.py`, `selectors.py`, `permissions.py`, `api/{serializers,views,urls}.py`, `tests/`, `migrations/`. Fayl kattalashsa mazmun bo'yicha paketga bo'linadi. Kichik domenda keraksiz qatlamlar yaratilmaydi.

`View → Serializer → Service → Models`; o'qish `Selector` orqali. Serializer shaklni, service biznes qoidasini, DB constraint yakuniy invariantni himoya qiladi. Moliyaviy effektlar signal yoki `model.save()` ichiga yashirilmaydi. Boshqa domen jadvaliga yozish uning service'i orqali.

## Tranzaksiya va takroriy so'rovlar

To'lov, ombor sarfi, refund, smena yopish va oylik to'lovida `transaction.atomic`, zarur qatorda `select_for_update`, bazada unique/check constraint ishlatiladi. Qulflar bir xil tartibda olinadi. Pul Decimal, API'da satr, miqdor Decimal; float pul hisobiga kiritilmaydi.

Pul mutatsiyasida Idempotency-Key + request hash saqlanadi. Bir xil kalit/bir xil so'rov oldingi javobni qaytaradi; boshqa body bilan bir xil kalit 409. Kalit foydalanuvchi, filial va operatsiya doirasida. Bir vaqtdagi dublikatni ham DB unique constraint to'xtatadi.

Tashqi to'lov yoki printer DB tranzaksiyasi ichida kutilmaydi. Biznes yozuvi va outbox yozuvi bir tranzaksiyada; worker outboxni retry bilan bajaradi. Crashdan keyin vazifa tiklanadi. Workerlar takroriy yetkazishga chidamli bo'ladi. Tashqi natija noaniq bo'lsa `unknown` va solishtirish jarayoni; taxminiy muvaffaqiyat yo'q.

Buyurtma tahririda version maydoni: eskirgan mijoz 409 oladi. To'lov boshlanganida hisob versiyasi muzlatiladi. To'langan hisob faqat ruxsatli tuzatish/refund orqali o'zgaradi.

## Xavfsizlik

- Bir domenda frontend va `/api/v1`; Django server sessiyasi, HttpOnly/Secure/SameSite cookie, barcha o'zgarishlarda CSRF. Login ham CSRF bilan himoyalanadi. Token/parol localStorage'da saqlanmaydi.
- Parol faqat Django hasheri bilan; qaytariladigan parol nusxasi yo'q. Egasi uchun MFA va tiklash kodlari; xodim uchun nazoratli parol tiklash. Shaxsiy hisoblar, sessiyani bekor qilish va faol qurilmalar ro'yxati.
- Default deny; har endpoint, list, detail, create, eksport, fayl va jonli kanal uchun filial vakolati. Requestdagi branch ID ishonchli emas. Bog'langan obyektlar ham bir filialga tegishli bo'lishi tekshiriladi.
- DRF object permission list/create'ni avtomatik to'liq himoya qilmaydi: queryset va create tekshiruvlari alohida yoziladi. [Rasmiy manba](https://www.django-rest-framework.org/api-guide/permissions/).
- Login rate limit, vaqtinchalik bloklash, audit; edge limitlari va backend limitlari birgalikda. Xodim rollarini faqat egasi yoki aniq vakolatli rol oshira oladi.
- Yuklangan rasm hajmi, piksel chegarasi va haqiqiy formati tekshiriladi; qayta kodlanadi. Dastlab SVG/HTML yuklash yo'q. Media bajarilmaydigan alohida saqlash qatlamida.
- Vue'da ishonchsiz template va `v-html` ishlatilmaydi. [Vue xavfsizlik tavsiyasi](https://vuejs.org/guide/best-practices/security).
- DEBUG=False, HTTPS, to'g'ri ALLOWED_HOSTS, cheklangan originlar, secretlar muhitdan; productionda standart parol yoki fallback secret yo'q. [Django deployment tekshiruvi](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
- Auditda actor, filial, amal, obyekt, vaqt, request ID, sabab va maxfiylikdan tozalangan o'zgarishlar. Parol, sessiya va karta rekvizitlari logga yozilmaydi. Ilova auditni tahrirlay olmaydi; tashqi saqlash bilan himoya kuchaytiriladi.
- Shifrlangan backup, tiklash sinovi, dependency tekshiruvi, CI, secret scanning. Oylik va moliyaviy eksport faqat ruxsat bilan.

## Ishga tushirish va barqarorlik

Reverse proxy → Vue statik fayllari va DRF; PostgreSQL asosiy haqiqat manbai. Redis kesh va Celery brokeri; Redis yo'qolishi moliyaviy yozuvni yo'qotmasligi kerak. Rasm storage, worker, monitoring, readiness/liveness, xato kuzatuvi va so'rov identifikatori.

Internet uzilganda ishlash talab qilindi. Restoranda kompyuter va Wi-Fi mavjudligi tasdiqlandi. Taklif: mos kompyuterda mahalliy server va PostgreSQL; kassir shu kompyuterdan yoki LAN orqali ishlaydi. Alohida ofitsiant qurilmasi talab qilinmaydi. Mahalliy server filial operatsiyalarining yagona yozuv manbai. Kompyuterning OS, quvvati, uyqu rejimi va doimiy ishlashi joriy etishda tekshiriladi; hozir uning serverga yaroqliligi sinovdan o'tmagan. Server, router yoki elektr uzilishini bu yechim o'zi bartaraf etmaydi; UPS mavjudligi ochiq.

Bulutda masofaviy hisobot nusxasi va ommaviy QR menyu. Mahalliy outbox hodisalarni xavfsiz kanal bilan filial ID, event ID va ketma-ketlik asosida yuboradi; retry/deduplication majburiy. Internet yo'q paytda bulut oxirgi sinxronlash vaqtini ko'rsatadi. Masofaviy moliyaviy o'zgartirishlar aloqa tiklanguncha yopiq; ikki mustaqil yozuvchi manba yo'q. Keyingi filiallar o'z mahalliy manbaiga ega bo'ladi.

Naqd savdo va mahalliy printer internetdan mustaqil ishlashi rejalashtiriladi. Tashqi karta/fiskal provayderning offline ishlashi alohida tekshiriladi; noaniq to'lov muvaffaqiyatli deb yozilmaydi. QR menyu bulutda mijoz interneti bilan ochiladi; restorandagi uzilish menyu narx/mavjudlik yangilanishini kechiktirishi mumkin. Mijoz internetisiz menyu uchun lokal Wi-Fi yo'li alohida loyihalanadi. Qurilma/deploy tanlovi hali yakunlanmagan.

Vaqt bazada UTC, ko'rsatish Asia/Tashkent. Biznes kunining yopilish soati sozlama; yarim tundan keyingi smena hisobotlari shu qoidaga bo'ysunadi. Backup uchun dastlab RPO ≤ 15 daqiqa, RTO ≤ 2 soat maqsad taklif qilinadi; amalda tiklash sinovi bilan isbotlanadi.
