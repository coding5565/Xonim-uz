# Superadmin moliya markazi

Holat: batafsil reja, implementatsiya emas. Maqsad — egasi pul qayerdan kelgani, qayerga ketgani, nima sabab o'zgarayotganini va qaysi yozuv bunga asos bo'lganini ko'ra olishi.

## 1. Panel tuzilishi

Doimiy yuqori filtr: sana, biznes kuni, oldingi davr bilan taqqoslash, pul birligi. Hozir bitta restoran; filial tanlash va filiallar taqqoslanishi ikkinchi filial qo'shilgach ko'rsatiladi. Ma'lumotlar boshidan filialga bog'lanadi. Tez oraliqlar: bugun, kecha, hafta, oy, yil, ixtiyoriy. Har ekran ma'lumotning yangilangan vaqtini va faol filtrlarni ko'rsatadi.

Ichki bo'limlar:

1. Umumiy holat.
2. Sotuv va tushumlar.
3. Xarajatlar va ularning maqsadi.
4. Pul oqimi va hisoblar.
5. Foyda, tannarx va marja.
6. Yetkazib beruvchi qarzi va olinadigan to'lovlar.
7. Ombor qiymati, sarf va isrof.
8. Xodimlar, oylik va xizmat haqi.
9. Reja–amal va o'sish/kamayish.
10. Audit, tasdiqlashlar va hisob sifati.

## 2. Birinchi ekrandagi KPI kartalar

| Ko'rsatkich | Hisoblash asosi | Ochilganda |
| --- | --- | --- |
| Sof savdo | Tan olingan taom savdosi − chegirma − qaytarilgan savdo; soliq/xizmat alohida | Chek va satrlar |
| Qabul qilingan to'lov | Muvaffaqiyatli payment summasi; refund alohida ko'rsatiladi | To'lovlar, usul va smena |
| Sof pul tushumi | Tashqi kirim − tashqi chiqim; ichki transferlar chiqariladi | Pul harakatlari |
| Xarajat | Davrda tan olingan operatsion xarajat, tannarxdan alohida | Kategoriya va hujjat |
| Yalpi foyda | Sof savdo − sotilgan mahsulot tannarxi | Taom/kategoriya kesimi |
| Operatsion natija | Yalpi foyda + tegishli boshqa daromad − davr xarajatlari | Natijani shakllantirgan yozuvlar |
| Joriy pul qoldig'i | Davr boshidagi qoldiq + hisob bo'yicha kirim − chiqim | Naqd/bank/terminal hisob-kitobi |
| To'lanadigan qarz | Tasdiqlangan majburiyat − ajratilgan to'lov/kredit | Yetkazib beruvchi yoki xodim |
| Ombor qiymati | Qolgan miqdorlarning registr bo'yicha qiymati | Mahsulot/partiya |
| O'rtacha chek | Yakunlangan savdo summasi / tegishli cheklar soni | Cheklar ro'yxati |

Har kartada summa, taqqoslashdagi mutlaq farq, foiz va kichik trend. To'lov, savdo va foyda bir-biriga almashtirilmaydi. Avans tushumi darhol savdo emas; egasi kiritgan kapital savdo daromadi emas. Soliq majburiyati operatsion foyda sifatida ko'rsatilmaydi.

Sotuvni tan olish siyosati: topshirilgan mahsulot yoki yakunlangan xizmat asosida; to'lov vaqti alohida. Unpaid/open order summasi alohida KPI. Qozonda tayyorlangan, ammo sotilmagan ovqat ombor aktivi bo'lib turadi. Bu qoidalar hisobchi bilan kelishiladi.

## 3. Grafiklar katalogi

| Grafik | Ko'rinish | Javob beradigan savol |
| --- | --- | --- |
| Sotuv dinamikasi | Joriy/oldingi davr chiziqlari | Savdo qachon o'sdi yoki tushdi? |
| Pul kirimi va chiqimi | Yonma-yon ustun; qoldiq alohida chiziq/panel | Qaysi kun pul kamaydi? |
| Natija tarkibi | Waterfall | Savdodan foydagacha qaysi xarajatlar ta'sir qildi? |
| Xarajat kategoriyalari | Saralangan gorizontal ustun | Eng ko'p pul nimaga sarflandi? |
| Kategoriya xarajati vaqtda | Ustma-ust ustun | Xarajat tarkibi qanday o'zgardi? |
| Reja va amaldagi xarajat | Yonma-yon ustun va farq | Qaysi kategoriya budjetdan chiqdi? |
| Taom savdosi va marjasi | Jadval + ustun, ikkita aniq o'lchov | Ko'p sotilgan taom foydali hammi? |
| Soat/hafta kuni faolligi | Issiqlik xaritasi | Qachon mijoz oqimi yuqori? |
| Naqd/karta ulushi | 100% ustun va aniq summalar | Pul qaysi usulda tushdi? |
| Filiallar taqqoslanishi | Ustun va KPI jadvali | Qaysi filial qanday natija bermoqda? |
| Qarz muddati | 0–7, 8–30, 31–60, 60+ kun ustunlari | Qaysi majburiyat kechikmoqda? |
| Isrof sabablari | Mahsulot/sabab bo'yicha ustun | Qayerda mahsulot yo'qotyapmiz? |
| Oylik tarkibi | Stavka/bonus/ulush/ushlanma jadvali | Kimga nima uchun qancha hisoblandi? |
| Ombor sarfi | Me'yoriy va haqiqiy sarf ustunlari | Retseptdan ortiq sarf bormi? |

Ko'p kategoriyali doiraviy grafik ishlatilmaydi. Grafik yonida sonli jadval, birlik, legenda va izoh bo'ladi. Rang yagona axborot manbai emas. Manfiy natijalar yashirilmaydi. Daromad va xarajat bir xil rang ma'nosiga ega bo'lmaydi: xarajat oshishi avtomatik yaxshi deb yashil belgilanmaydi.

## 4. «Chiqim nimaga ishlatildi?» zanjiri

Grafikdagi kategoriya → kichik kategoriya → operatsiyalar → xarajat kartasi → to'lov va kiritgan xodim → biriktirilgan hujjat.

Xarajat kartasi maydonlari:

- Filial, xarajat sanasi, hisobga olish davri va to'lov sanasi.
- Kategoriya/kichik kategoriya, majburiy maqsad yoki izoh.
- Yetkazib beruvchi/oluvchi, mas'ul xodim, kiritgan shaxs va kiritilgan vaqt.
- Miqdor, birlik narxi, jami, kerak bo'lsa soliq ajratmasi.
- Naqd/bank hisobi, to'langan summa, qolgan qarz.
- Chek/faktura/rasm, xarid yoki ta'mirlash kabi manba hujjati.
- Hujjat holati: hisobga olindi/teskari yozuv bilan bekor qilindi. To'lov holati alohida: to'lanmagan/qisman to'landi/to'landi. Superadmin tasdig'ini kutish bosqichi yo'q.
- O'zgarish tarixi, teskari yozuv va uning sababi.

Xaridga bog'langan to'lov uchun yana alohida «kundalik xarajat» yaratish o'rniga manba bog'lanadi. Bir bank/kassa operatsiyasi ikki marta import/post qilinmasligi uchun noyob tashqi identifikator yoki nazoratli moslashtirish ishlatiladi.

## 5. O'sish va kamayish qoidalari

Mutlaq farq = joriy − oldingi. Oldingi qiymat musbat bo'lsa foiz = farq / oldingi × 100. Oldingi qiymat nol bo'lsa foiz o'rniga «yangi»/«taqqoslash bazasi yo'q». Ikkalasi nol bo'lsa «o'zgarish yo'q». Oldingi natija manfiy bo'lsa odatiy foizli o'sish o'rniga mutlaq farq va «zarar kamaydi/foydaga o'tdi» ko'rsatiladi.

Bugun soat 14:00 dagi natija kechagi butun kun bilan sukut bo'yicha solishtirilmaydi: kechagi 14:00 gacha bo'lgan bir xil vaqt oralig'i olinadi. Oy boshidan joriy kungacha natija o'tgan oyning mos davri bilan yoki foydalanuvchi tanlagan teng uzunlikdagi davr bilan solishtiriladi. 28/30/31 kunlik farq va mavjud bo'lmagan sanalar aniq yorliq bilan ko'rsatiladi.

Taklif etilgan savdo tahlili: cheklar soni, o'rtacha chek, taom miqdori va narx o'zgarishi alohida ko'rsatiladi. Sabab tasdiqlanmagan bo'lsa «savdo pasayishiga shu sabab bo'ldi» degan xulosa chiqarilmaydi. Izoh kuzatilgan fakt bilan chegaralanadi.

## 6. Hisobot ishonchliligi

Admin saqlagan va server tekshiruvidan o'tgan xarajat darhol hisobga olinadi. Boshqa hujjat turlaridagi hali hisobga olinmagan qoralamalar rasmiy jami ichiga kirmaydi. Bekor qilish va refund asl manbaga bog'lanadi. Kech kiritilgan hujjatda haqiqiy operatsiya sanasi va tizimga yozilgan sana alohida saqlanadi.

Yopilgan davr orqaga yashirin o'zgartirilmaydi: maxsus ruxsat bilan qayta ochish yoki joriy davrda tuzatish. Yopilgan hisobot versiyasi saqlanadi. Qayta hisoblangan ochiq davrda yangilanish belgisi chiqadi.

Bir ko'rsatkich uchun umumiy query/service ishlatiladi: karta, grafik, jadval va eksport bitta semantik manbaga tayanadi. Puldagi farq 0 bo'lishi shart; yaxlitlash farqi alohida yozuv bilan izohlanadi. Filiallar yig'indisida o'zaro transferlar chiqariladi. Turli valyutalar kurs siyosatisiz qo'shilmaydi.

Ma'lumot sifati belgilariga quyidagilar kiradi: tannarxi yo'q taom, tasdiqlanmagan kirim, yopilmagan smena, qoldiq nomuvofiqligi, hujjatsiz xarajat, noaniq terminal to'lovi. Tannarx yetishmasa aniq foyda chiqarish o'rniga «to'liq emas» ko'rsatiladi.

Yangilanish maqsadi: kassa operatsiyasi yozilgach tegishli balans darhol serverdan; umumiy dashboard 30 soniyagacha yangilanish bilan. Oxirgi muvaffaqiyatli yangilanish va eskirgan ma'lumot holati ko'rinadi. Bu maqsadlar yuklama sinovida tekshiriladi. Internet uzilganda mahalliy panel mahalliy ma'lumotni, masofaviy panel oxirgi sinxronlangan nusxani ko'rsatadi.

Kunlik haqiqiy sarf kiritilguncha tannarx/foyda retsept asosidagi «taxminiy» qiymat. Haqiqiy sarf va sotilgan/qolgan/isrof porsiyalar taqsimoti kiritilgach yangilanadi. Registrdagi xomashyo qoldig'i, kutilgan qoldiq va sanalgan qoldiq ajratiladi. Ombor sarfi yangi pul chiqimi yaratmaydi: xaridda to'langan pul qayta ayrilmaydi.

## 7. Nazorat va ogohlantirishlar

Egasi limit belgilaydi: kategoriya budjeti, katta xarajat, ortiqcha chegirma, refundlar, smena farqi, isrof, past marja, kechikkan qarz va minimal qoldiq. Ogohlantirishda asosiy raqam, limit, davr, sabab hujjati va bajarilishi kerak bo'lgan amal bo'ladi. Bir xil hodisa takroriy bildirishnoma yog'dirmaydi.

Xarajat uchun alohida tasdiqlash bosqichi yo'q: admin kiritadi, tizim darhol hisobga oladi, superadmin nazorat qiladi. Budjet/katta xarajat ogohlantirishi yozuvni tasdiq kutishga o'tkazmaydi. Xatolar sababli teskari yozuv orqali tuzatiladi va auditda saqlanadi. Muammo bo'yicha mas'ul va hal etilgan vaqt belgilanadi.

Ofitsiant xizmat haqi va ulush grafiklarining formulasi keyin kelishiladi; hozir bu bo'lim rejalashtirilgan, foizlari aniqlanmagan. Taxminiy qiymatlar haqiqiy daromad yoki oylik hisobiga kiritilmaydi.

## 8. Qabul ssenariysi

Nazorat to'plami: 1 mln so'mlik xomashyo xaridi/to'lovi, 300 ming tannarxli 600 ming sof savdo/to'lov, 100 ming davr xarajati/to'lovi. Soliq, xizmat va boshlang'ich qoldiqsiz misol.

Kutilgan natija: sof savdo 600 ming; yalpi foyda 300 ming; operatsion natija 200 ming; ombor 700 ming; sof pul oqimi −500 ming. Pul yetarliligi uchun boshlang'ich balans alohida beriladi. Grafik, karta, drill-down va eksport shu qiymatlarga teng bo'lishi kerak.

Qo'shimcha ssenariylar: qisman qarzli xarid, oldindan mijoz to'lovi, xizmat haqi ulushi, manfiy foyda, qisman refund, filial transferi, oylik avansi, oy chegarasidagi smena va o'tgan davr tuzatishi. «Ideal ishlaydi» mezoni — shu holatlarning tekshiriladigan, takrorlanuvchi natijasi.
