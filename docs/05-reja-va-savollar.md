# Ish rejasi

Joriy bosqich: faqat rejalashtirish. Foydalanuvchi 2026-09-16 kuni avval mukammal reja tuzishni, superadmin moliyaviy grafiklarini batafsil belgilashni so'radi. Dastur implementatsiyasi boshlanmagan.

## Tasdiqlangan qarorlar

- Hozir bitta restoran; keyin filiallar qo'shiladi. Filialga bog'lanish boshidan modelda bo'ladi, bir filialli interfeysda ortiqcha tanlov ko'rsatilmaydi.
- Admin xarajatni darhol hisobga kiritadi; superadminning alohida tasdig'i kerak emas. Superadmin grafik, hujjat va audit orqali nazorat qiladi.
- Oxirgi aniqlashtirish: retsept me'yorni hisoblaydi, admin kun oxirida haqiqiy sarfni kiritadi va xomashyo bir marta ayriladi. Qozonda oldindan tayyorlash mavjud. Bu oldingi har-buyurtmada sarf taklifini almashtiradi.
- QR menyu faqat ko'rish uchun. Barcha buyurtmalarni kassir kiritadi; ofitsiant paneli dastlabki ko'lamdan chiqarildi, xodimni buyurtmaga biriktirish qoladi.
- Chek apparati mavjud; oshxona topshirig'i ham chop oqimi orqali rejalashtiriladi. Printer modeli/ulanishi bo'yicha muhokama foydalanuvchi tomonidan keyinga qoldirildi.
- Internet uzilganda savdo davom etadi. Kompyuter va Wi-Fi mavjud. Taklif: mahalliy server/LAN va bulutga sinxronlash; kompyuterning serverga mosligi keyinchalik tekshiriladi.
- Ofitsiant xizmat haqi va xodim ulushi keyingi muhokamaga qoldirildi. Hozir hech qanday foiz taxmin qilinmaydi.

## Bosqichlar va chiqish mezonlari

Ekranlar va kundalik oqimning yozma loyihasi tayyorlandi: 07-ekranlar-va-amallar.md va 08-ish-kuni-va-holatlar.md. Ko'rinadigan maketlar, OpenAPI kontrakt va yakuniy ERD hali bajarilmagan; bu bosqich to'liq yakunlangan deb hisoblanmaydi.

| Bosqich | Natija | Qabul mezoni |
| --- | --- | --- |
| 0. Talablar | Rollar, hisob siyosati, qurilmalar, ekranlar va KPI lug'ati | Ochiq biznes savollariga javob; har KPI manbasi/formulasi aniq |
| 1. UX va kontrakt | Superadmin, admin, kassir POS va QR menyu maketlari; ERD/OpenAPI | Kassir orqali tezkor va stolga xizmat oqimlari maketda tekshiriladi |
| 2. Poydevor | Auth, filial, ruxsat, audit, CI, DB | Boshqa filialga kirish, rolni oshirish, CSRF va sessiya testlari o'tadi |
| 3. Menyu va savdo | Taom, narx, stol, buyurtma, to'lov, smena, chek | Kassa va ofitsiant oqimi oxirigacha; dublikat to'lov yo'q |
| 4. Oshxona va ombor | Retsept, kunlik sarf, xarid, partiya, inventarizatsiya | Kunlik hujjat bir marta sarflaydi; sotilgan/qolgan/isrof porsiyalar qiymati ajratiladi |
| 5. Moliya va superadmin | Jurnal, xarajat, qarz, dashboard, eksport | KPI → tranzaksiya → hujjat bo'yicha summalar to'liq mos |
| 6. Xodim va oylik | Davomat, stavka, avans, hisoblash/to'lash | Oylik ikki marta to'lanmaydi; xizmat ulushi siyosatga mos |
| 7. Qurilma va pilot | Haqiqiy printer, kerakli fiskal/provayder integratsiyasi | Qurilmada sinov, uzilishdan tiklanish, smena yopish, backup tiklash |
| 8. Ishlab chiqarish | Monitoring, yo'riqnoma, boshlang'ich import | Egasi/kassir/omborchi bilan qabul sinovi; qaytish rejasi tayyor |

## Majburiy biznes testlari

1. Bitta to'lovni parallel ikki so'rov yuborsa, bitta pul yozuvi yaratiladi.
2. Kunlik sarf parallel/qayta yuborilganda bir marta yoziladi; me'yor va haqiqiy sarf qo'shib ayrilmaydi. Tayyor porsiya parallel savdoda ortiqcha sotilmaydi.
3. Narx yoki retsept o'zgarsa eski chek va tarixiy tannarx o'zgarmaydi.
4. Tayyorlangan ovqat bekor qilinsa, pul qaytarish bilan ingredient avtomatik tiklanmaydi.
5. Naqd/karta aralash to'lov, qaytim va qisman refund kassa hamda hisobot bilan teng.
6. Xarid, qarz va to'lov foyda/xarajatda ikki marta hisoblanmaydi.
7. Ruxsatsiz xodim URL yoki eksport orqali oylik/filial ma'lumotini ko'rolmaydi.
8. Printer yoki worker qayta ishga tushsa, savdo/to'lov takrorlanmaydi.
9. Oylik avansi berilgan va hisoblangan davrda xarajat ikki marta yozilmaydi.
10. Dashboard, drill-down va eksport bir xil filtr/as_of bilan teng jami beradi.
11. Nol bazali o'sish, bo'sh davr, qisman kun, vaqt zonasi va refundli davrlar to'g'ri chiqadi.
12. Backup boshqa muhitga tiklanadi; pul va ombor registrlari mosligi qayta tekshiriladi.
13. Internet uzilganda mahalliy naqd savdo/chop ishlaydi; qayta ulanishda bulutda dublikat yo'q, summalar teng. Tashqi to'lov noaniqligi yashirilmaydi.

## Aniqlashtiriladigan savollar

1. Taxminiy stollar, bir smenadagi xodimlar va kunlik cheklar soni?
2. Keyinga qoldirilgan: ofitsiant xizmat haqi, hisoblash asosi va xodimga ulush.
3. Qolgan/isrof tayyor porsiyalarni kim kiritadi? Dastlabki taklif: kunlik sarfni kirituvchi admin.
4. Naqd va karta yetarlimi? To'lov/fiskal provayder aniqlashtiriladi. Printer modeli, USB/LAN va qog'oz o'lchami keyingi qurilma bosqichiga qoldirildi.
5. Joriy etishda mavjud kompyuterning OS/quvvati/doimiy ishlashi va UPS tekshiriladi; kompyuter va Wi-Fi borligi allaqachon tasdiqlangan.
6. Oyliklar oylik/kunlik/soatbaymi? Avans, bonus va ofitsiant ulushi qoidalari qanday?
7. Egasi pul olib chiqishi va keyinchalik filiallararo transferlar qanday yuritiladi? Xarajat uchun qo'shimcha tasdiq talab qilinmaydi.
8. Interfeys o'zbekcha yetarlimi, ruscha ham kerakmi? Turon kabi aynan Nuxtmi yoki Vue/Vite maqbulmi?
9. Biznes kuni soat nechada yopiladi? Soliq narx ichidami; xizmat haqi qoidasi qanday? Hisobchi bilan aniqlashtiriladi.
10. Mavjud Excel/daftar hisobi, boshlang'ich ombor, qarz va kassa qoldiqlari bormi?

Yuqoridagi tasdiqlangan qarorlar amal qiladi; qolgan taxminlar savollarga javob kelgach aniqlashtiriladi. Grafiklar uchun avval ma'lumotlar lug'ati va hisob qoidalari kelishiladi; keyin ko'rinadigan maket tayyorlanadi.
