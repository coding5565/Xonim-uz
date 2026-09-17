# Ish kuni, hisob holatlari va uzilishlar

Bu hujjat ekranlar orasidagi biznes jarayonini belgilaydi. «Tavsiya» bilan ko'rsatilgan siyosatlar hali egasi tomonidan alohida aniqlashtirilishi mumkin.

## 1. Ish kunining ketma-ketligi

1. Admin/kassir mahalliy tizimga kiradi. Server, printer, biznes kuni va backup holatini ko'radi.
2. Kassir smena ochadi. Boshlang'ich naqd sanaladi; bu savdo daromadi emas.
3. Admin yangi xomashyoni kirim qiladi va oldindan tayyorlangan taom porsiyalarini qayd etadi. Xomashyoning yakuniy sarfi kun oxirida yoziladi.
4. Kassir barcha buyurtmalarni kiritadi: tezkor savdo yoki stolga xizmat. Taom izohi va ofitsiant biriktirilishi shu yerda.
5. Oshxona topshirig'i chop etiladi. Qo'shimcha buyurtma va bekor qilish alohida topshiriq sifatida ketadi.
6. To'lov tezkor savdoda oldindan yoki stol xizmatida oxirida olinadi. To'lov, tayyorlash va chop holatlari mustaqil.
7. Admin kundalik pul xarajatlarini kiritadi; tegishli hisob darhol yangilanadi. Egasi tasdig'i kutilmaydi.
8. Kun oxirida admin haqiqiy xomashyo sarfi, qolgan/isrof tayyor porsiyalarni tekshiradi. Sarf bir marta hisobga olinadi.
9. Kassir naqdni sanab smenani yopadi. Ochiq hisoblar bo'lsa ularning davom etishi aniq qayd etiladi.
10. Kun yakuni hisobotida savdo, pul, sarf, isrof, qarz va farqlar jamlanadi. Tugallanmagan hujjat borida «to'liq yakunlanmagan» belgisi qoladi.

Smena yopilishi, kunlik sarfni hisobga olish va biznes kunini yakunlash bir-birini almashtirmaydi. Bir kunda bir nechta smena bo'lishi mumkin; kunlik sarf smenaga emas, biznes kuni/omborga tegishli.

## 2. Holatlar jadvali

| Obyekt | Holatlar | Muhim o'tish qoidasi |
| --- | --- | --- |
| Buyurtma | Qoralama → faol → bajarildi / bekor qilindi | Bajarilish to'lovdan alohida; yuborilgan satr bekori sababli |
| To'lov yig'indisi | To'lanmagan → qisman → to'langan → qisman/to'liq qaytarilgan | Faqat yakunlangan payment/refundlardan hisoblanadi |
| Alohida to'lov | Boshlangan → yakunlangan / muvaffaqiyatsiz / noaniq | Noaniq amal tekshirilmasdan yangi to'lov qilinmaydi |
| Oshxona topshirig'i | Navbatda → tayyorlanmoqda → tayyor → topshirildi | Chop holatidan alohida; kassir xabar asosida belgilaydi |
| Chop ishi | Navbatda → yuborildi → tasdiq / xato / noaniq | Printer imkoniyatiga qarab tasdiq; qog'oz chiqishi taxmin qilinmaydi |
| Kunlik sarf | Qoralama → hisobga olindi → teskari yozildi | Bir manba/versiya bir marta sarflaydi |
| Xarajat | Hisobga olindi → teskari yozildi | Saqlashda darhol hisobga olinadi; to'lov holati alohida |
| Smena | Ochiq → yopilgan | Yopilganga yangi to'lov yozilmaydi; tuzatish bog'langan hujjat bilan |
| Biznes kuni | Ochiq → yakunlashga tayyor → yopilgan | Ochiq/noaniq majburiyatlar tekshiriladi |

Buyurtmada umumiy «yopildi» belgisi xizmat va hisob-kitob yakunlangandan keyin hosil bo'ladi. Qayta hisob ochish/refund eski holat tarixini yo'qotmaydi. Muhim satr/holatlarda versiya tekshiruvi parallel tahrirni himoya qiladi.

## 3. Kunlik sarf misoli

Ertalab 50 kg guruch bor, kunda 10 kg kirim bo'ldi. Retsept bo'yicha kutilgan sarf 11 kg. Admin haqiqiy sarfni 12 kg deb kiritdi.

- Hisobga olishdan oldingi registr: 60 kg.
- Kutilgan qoldiq: 49 kg, taxmin sifatida.
- Haqiqiy sarf hujjatidan keyingi registr: 48 kg.
- Me'yordan farq: +1 kg; narx registri bo'yicha qiymati ham ko'rsatiladi.
- To'lov vaqtida yoki buyurtma satrida yana guruch ayrilmaydi.

Kun oxirida sanalgan qoldiq 47.5 kg chiqsa, 0.5 kg farq sababli inventarizatsiya tuzatishi bo'ladi. 12 kg sarf va 0.5 kg farq bir xil hodisa sifatida ikki marta kiritilmasligi admin ekranida ko'rinadi.

## 4. Qozon/partiya misoli

Partiyadan 100 porsiya tayyorlandi, 80 sotildi, 15 saqlashga qoldi, 5 isrof. Partiyaga ajratilgan haqiqiy xomashyo tannarxi 1 000 000 so'm bo'lsa, bir xil porsiya modeli bo'yicha 800 000 sotuv tannarxi, 150 000 tayyor mahsulot qiymati, 50 000 isrof chiqadi.

Qolgan mahsulotni keyingi kunga o'tkazishda partiya va yaroqlilik holati saqlanadi. Qayta tayyorlash/sotish xomashyoni ikkinchi marta ayirmaydi. Aralash retsept/porsiya bo'lsa taqsimot alohida koeffitsiyent bilan, audit qilinadigan tarzda. Bu misol faqat xomashyo tannarxi: ish haqi/kommunalni taomga taqsimlash siyosati hali belgilanmagan.

## 5. Internet va nosozliklar

| Vaziyat | Mahalliy kassa | Masofaviy egasi / QR | Tiklash |
| --- | --- | --- | --- |
| Internet bor | Odatdagi ish | Yangilanadigan nusxa | Outbox odatiy yuborish |
| Internet uzildi, LAN ishlaydi | Naqd savdo va mahalliy chop davom etadi | Egada oxirgi nusxa; mijoz interneti bilan QR ochiladi, menyu yangilanishi kechikadi | Aloqa qaytgach ketma-ket sinxronlash |
| Mahalliy server yo'q | Yangi moliyaviy amal yopiq; muvaffaqiyat xabari berilmaydi | Oxirgi nusxa | Serverni tiklash, tugamagan amal holatini tekshirish |
| Printer ishlamaydi | Buyurtma/to'lov saqlanadi | Chop ogohlantirishi | Noaniq holat tekshiriladi, nazoratli nusxa |
| To'lov javobi yo'qoldi | Noaniq/pending ko'rinadi | Yakunlanmaguncha to'langan deb jamlanmaydi | Provayder/amal ID orqali tekshirish |
| Elektr uzildi | UPS bo'lmasa to'xtaydi | Bulut oxirgi nusxani saqlaydi | DB va navbatni tiklash; apparat holatini tekshirish |

Sinxronlashda bitta event qayta kelishi normal, lekin pul registrida dublikat yozuv emas. Bulut nusxasi yo'qolsa mahalliy checkpoint/snapshot va hodisalar bilan qayta tiklanadi. Ko'p qurilma bir filialda bitta mahalliy serverga yozadi; internet qaytganda o'zaro «kimning balansi to'g'ri» nizosi yaratilmaydi.

Masofaviy superadmin mutatsiyalari taklifi: internet borida buyruq mahalliy serverga yo'naltiriladi va uning tasdig'idan keyin bajarildi deb ko'rsatiladi. Internet yo'qida «saqlandi» deb ko'rsatilmaydi; dastlab faqat o'qish. Bu moliya, menyu narxi va vakolatlarni ikki mustaqil nusxada tahrirlashdan saqlaydi. Masofaviy auth uchun alohida server sessiyasi; filial credentiallari bulutga ochiq ko'chirilmaydi. Qurilma sinxronlashida alohida cheklangan credential, bekor qilish va rotatsiya.

## 6. Dastlabki vakolatlar taklifi

| Amal | Egasi | Admin | Kassir |
| --- | --- | --- | --- |
| Buyurtma/to'lov/chek | Ha | Ha | Ha |
| Menyu/narx/retsept | Ha | Ha | Yo'q |
| Xarid/kunlik sarf/xarajat | Ha | Ha, kutishsiz | Yo'q, alohida berilsa mumkin |
| Barcha moliya va foyda | Ha | Faqat berilgan bo'lim | O'z smenasi |
| Refund/chegirma | Ha | Berilgan limitda | Faqat berilgan limitda |
| Xodim/admin vakolati | Ha | Yo'q | Yo'q |
| Oylik hisoblash/to'lash | Ha | Alohida ruxsat bilan | Yo'q |
| Davrni qayta ochish | Ha, sabab bilan | Yo'q | Yo'q |

Bu jadval biznes egasining keng vakolati bilan adminning kundalik erkin ishlashini uyg'unlashtiradi. Oddiy xarajat uchun hech qanday egasi tasdig'i kiritilmaydi. Refund/chegirma limitlari hozir raqam bilan belgilanmagan.

## 7. Keyingi reja natijalari

Ekranlar rejasi asosida avval SA-01 umumiy moliya, POS-02 kassa va AD-07 kunlik sarf maketlari ishlab chiqiladi. Ular grafikdan hujjatgacha o'tish, kassa tezligi va sarfning ikki marta ayrilmasligini tekshirishga xizmat qiladi. Keyin qolgan ekranlar va OpenAPI/ERD aniqlashtiriladi. Hozir implementatsiya boshlanmaydi.
