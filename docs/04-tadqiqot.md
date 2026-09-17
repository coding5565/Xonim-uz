# Tadqiqot va manbalar

O'rganilgan sana: 2026-09-16. Ko'lam: Turon loyihasining tanlangan strukturaviy va xizmat fayllari; ochiq loyihalarning repository sahifalari/README'lari va rasmiy hujjatlar. To'liq kod auditi yoki ushbu tizimlarning ishlash sinovi o'tkazilmadi. Ochiq loyihalardan kod ko'chirilmadi.

## Turon_talim

Manzil: `C:/Users/user/Desktop/Turon_talim`.

Ko'rilganlar: frontend package.json, pages/layouts/stores/composables tuzilishi, useApi.ts va auth middleware; backend requirements, core/urls.py, users/models.py, payments/models.py va payments/services.py.

Foydali asos: backend/frontend alohida, Django biznes modullari, rolga mos frontend layoutlar, yagona API mijozi, filial konteksti, moliyaviy service, audit va teskari yozuvlar.

Yangi loyiha uchun o'zgarishlar: Vue TypeScript qat'iy tiplari, versiyalangan API, testlar, dependency lock, serverda filial izolyatsiyasi, moliyaviy yozuvlarda idempotency va parallel ishlash nazorati. Ko'rilgan users modelida qaytariladigan shifrlangan parol nusxasi va visible_password mavjud; Honim'da bu naqsh ishlatilmaydi. Parol xeshi va tiklash oqimi qo'llanadi.

Turon frontend package.json Nuxt 3/Vue 3/Pinia ishlatadi. Honim taklifi Vue 3/Vite; papkalarni tashkil etish va rol layoutlari o'xshash, framework bootstrapi boshqacha. Aynan Nuxt tanlovi ochiq qoladi.

## Ochiq loyihalar

| Manba | Ko'rilgan jihat | Honim uchun xulosa |
| --- | --- | --- |
| [NexoPOS](https://github.com/Blair2004/NexoPOS) | Vue asosidagi POS, kategoriya, savdo, ombor, to'lov, rollar; restoran uchun qo'shimcha modullar | Kassa va operatsion modullarni birga loyihalash. Laravel backendini DRF o'rniga olmaymiz. Qo'shimcha modul mavjudligi uning bepul ekanini anglatmaydi |
| [POS Awesome](https://github.com/ucraft-com/POS-Awesome) | Vue/Vuetify va ERPNext ustidagi POS | Kassa foydalanuvchi oqimi uchun namuna; mustaqil DRF loyihasiga tayyor drop-in emas |
| [rest-erp](https://github.com/rednaxela1813/rest-erp) | Django/DRF restoran domenlari, retsept, buyurtma, smena, to'lov va qurilma navbatlari | Sohaga yaqin modul chegaralari; README barcha imkoniyatlar public REST API orqali ochilmaganini aytadi. Tayyor mahsulot sifatida qabul qilinmaydi |
| [ERPNext ombor](https://docs.frappe.io/erpnext/stock) va [inventarizatsiya](https://docs.frappe.io/erpnext/stock-reconciliation) | Ombor harakatlari va haqiqiy qoldiqni solishtirish | Qoldiqni izsiz tahrirlash o'rniga hujjatlashtirilgan farq yozuvi |

NexoPOS va POS Awesome repository sahifalari GPL-3.0 litsenziyasini ko'rsatadi. Kodni qayta ishlatishdan oldin aniq versiya/fayl litsenziyasi va tarqatish modeli tekshiriladi. rest-erp uchun qayta foydalanish litsenziyasi bu tekshiruvda tasdiqlanmadi; kod ko'chirish uchun asos deb olinmaydi. Hozirgi foydalanish — g'oya va strukturani o'rganish.

## Rasmiy texnik manbalar

- [Django qo'llab-quvvatlanadigan relizlar](https://www.djangoproject.com/download/): 5.2 LTS qo'llab-quvvatlanadigan liniya; aniq patch o'rnatish vaqtida tekshiriladi.
- [DRF 3.16](https://www.django-rest-framework.org/community/3.16-announcement/): Django 5.2 bilan moslik tayanchi.
- [DRF permissions](https://www.django-rest-framework.org/api-guide/permissions/): object, list va create vakolat tekshiruvlari farqi.
- [Django row lock](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update): bir vaqtdagi balans/qoldiq amallari uchun vosita.
- [Django deployment checklist](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/): production sozlamalari.
- [Vue security](https://vuejs.org/guide/best-practices/security): ishonchsiz HTML/template xavflari.
- [QZ Tray signing](https://qz.io/docs/signing): mahalliy chop integratsiyasining imzolash mexanizmi. Qurilma tanlanmagani sabab hozir integratsiya majburiy tanlanmagan.

Hisobot formulalari va biznes jarayonlari Honim uchun taklif; ularni ochiq loyihalarda aynan mavjud deb da'vo qilmaymiz.
