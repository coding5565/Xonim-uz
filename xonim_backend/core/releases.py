"""Versiya tarixi: har yangilanishda nima qo'shilgani.

BU FAYLNI QO'LDA YOZAMAN — kod bilan BITTA commitda. Sabab oddiy: bu
yagona joy bo'lib, uni odam o'qiydi. Commit sarlavhasidan avtomatik
yasash mumkin edi, lekin «feat: partners — food sent to schools» degan
qator restoran egasiga hech narsa aytmaydi.

Ro'yxat serverga kod bilan BIRGA boradi, shuning uchun u hech qachon
yolg'on gapira olmaydi: eski versiyaga qaytarilsa, o'sha eski
`releases.py` ham qaytadi va kelajakdagi yozuvlar o'z-o'zidan yo'qoladi.
Alohida tekshiruv kerak emas — fayl kodning o'zi bilan yuradi.

Uch til YOZUVNING SHAKLIDA talab qilinadi, `_()` orqali emas. Sabab:
izohlar har chiqishda qaytadan yoziladigan uzun matn, va ularni UI
yorliqlari bilan bitta lug'atga tiqish `core/translations.py` ni bir
yilda o'qib bo'lmaydigan holga keltirardi. Lekin rus tilida gaplashadigan
kassir ham nima o'zgarganini bilishi kerak, shuning uchun uch tilni test
majburlaydi — faqat boshqa joyda.

`kind` qiymatlari:
    yangi   — ilgari umuman bo'lmagan narsa
    tuzatish — ishlamayotgan narsa tuzatildi
    yaxshi  — bor narsa qulayroq yoki aniqroq bo'ldi

`roles` — kimga ko'rsatiladi. Kassirga moliya zanjiridagi o'zgarish
kerak emas, egasiga esa hammasi kerak.
"""

# Eng yangisi BIRINCHI turadi: ekranda ham shu tartibda ko'rinadi va
# «hozirgi versiya» aynan shu ro'yxatning birinchi yozuvi.
RELEASES = [
    {
        'version': '1.4',
        'released': '2026-09-22',
        'title': {
            'uz': 'Hamkorlar, Uzum bonusi va hodimlar ovqati',
            'ru': 'Партнёры, бонус Uzum и питание сотрудников',
            'en': 'Partners, the Uzum bonus and staff meals',
        },
        'changes': [
            {
                'kind': 'yangi',
                'roles': ['owner', 'cashier'],
                'uz': '«Hamkorlar» bo‘limi ochildi: maktab va universitetlarga taom '
                      'jo‘natiladi, kechqurun nechtasi sotilgani kiritiladi, so‘ng puli '
                      'olinadi. Har bir hamkorning o‘z sahifasi bor.',
                'ru': 'Появился раздел «Партнёры»: еда отправляется в школы и '
                      'университеты, вечером вносится, сколько продано, затем '
                      'забираются деньги. У каждого партнёра своя страница.',
                'en': 'A “Partners” section: food goes to schools and universities, in '
                      'the evening you enter how many were sold, then you take the '
                      'money. Every partner has its own page.',
            },
            {
                'kind': 'yangi',
                'roles': ['owner'],
                'uz': 'Har bir hamkorga shartnoma narxi belgilanadi. Narx jo‘natma '
                      'qatoriga muzlatiladi — ertaga narxni o‘zgartirsangiz, kecha '
                      'jo‘natilgan taomning hisobi o‘zgarmaydi.',
                'ru': 'Для каждого партнёра задаётся договорная цена. Цена '
                      'замораживается в строке отправки — если завтра изменить цену, '
                      'счёт за вчерашнюю отправку не поменяется.',
                'en': 'Each partner gets a contract price. The price is frozen onto the '
                      'delivery line — changing it tomorrow never rewrites yesterday’s '
                      'delivery.',
            },
            {
                'kind': 'yangi',
                'roles': ['owner', 'cashier'],
                'uz': 'Uzum aksiyasi: buyurtmada «Bozor honim» bo‘lsa, mijoz nechta '
                      'olganidan qat’i nazar ustiga bittasi tekin ketadi — 1 ta olsa '
                      '2 ta, 10 ta olsa 11 ta. «Bonuslar» bo‘limida nechta porsiya '
                      'tekin ketgani va u qanchaga tushgani ko‘rinadi.',
                'ru': 'Акция Uzum: если в заказе есть «Bozor honim», сверху одна уходит '
                      'бесплатно — сколько бы клиент ни взял: взял 1 — уйдёт 2, взял '
                      '10 — уйдёт 11. В разделе «Бонусы» видно, сколько порций ушло '
                      'бесплатно и во сколько это обошлось.',
                'en': 'The Uzum promotion: if the order contains a “Bozor honim”, one '
                      'more goes out free no matter how many the guest took — 1 becomes '
                      '2, 10 becomes 11. The “Bonuses” section shows how many portions '
                      'went out free and what they cost.',
            },
            {
                'kind': 'yangi',
                'roles': ['owner', 'cashier'],
                'uz': '«Hodimlar ovqati» bo‘limi: taomni tanlab, nechta va kim yeganini '
                      'yozib qo‘yasiz. Bu hech kimning oyligiga ta’sir qilmaydi — faqat '
                      'oyiga qancha ketayotganini bilish uchun.',
                'ru': 'Раздел «Питание сотрудников»: выбираете блюдо и записываете, '
                      'сколько и кто съел. На зарплату это не влияет — только чтобы '
                      'знать, сколько уходит за месяц.',
                'en': 'A “Staff meals” section: pick a dish and record how many and who '
                      'ate them. It never touches anyone’s pay — it is only there so you '
                      'know how much goes out in a month.',
            },
            {
                'kind': 'yangi',
                'roles': ['owner', 'cashier'],
                'uz': 'Ombordagi mahsulotning nomini tahrirlash va uni ro‘yxatdan '
                      'chiqarish mumkin bo‘ldi. Kirim-chiqim tarixi bor mahsulot '
                      'o‘chirilmaydi — ro‘yxatdan olinadi, eski hisobotlarda nomi '
                      'joyida qoladi.',
                'ru': 'Теперь можно изменить название продукта на складе и снять его с '
                      'учёта. Продукт с историей прихода-расхода не удаляется — он '
                      'снимается с учёта, а в старых отчётах его имя остаётся.',
                'en': 'A warehouse product can now be renamed and taken off the list. A '
                      'product with a movement history is never deleted — it is taken '
                      'off the list and its name stays in the old reports.',
            },
            {
                'kind': 'yaxshi',
                'roles': ['owner'],
                'uz': 'Moliyada hamkorlar tushumi va tannarxi alohida qatorlar bo‘lib '
                      'turadi, kassa savdosiga aralashmaydi. «Hamkorlar» kartasida '
                      'jo‘natilgan pul, hisoblangan qarz va qo‘lga tekkan pul yonma-yon '
                      'ko‘rinadi.',
                'ru': 'В финансах выручка и себестоимость партнёров — отдельные строки, '
                      'они не смешиваются с продажами кассы. На карточке «Партнёры» '
                      'рядом видны отправленная сумма, начисленный долг и полученные '
                      'деньги.',
                'en': 'In finance, partner revenue and cost are their own lines and never '
                      'mix with till sales. The “Partners” card puts the value sent, the '
                      'debt accrued and the money received side by side.',
            },
            {
                'kind': 'yaxshi',
                'roles': ['owner', 'cashier'],
                'uz': 'Kun yakunida hisobot bermagan hamkor eslatiladi va ulardan '
                      'olingan naqd kutilgan naqdga qo‘shiladi — endi kassada sababsiz '
                      'farq chiqmaydi.',
                'ru': 'В итоге дня напоминается о партнёре, который не отчитался, а '
                      'полученные от них наличные добавляются к ожидаемой сумме — '
                      'беспричинной разницы в кассе больше не будет.',
                'en': 'The end of day now names the partner that has not reported, and '
                      'cash taken from partners adds to the expected cash — no more '
                      'unexplained difference in the drawer.',
            },
        ],
    },
    {
        'version': '1.3',
        'released': '2026-09-22',
        'title': {
            'uz': 'Xodimlar, kunlik haq va ofitsiant xizmat haqi',
            'ru': 'Сотрудники, дневная оплата и сервисный сбор официанта',
            'en': 'Employees, the daily wage and the waiter service charge',
        },
        'changes': [
            {
                'kind': 'yangi',
                'roles': ['owner', 'cashier'],
                'uz': 'Xodim endi tizimga kirish emas, odam: loginsiz ham yaratiladi, '
                      'lavozimi erkin yoziladi va kunlik haqi belgilanadi. Davomat har '
                      'kuni belgilanadi, haq balansga yig‘iladi va istalgan payt '
                      'istalgan summa berilishi mumkin.',
                'ru': 'Сотрудник теперь человек, а не логин: его можно создать без '
                      'входа в систему, должность пишется свободно и задаётся дневная '
                      'оплата. Посещаемость отмечается ежедневно, оплата копится на '
                      'балансе, и выдать можно любую сумму в любой момент.',
                'en': 'An employee is a person now, not a login: they can be created '
                      'without one, the position is free text and a daily wage is set. '
                      'Attendance is marked daily, pay accrues onto a balance, and any '
                      'amount can be paid out at any time.',
            },
            {
                'kind': 'yangi',
                'roles': ['owner', 'cashier'],
                'uz': 'Ofitsiant xizmat haqi hisob USTIGA qo‘shiladi: 100 000 so‘mlik '
                      'savdoda 10% bo‘lsa, mijoz 110 000 to‘laydi va 10 000 ofitsiant '
                      'hisobiga o‘tadi. Foizni superadmin belgilaydi, ofitsiant esa '
                      'buyurtma berilayotganda ro‘yxatdan tanlanadi.',
                'ru': 'Сервисный сбор официанта добавляется СВЕРХУ счёта: при продаже '
                      'на 100 000 сум и ставке 10% клиент платит 110 000, а 10 000 '
                      'уходит официанту. Процент задаёт суперадмин, а официант '
                      'выбирается из списка при оформлении заказа.',
                'en': 'The waiter service charge is added ON TOP of the bill: on a '
                      '100,000 so‘m sale at 10% the guest pays 110,000 and 10,000 goes '
                      'to the waiter. The superadmin sets the percentage and the waiter '
                      'is picked from a list when the order is taken.',
            },
            {
                'kind': 'yangi',
                'roles': ['owner'],
                'uz': 'Uzum va Yandex ushlab qoladigan foiz superadmin qo‘lida. Foiz '
                      'sotuv paytida muzlatiladi — shartnoma o‘zgarsa ham o‘tgan oyning '
                      'hisoboti qayta yozilmaydi.',
                'ru': 'Процент, который удерживают Uzum и Yandex, теперь в руках '
                      'суперадмина. Процент замораживается в момент продажи — при смене '
                      'договора отчёт за прошлый месяц не перепишется.',
                'en': 'The cut Uzum and Yandex withhold is now the superadmin’s to set. '
                      'It is frozen at the moment of sale, so a new contract never '
                      'rewrites last month’s report.',
            },
        ],
    },
    {
        'version': '1.2',
        'released': '2026-09-22',
        'title': {
            'uz': 'Tayyor taomlar, terminal va masalliq xarajati',
            'ru': 'Готовые блюда, терминал и расход на продукты',
            'en': 'Prepared dishes, the terminal and produce spending',
        },
        'changes': [
            {
                'kind': 'yaxshi',
                'roles': ['owner', 'cashier'],
                'uz': 'Tayyor taomlar qoldig‘i endi kundan kunga o‘tadi — kechqurun '
                      'ortib qolgani ertasiga nolga aylanmaydi. Suv va tayyor keladigan '
                      'mahsulotlar oshxonada pishiriladigan taomlardan alohida guruhda '
                      'turadi va sotuvni hech qachon to‘xtatmaydi.',
                'ru': 'Остаток готовых блюд теперь переходит со дня на день — то, что '
                      'осталось вечером, не обнуляется наутро. Вода и готовые товары '
                      'стоят отдельной группой от блюд, которые готовятся на кухне, и '
                      'никогда не останавливают продажу.',
                'en': 'Prepared portions now carry over from day to day — what is left in '
                      'the evening is not reset to zero overnight. Water and ready-made '
                      'goods sit in their own group, apart from the dishes the kitchen '
                      'cooks, and they never stop a sale.',
            },
            {
                'kind': 'yangi',
                'roles': ['owner', 'cashier'],
                'uz': 'Terminal alohida to‘lov usuli bo‘ldi. Moliyada naqd, karta, '
                      'Click, terminal, Uzum va Yandex har biri alohida ko‘rinadi va '
                      'ustiga bosilsa faqat o‘sha usuldagi to‘lovlar chiqadi.',
                'ru': 'Терминал стал отдельным способом оплаты. В финансах наличные, '
                      'карта, Click, терминал, Uzum и Yandex видны по отдельности, и по '
                      'клику показываются только платежи этим способом.',
                'en': 'The terminal is its own payment method now. In finance, cash, '
                      'card, Click, terminal, Uzum and Yandex each show separately, and '
                      'clicking one shows only the payments made that way.',
            },
            {
                'kind': 'yangi',
                'roles': ['owner'],
                'uz': '«Masalliq» xarajat kategoriyasi qo‘shildi. Agar bitta xarid ham '
                      'xarajatga, ham ombor kirimiga yozilgan bo‘lsa, moliya buni sezib '
                      'ogohlantiradi — pul ikki marta sanalib ketmaydi.',
                'ru': 'Добавлена категория расходов «Продукты». Если одна и та же '
                      'покупка записана и в расход, и в приход склада, финансы это '
                      'заметят и предупредят — деньги не посчитаются дважды.',
                'en': 'A “Produce” expense category. If one purchase was recorded both '
                      'as an expense and as a warehouse receipt, finance notices and '
                      'warns you — the money is never counted twice.',
            },
        ],
    },
    {
        'version': '1.1',
        'released': '2026-09-21',
        'title': {
            'uz': 'Zaxira nusxa va restoran ichidagi chek printeri',
            'ru': 'Резервная копия и чековый принтер внутри ресторана',
            'en': 'Backups and the receipt printer inside the restaurant',
        },
        'changes': [
            {
                'kind': 'yangi',
                'roles': ['owner'],
                'uz': 'Baza va rasmlar Telegramga zaxiraga yuboriladi — jadval bo‘yicha '
                      'o‘zi, yoki `/backup` buyrug‘i bilan istalgan payt. Bir nechta '
                      'qabul qiluvchiga birdan boradi.',
                'ru': 'База и фотографии отправляются в резервную копию в Telegram — по '
                      'расписанию автоматически или командой `/backup` в любой момент. '
                      'Отправляется сразу нескольким получателям.',
                'en': 'The database and the photos are backed up to Telegram — on a '
                      'schedule, or on demand with `/backup`. It reaches several '
                      'recipients at once.',
            },
            {
                'kind': 'tuzatish',
                'roles': ['owner', 'cashier'],
                'uz': 'Chek endi restoran ichidagi kompyuterda turgan kichik dastur '
                      'orqali chiqadi. Ilgari buyruq bulutdagi serverdan ketardi va u '
                      'restorandagi USB printerga umuman yeta olmasdi.',
                'ru': 'Чек теперь печатается через небольшую программу на компьютере в '
                      'ресторане. Раньше команда шла с облачного сервера, который '
                      'физически не мог достучаться до USB-принтера в зале.',
                'en': 'Receipts now print through a small program on a computer inside '
                      'the restaurant. The command used to come from the cloud server, '
                      'which could never reach a USB printer in the dining room.',
            },
        ],
    },
]
