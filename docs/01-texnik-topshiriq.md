# Texnik topshiriq

## 1. Maqsad va chegara

Restoran savdosi, stollar, oshxona, ombor, xarid, xarajat, kassa, xodimlar va boshqaruv hisobotlarini yagona tizimga birlashtirish. Bu loyiha CRM funksiyalari bilan birga POS va operatsion hisobni ham qamrab oladi.

Tasdiqlangan talab: ommaviy QR menyu faqat ko'rish uchun. Unda savat, to'lov va buyurtma yuborish funksiyasi bo'lmaydi. Ichki xodimlar buyurtmani himoyalangan panelda kiritadi.

Tasdiqlangan qarorlar: hozir bitta restoran, keyin filiallar qo'shiladi; admin xarajatni alohida superadmin tasdig'isiz darhol hisobga kiritadi. Oxirgi aniqlashtirish: kun oxirida haqiqiy xomashyo sarfi kiritilib ombordan ayriladi; retsept me'yoriy sarfni hisoblaydi. Mavjud chek printeridan foydalaniladi. Internet uzilganda mahalliy savdo davom etishi kerak. Ofitsiant xizmat haqi va ulushi keyin muhokama qilinadi, hozircha foiz belgilanmaydi.

Dastlabki taxminlar: UZS; Asia/Tashkent; o'zbekcha interfeys. Tasdiqlangan: barcha buyurtmalarni kassir kiritadi; ofitsiant uchun alohida panel dastlabki ko'lamga kirmaydi. Restoranda kompyuter va Wi-Fi mavjud. Printer modeli/ulanishi keyin aniqlashtiriladi.

## 2. Rollar

| Rol | Vakolat |
| --- | --- |
| Superadmin / egasi | Barcha filiallar, xodimlar, rollar, narx siyosati, xarajat nazorati, oylik, hisobot, audit va sozlamalar |
| Admin / menejer | Biriktirilgan filial menyusi, ombor, xarid, xarajat va operatsiyalar; xarajatni darhol hisobga kiritish |
| Kassir | Smena, buyurtma, hisob, to'lov, chek; berilgan limitdagi chegirma |
| Ofitsiant | Xodim sifatida stol/buyurtmaga biriktiriladi; buyurtma va holatlarni kassir kiritadi, alohida panel hozir kerak emas |
| Oshxona | Oshxona buyurtmalari, tayyorlash holati, taom mavjudligi; moliya va oylik yopiq |
| Omborchi | Qabul, qoldiq, inventarizatsiya, hisobdan chiqarish; oylik va foyda yopiq |
| Hisobchi | Xarajat, yetkazib beruvchi qarzi, oylik va hisobotlar — berilgan vakolat doirasida |
| Mehmon | Ommaviy menyu: rasm, nom, tavsif, narx va mavjudlik |

Kichik restoranda admin va kassir vakolatlari bir foydalanuvchiga berilishi mumkin. Rol bilan birga `branch + action + object` tekshiruvi ishlaydi. Biznes superadmini avtomatik ravishda Django texnik superuseri bo'lmaydi. Oxirgi faol egani bloklash yoki vakolatini olib tashlash taqiqlanadi.

## 3. Savdo oqimlari

### Kassa orqali tezkor savdo

1. Kassir smena ochadi va boshlang'ich naqdni kiritadi.
2. Kategoriya yoki qidiruvdan taom tanlaydi; porsiya, son va izohni belgilaydi.
3. Server amaldagi narx, chegirma, soliq va xizmat haqidan yakuniy summani hisoblaydi.
4. Naqd, karta yoki aralash to'lov yoziladi; naqd berilgan summa va qaytim alohida ko'rsatiladi.
5. Buyurtma/to'lov tasdiqlanadi, zarur bo'lsa oshxonaga topshiriq tushadi, chek chop etish navbatiga qo'yiladi.

### Ofitsiant bilan xizmat

1. Kassir zal/stolni tanlaydi, mehmonlar soni va xizmat qilayotgan ofitsiantni biriktiradi.
2. Ofitsiant buyurtmani kassirga yetkazadi; kassir taomlarni kiritib oshxona topshirig'ini chopga yuboradi. Keyingi qo'shimchalar alohida topshiriq bo'ladi.
3. Oshxona/ofitsiant xabariga ko'ra kassir tayyorlash va yetkazish holatlarini qayd etadi. Alohida oshxona ekrani kelajakdagi ixtiyoriy imkoniyat; dastlab printer oqimi asosiy. Qurilmaga yo'naltirish printer tafsilotlari bilan aniqlashtiriladi.
4. Yakunda taomlar, chegirma, xizmat haqi va jami ko'rsatilgan oldindan hisob chiqariladi.
5. Kassir to'lovni qabul qiladi; to'liq yopilgach yakuniy chek chiqariladi va stol bo'shatiladi.

Buyurtma bajarilishi va to'lov holati alohida: tayyor taom hali to'lanmagan bo'lishi mumkin. Oldindan hisob to'lov tasdig'i emas. Stol ko'chirish, chek bo'lish, buyurtmalarni birlashtirish audit va vakolat bilan bajariladi.

## 4. Menyu va narxlar

Kategoriyalar tartibi, rasmlar, nom/tavsif, porsiyalar, modifikatorlar, ingredientlar, allergenlar, tayyorlash vaqti, mavjudlik, arxivlash va filialga xos narxlar. Modifikator narx va retseptga ta'sir qilishi mumkin. Tarozida sotiladigan taom kerak bo'lsa kasr miqdor qo'llanadi.

Buyurtma satrida nom, narx, soliq, retsept versiyasi va modifikatorlar nusxasi saqlanadi. Keyingi narx o'zgarishi eski chekni o'zgartirmaydi. Tasdiqlangan satrni yashirin tahrirlash o'rniga yangi satr yoki sababli bekor qilish ishlatiladi.

## 5. Ombor va retsept

Xomashyo taomdan alohida katalogda yuritiladi. Asosiy birliklar: kg, litr, dona; g↔kg va ml↔l konversiyasi. Dona→kg kabi o'tish uchun mahsulotga xos koeffitsiyent zarur.

Oxirgi aniqlashtirish oldingi har-buyurtmada avtomatik xomashyo sarfi taklifini almashtiradi. Retsept me'yoriy sarfni hisoblaydi; admin kun oxirida haqiqiy sarfni kiritganda tizim uni bir marta ayiradi. Misol: me'yor 1.5 kg guruch, haqiqiy sarf 1.7 kg — ombordan 1.7 kg ayriladi, 0.2 kg farq ko'rsatiladi. Me'yor va haqiqiy sarf qo'shib ayrilmaydi.

Kun ichida registrdagi xomashyo qoldig'i va retseptdan kutilgan qoldiq alohida ko'rsatiladi. Buyurtma yoki to'lov xomashyoni kamaytirmaydi. Kunlik sarf hujjatida filial, ombor, biznes kuni, mahsulot, birlik va haqiqiy miqdor saqlanadi. Parallel yoki takroriy yuborish dublikat sarf yaratmaydi. Tuzatish teskari yozuv va yangi versiya bilan. Refund mahsulotni avtomatik tiklamaydi.

Qozonda oldindan tayyorlash mavjud. Partiyada tayyorlangan, sotilgan, qolgan va isrof porsiyalar yuritiladi. Sotuv tayyor porsiyani kamaytiradi; xomashyo kunlik sarfda bir marta ayriladi. Kunlik sarf partiyalarga taqsimlanadi: sotilgan qism tannarx, saqlanadigan qism tayyor mahsulot aktivi, tashlangan qism isrof. Taqsimot yetishmasa taom bo'yicha marja «to'liq emas» deb belgilanadi. Retsept bog'lanishida sikl taqiqlanadi.

Ombor operatsiyalari: kirim, sarf, qaytarish, isrof, inventarizatsiya farqi, filiallararo transfer. Tasdiqlangan operatsiyalar o'chirilmaydi; teskari yozuv bilan tuzatiladi. Partiya, yaroqlilik muddati, minimal qoldiq, yetkazib beruvchi, kirim narxi saqlanadi. Jismoniy chiqish uchun FEFO, tannarx uchun dastlab o'rtacha tortilgan qiymat taklif qilinadi.

Inventarizatsiyada sanash vaqti va undan keyingi harakatlar hisobga olinadi. Manfiy mavjud qoldiq odatda taqiqlanadi. Kam qolgan mahsulot, tugagan taom va muddati yaqinlashgan partiyalar haqida ogohlantirish bo'ladi.

## 6. Xarid, pul va foyda

Xarid buyurtmasi, tovar qabul qilish va yetkazib beruvchiga to'lash alohida hujjatlardir. Qisman qabul/qisman to'lov, qarz, qaytarish va yetkazish xarajatlari qo'llanadi.

- Pul oqimi: kirgan pul − chiqqan pul.
- Sotuv marjasi: sof savdo − sotilgan taom tannarxi.
- Operatsion natija: marja + tegishli boshqa daromad − davr xarajatlari.

Misol: 1 mln so'm mahsulot sotib olindi, undan 300 ming so'mlik qismi sarflandi. Omborda 700 ming so'm aktiv qoladi. Xarid to'langan bo'lsa kassadan 1 mln chiqadi, lekin shu davr taom tannarxi 300 ming. Xaridning 1 mln summasi foydadan yana to'liq ayrilmaydi.

Ijara, kommunal, transport, ta'mir va boshqa kundalik xarajatlarda kategoriya, sana, mas'ul, izoh va hujjat bo'ladi. Admin saqlaganda tekshiruvdan o'tgan xarajat darhol hisobga olinadi, superadmin tasdig'i kutilmaydi. Kim kiritgani va keyingi tuzatishlar auditda saqlanadi. Hisoblangan xarajat va uning to'lovi alohida yuritiladi: to'lanmagan xarajat kassani kamaytirmaydi. Soliq va fiskal hisob qoidalari integratsiya tanlangach mutaxassis bilan aniqlashtiriladi; operatsion hisobot avtomatik rasmiy buxgalteriya hisobotiga tenglashtirilmaydi.

Smena yopilishi: boshlang'ich naqd + naqd tushum − qaytarish − naqd chiqim − inkassatsiya = kutilgan naqd. Kassir sanagan naqd bilan farq sabab bilan saqlanadi. Karta tushumi naqd balansga qo'shilmaydi.

## 7. Xodim va oylik

Xodim kartasi, ish davri, lavozim, smena/davomat, oylik stavkasi, bonus, avans va ruxsat etilgan ushlanmalar. Stavka tarixli bo'ladi. `Hisoblandi → tasdiqlandi → qisman/to'liq to'landi` holatlari. Bir davr bir xodimga qayta hisoblanganda dublikat yuzaga kelmaydi.

Mehmonga qo'shilgan xizmat haqi va ofitsiantga beriladigan ulush ikki alohida tushuncha. Foydalanuvchi bu masalani keyinga qoldirdi: hozir foiz, hisoblash asosi yoki taqsimot belgilanmaydi. Hujjatdagi xizmat haqiga oid oqimlar shartli imkoniyat; haqiqiy hisobga ulashdan oldin siyosat aniqlashtiriladi.

## 8. Cheklar va qurilmalar

Oldindan hisob, yakuniy to'lov cheki va oshxona topshirig'i alohida shablon. Chekda filial, raqam, vaqt, kassir/ofitsiant, stol, taomlar soni va narxi, chegirma, xizmat, soliq, jami, to'lov usuli, berilgan pul va qaytim ko'rsatiladi.

58/80 mm format printer modeli aniqlangach tanlanadi. Dastlab brauzer orqali chop etish; avtomatik chop uchun mahalliy print bridge yoki printerga mos SDK. Bulutdagi server USB printerga to'g'ridan-to'g'ri kira olmaydi. Oddiy termal chek fiskal integratsiya bajarilganini bildirmaydi.

PrintJob `queued/sent/confirmed/failed/unknown` holatlari bilan kuzatiladi. Printer javobi noaniq bo'lsa avtomatik cheksiz qayta chop etilmaydi; operator tekshiradi. Qayta chopda nusxa belgisi va audit bo'ladi; to'lov qayta yozilmaydi.

## 9. Hisobot va interfeys

Egasi: kunlik savdo, naqd/karta, xizmat haqi, operatsion natija, xarajat, ombor qiymati, qarz, oylik, qaytarish, chegirma, eng ko'p sotilgan taomlar va tannarx ulushi. Sana/filial filtrlari va har raqamdan manba operatsiyaga o'tish.

Kassir: chapda kategoriya/qidiruv, markazda rasmli taomlar, o'ngda doimiy hisob paneli; stol va ofitsiant tanlash, ochiq hisoblar hamda chop holati shu panelda. Ofitsiant uchun telefon paneli dastlab yaratilmaydi. Oshxonaga o'qiladigan chop topshirig'i; oshxona ekrani keyinchalik ixtiyoriy. Superadmin: tartibli yon menyu va ma'lumot zichligi boshqariladigan jadvallar.

Vizual yo'nalish: neytral fon, to'q matn, bitta asosiy aksent, bir xil ikonlar, aniq tipografiya; rang bilan birga holat matni. Klaviatura, fokus, kontrast, kamida 44px sensor tugmalar, yuklanish/bo'sh/xato/aloqa uzilishi holatlari. Muhim amallarda server javobisiz muvaffaqiyat ko'rsatilmaydi.

## 10. Keyingi imkoniyatlar

Bron qilish, sodiqlik dasturi, mijozlar tarixi, yetkazib berish platformalari, kengaytirilgan prognoz, ko'p tashkilotli SaaS va to'liq offline sinxronlash — asosiy oqimlar barqarorlashgach alohida bosqich. Mehmon ma'lumotlari faqat kerak bo'lganda olinadi.
