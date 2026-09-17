# Ekranlar va amallar spetsifikatsiyasi

Holat: implementatsiyaga tayyorlash uchun ekran rejasi. Quyidagi yangi UX qarorlari tavsiya; avvalgi tasdiqlangan biznes qoidalari ustuvor. Kod yoki ishlaydigan maket emas.

## 1. Umumiy tuzilish

Asosiy ish joylari: superadmin, admin/kassir va ommaviy QR menyu. Admin va kassir bitta xodim bo'lishi mumkin; ekranda faqat berilgan vakolatlar ochiladi. Ofitsiant buyurtmaga biriktiriladigan xodim, alohida kirish paneli yo'q.

Superadmin yon menyusi: Umumiy holat, Moliya, Savdo, Menyu, Ombor, Xaridlar, Xodimlar, Oylik, Audit, Sozlamalar. «Moliya» ichida tushum, xarajat, pul oqimi, foyda va qarz sahifalari. Kam ishlatiladigan sozlamalar kundalik amallardan ajratiladi.

Admin yon menyusi: Ish kuni, Kassa, Ochiq hisoblar, Menyu, Ombor, Xaridlar, Xarajatlar, Smena, Cheklar. Xodim/oylik yoki umumiy foyda standart admin vakolatiga kirmaydi; egasi aniq ruxsat bersa ochiladi. Kassirning tor rolida Kassa, Ochiq hisoblar, Smena va Cheklar qoladi.

Yuqori panel: restoran nomi, biznes kuni, foydalanuvchi, mahalliy aloqa, bulutga sinxronlash va printer holati. Bir filial borida filial tanlash ko'rsatilmaydi. Bulut uzilishi va mahalliy server uzilishi turli xabar beradi.

## 2. Superadmin ekranlari

| ID / sahifa | Tarkib | Asosiy amallar | Natija |
| --- | --- | --- | --- |
| SA-01 Umumiy holat | Savdo, tushum, xarajat, pul qoldig'i, foyda taxmini/yakuniyligi; trend; muammolar | Davr tanlash, taqqoslash, KPI ochish | Bir xil filtr bilan tafsilotga o'tadi |
| SA-02 Tushumlar | To'lov sanasi, chek, kassir, usul, summa, qaytarish, terminal holati | Filter, chekni ochish, eksport | Pul kirimining manbasini ko'rsatadi |
| SA-03 Xarajatlar | Kategoriya, maqsad, oluvchi, admin, summa, to'lov holati, hujjat | Xarajat qo'shish, tafsilot, tuzatish | Xarajat darhol hisobga olinadi; tasdiq navbati yo'q |
| SA-04 Pul oqimi | Hisoblar qoldig'i, kirim/chiqim, ichki transfer, kassa farqi | Hisobni ochish, inkassatsiya/transfer qaydi | Pulning qayerda ekanini ko'rsatadi |
| SA-05 Foyda | Sof savdo, tannarx, isrof, davr xarajati, natija; taom marjasi | Davr/taom bo'yicha ochish | Ma'lumot yetishmasa aniq foyda deb ko'rsatmaydi |
| SA-06 Qarzlar | Yetkazib beruvchi va xodimga qarz, muddat, to'lovlar | Qarz hujjatini ochish, to'lov qaydi | Qisman to'lov qarzdan ayriladi |
| SA-07 Savdo | Buyurtmalar, sotilgan taomlar, chegirma/refund, stol/ofitsiant | Chek ochish, sabablarni tekshirish | Buyurtma va to'lov holati alohida |
| SA-08 Ombor tahlili | Registr/kutilgan qoldiq, kunlik sarf farqi, partiya, isrof | Sarf hujjati va kirimni ochish | Xomashyo va tayyor porsiyalar ajratilgan |
| SA-09 Xodimlar | Lavozim, filial, faol holat, kirish vakolati | Xodim/admin yaratish, bloklash, rol berish | Xodim kartasi bilan login alohida |
| SA-10 Oylik | Davr, stavka, hisoblangan, avans, qolgan, to'langan | Hisoblash, tekshirish, tasdiqlash, to'lash | Dublikat davr/to'lov bloklanadi |
| SA-11 Audit | Kim, nima, qachon, obyekt, sabab, oldingi/yangi qiymat | Qidirish, obyektga o'tish | Audit tahrirlanmaydi |
| SA-12 Sozlamalar | Restoran, stollar, hisoblar, vakolatlar, biznes kuni, backup holati | Sozlama tahriri | Tarixiy cheklar qayta hisoblanmaydi |

SA-01 sahifa tartibi: filtrlar → 4–6 asosiy KPI → savdo/pul dinamikasi → xarajat tarkibi va foyda tarkibi → amaliy e'tibor talab qiladigan ro'yxat. Barcha grafiklarni bir ekranga tiqishtirish o'rniga qolganlari o'z bo'limida. Grafiklarning formulalari 06-superadmin-moliya.md da.

SA-03 xarajat kartasi: sarlavhada summa va holat; asosiy qismda «nimaga ishlatildi», kategoriya, oluvchi, sana; pastda to'lov manbai, hujjatlar va tarix. Egasi summadan bir-ikki o'tishda manba hujjatini topishi kerak.

SA-09 da xodim yaratish login yaratishni majburiy qilmaydi: ofitsiant uchun ism/lavozim yetarli. Admin hisobida vaqtinchalik kirish/tiklash oqimi va birinchi kirishda parol o'zgartirish; mavjud parolni ko'rish tugmasi bo'lmaydi. Oxirgi faol egani o'chirish/bloklash rad etiladi.

## 3. Kassir ish joyi

### POS-01 Smena ochish

Ko'rsatish: kassir, kassa, biznes kuni, oldingi yopilish, mavjud faol smena. Maydon: boshlang'ich sanalgan naqd va tafovut bo'lsa izoh. Tugma: «Smenani ochish». Qayta bosish ikkinchi smena yaratmaydi. Boshlang'ich qoldiq yangi daromad sifatida yozilmaydi; haqiqiy qo'shilgan pul alohida kirim hujjati bo'ladi.

### POS-02 Taom tanlash

Uch qism: kategoriya/qidiruv; rasmli taomlar; doimiy buyurtma paneli. Yuqorida «Tezkor savdo» va «Stolga xizmat» tanlovi. Taom kartasida nom, porsiya narxi, mavjudlik; rasm yo'qligi ishlashni to'xtatmaydi.

Buyurtma satri: taom/porsiya, son, birlik narxi, jami, izoh, modifikator, oshxonaga yuborilganlik. Tez tugmalar: sonni oshirish/kamaytirish, izoh, olib tashlash. Yuborilgan satrda kamaytirish/bekor qilish sabab va vakolat talab qiladi. Narxni kassir erkin yozmaydi; ruxsatli chegirma alohida amal.

Hisob paneli: taomlar jami, chegirma, kelishilgach xizmat haqi, soliq siyosati, jami, avval to'langan, qolgan. Tugmalar: «Saqlash», «Oshxonaga yuborish», «Oldindan hisob», «To'lov». Qoralama va serverda saqlangan buyurtma aniq ajraladi.

### POS-03 Stollar va ochiq hisoblar

Kartalarda stol nomi, bo'sh/band holati, ochiq hisob summasi, ochilgan vaqt va ofitsiant. Rang yonida holat matni. Stolni bosganda mavjud hisob ochiladi. Bir stolga odatda bitta faol tashrif; alohida cheklar shu tashrif ichida boshqariladi.

Yangi stol hisobida stol, ofitsiant va ixtiyoriy mehmonlar soni. «Stolni almashtirish» maqsad stol bo'shligini serverda tekshiradi. Band stolga qo'shish alohida «Hisoblarni birlashtirish» amali; to'lov boshlangan/yakunlangan hisoblar oddiy birlashtirilmaydi. Amal versiya nazorati va audit bilan.

Hisob bo'lish: tanlangan satr/miqdorlarni yangi hisobga ajratish; umumiy miqdor va pul saqlanadi. Boshlang'ich relizda aralash to'lov bilan bo'lib to'lash asosiy; murakkab chek bo'lish alohida qabul ssenariysi o'tgach yoqiladi.

### POS-04 Oshxona topshirig'i

Chop tarkibi: buyurtma/stol raqami, vaqt, kassir, ofitsiant, taomlar soni va izoh. Qo'shimcha buyurtmada faqat yangi satrlar chop etiladi. Oldingi satr qayta chop qilinsa «NUSXA». Bekor qilingan yuborilgan satr uchun alohida bekor qilish xabari; jim yo'qotish yo'q.

Holat: navbatda / yuborildi / xato / natija noaniq. «Chop holatini tekshirish» va «Nusxa chiqarish» tugmalari. Qurilma tasdig'i bo'lmasa «qog'oz chiqdi» deb da'vo qilinmaydi. Printer muammosi buyurtmani yo'qotmaydi.

### POS-05 To'lov

Oyna: hisob raqami, jami, oldingi to'lov, qolgan; naqd/karta/aralash tanlash. Naqdda berilgan pul va qaytim. Aralashda har usulga ajratilgan summa. Misol: 100 000 hisob, 60 000 karta va 50 000 naqd berildi → naqd hisobga 40 000, qaytim 10 000.

«To'lovni qayd etish» serverga bitta idempotent amal yuboradi. Bosish vaqtida qayta bosish bloklanadi, lekin asosiy himoya serverda. Javob yo'qolsa yangi to'lov yaratish o'rniga oldingi amal holati olinadi. Terminal tasdiqlanmagan karta «to'langan» hisoblanmaydi.

Muvaffaqiyatdan keyin chek navbatga tushadi. Chek chiqmasa to'lov saqlanib qoladi; «To'lov olindi, chek kutilmoqda» ko'rinadi. Stol to'lov to'liq va xizmat tugagach bo'shatiladi; tezkor oldindan to'lov buyurtmani darhol tayyor/yetkazilgan deb belgilamaydi.

### POS-06 Cheklar va qaytarish

Qidiruv: chek raqami, sana, kassir, summa. Tafsilot: asl satrlar/narx, to'lovlar, choplar va refund. Tugmalar: nusxa, ruxsat bo'lsa «Qaytarish». Refundda satr/miqdor yoki ruxsatli summa, sabab va to'lov usuli. Limit — hali qaytarilmagan asl summa. Xomashyo avtomatik tiklanmaydi.

### POS-07 Smena yopish

Ko'rsatish: ochiq hisoblar, noaniq to'lovlar, qaytarishlar, naqd kirim/chiqim, kutilgan naqd. Kassir sanalgan naqdni kiritadi; farqda sabab majburiy. Yopish yangi savdoni shu smenaga yozishni to'xtatadi, eski yozuvni o'chirmaydi.

Ochiq stol bo'lsa avtomatik qarzni yopish yo'q: davom etuvchi smenaga nazoratli topshirish yoki ochiq majburiyat sifatida aniq qayd. Hisobni topshirish to'lov deb yuritilmaydi. Smena yopilishi va oshxona kunlik sarfini yopish ikki alohida amal.

## 4. Admin ish joyi

| ID / ekran | Maydonlar va tarkib | Amallar / tekshiruv |
| --- | --- | --- |
| AD-01 Ish kuni | Faol smena, ochiq hisoblar, kam mahsulot, kiritilmagan sarf, chop xatolari | Tegishli muammoga o'tish |
| AD-02 Kategoriyalar | Nom, tartib, rasm, faol/arxiv | Qo'shish, tartiblash, arxivlash; ishlatilgan tarix o'chmaydi |
| AD-03 Taomlar | Nom, kategoriya, rasm, tavsif, porsiya, narx, mavjudlik | Saqlash, ommaviy menyuda ko'rish, arxivlash |
| AD-04 Retsept | Versiya, chiqish miqdori, ingredient/birlik/me'yor | Birlik tekshiruvi, yangi versiya; eski buyurtma retsepti o'zgarmaydi |
| AD-05 Xomashyo | Nomi, asosiy birlik, minimal qoldiq, partiyalar | Kirim, harakatlar, sanash; qoldiqni izsiz tahrirlash yo'q |
| AD-06 Xarid/qabul | Yetkazib beruvchi, mahsulot, miqdor, narx, sana, partiya, muddat | Qabulni saqlash; alohida to'lov/qarz |
| AD-07 Kunlik sarf | Me'yoriy/haqiqiy sarf, farq, mahsulot, partiya taqsimoti | Tekshirish, «Sarfni hisobga olish», teskari yozuv bilan tuzatish |
| AD-08 Tayyor porsiyalar | Taom/partiya, tayyorlandi, sotildi, qoldi, isrof | Qoldiqni keyingi kunga o'tkazish yoki sababli isrof |
| AD-09 Xarajat | Kategoriya, maqsad, summa, oluvchi, sana, to'lov, ilova | «Saqlash» darhol hisobga oladi; superadmin kutish yo'q |
| AD-10 Inventarizatsiya | Mahsulot, hisobdagi/sanalgan qoldiq, vaqt, farq | Farqni sabab bilan hisobga olish; sarf bilan ikki marta ayrilmaydi |

AD-07 formasi me'yorni tavsiya sifatida ko'rsatadi, haqiqiy sarfni o'zi tasdiqlamaydi. Maydon bo'sh bo'lsa «kiritilmadi», 0 bo'lsa «sarf bo'lmagan» — ikkalasi farqli. Admin barcha ishlatilgan mahsulotlar kiritilganini tekshiradi. Eski sana/qoldiq ziddiyatlari aniq satr bilan ko'rsatiladi; tizim qoldiqni yashirin manfiy qilmaydi.

AD-09 da «To'langanmi?» maydoni: to'lanmagan / qisman / to'liq. To'langan qism uchun hisob tanlash majburiy. Bir amal ichida xarajat va to'lov yozilishi mumkin, ammo registrlar alohida. Ombor xaridi uchun xarid hujjatiga o'tish tavsiya qilinadi, bir xaridni yana xarajatga takror kiritishdan saqlaydi.

## 5. QR menyu

Telefon uchun: restoran nomi/logotipi → kategoriya tugmalari → qidiruv → rasmli taomlar va narx → taom tafsiloti. Tafsilotda porsiya, tavsif, mavjud bo'lsa allergenlar. Tugagan taom «Hozir mavjud emas» deb ko'rsatiladi yoki admin siyosatiga ko'ra yashiriladi.

Login, savat, «Buyurtma berish» va to'lov yo'q. QR ichida maxfiy token emas, barqaror menyu URL bo'ladi. Stol uchun QR ishlatilsa ham buyurtma yozish vakolati bermaydi. Rasm yuklanmasa nom/narx ishlaydi. Narx yangilanish vaqti, uzilishda eskirgan mavjudlik holati ko'rsatiladi. Mijoz internetisiz ochish hozir va'da qilinmaydi.

## 6. Bir xil interfeys qoidalari

Har sahifa uchun: yuklanmoqda, bo'sh, ma'lumot bor, xato, vakolat yo'q, aloqa yo'q holatlari. Saqlash xatosi formadagi qiymatlarni yo'qotmaydi. Server o'zgartirgan narx/versiya tafovuti ko'rsatiladi, kassirga sezilmay almashtirilmaydi.

Oddiy yangi yozuvlarda ortiqcha tasdiq oynasi yo'q. Pul qaytarish, kunlik sarfni qaytarish va arxivlashda aniq amal/summa ko'rsatilgan tasdiq ishlatiladi; bu egasidan alohida ruxsat olish oqimi emas. Vakolat avvaldan rolga beriladi.

Jadval filtrlari sahifaga qaytganda saqlanadi. Eksport amaldagi filtr va ko'rsatkich asosi bilan. CSV/Excel formulaga aylanuvchi matnlar xavfsiz chiqariladi. Pul summalarida birlik va minglik ajratkich, kiritishda aniq xato matni. Kompyuter POSida klaviatura bilan taom topish va to'lov oynasiga o'tish mumkin.

## 7. Maket qabul mezonlari

- Kassir 3 xil taom, 2 porsiya va izoh bilan tezkor hisobni yakunlay oladi.
- Bir stolda ketma-ket qo'shimcha buyurtmalar alohida chop topishirig'iga aylanadi.
- 100 000 hisobni karta/naqd bilan to'lab qaytimni aniq ko'radi.
- Printer ishlamasa kassir to'lovni qayta olmaydi, nusxa holatini topadi.
- Admin haqiqiy sarf kiritganda me'yordan farq va yangi qoldiqni ko'radi.
- Superadmin xarajat grafigidan maqsad, kiritgan xodim va hujjatga yetib boradi.
- Internet uzilishi bilan mahalliy server uzilishining xabarlari farqlanadi.
- QR menyuda buyurtma berish yo'li mavjud emas.
