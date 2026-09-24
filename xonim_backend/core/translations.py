"""Server xabarlarining ruscha va inglizcha tarjimalari.

Kalit — o'zbekcha matnning o'zi. Yangi xabar qo'shilsa, tarjimasiz ham
ishlayveradi: o'zbekchasi ko'rinadi.
"""

RU = {
    'Bir taomni faqat bir marta kiriting.': 'Вносите каждое блюдо только один раз.',
    'Bir martada ko‘pi bilan 100 ta taom.': 'За раз не более 100 блюд.',
    'Ayrim taomlar topilmadi.': 'Некоторые блюда не найдены.',
    'Ombor harakatlari tarixi faqat superadminga ochiq.':
        'История движений по складу доступна только суперадмину.',
    '{name} — bugun tayyorlanmagan': '{name} — сегодня не приготовлено',
    '{name} — {count} ta qoldi': '{name} — осталось {count}',
    '{name} — qoldiq {count} ta, undan ko‘pini hisobdan chiqarib bo‘lmaydi.':
        '{name} — в остатке {count}, списать больше нельзя.',
    'Bu taomlar tayyor emas: {dishes}. «Tayyor taomlar» bo‘limida bugun nechta tayyorlanganini kiriting.':
        'Эти блюда не готовы: {dishes}. Укажите в разделе «Готовые блюда», сколько приготовлено сегодня.',
    'Ofitsiant topilmadi.': 'Официант не найден.',
    'Bu ismli ofitsiant allaqachon bor.': 'Официант с таким именем уже есть.',
    'Nom bo‘sh bo‘lishi mumkin emas.': 'Название не может быть пустым.',
    'Suhbat topilmadi.':
        'Диалог не найден.',
    'Suhbat o‘chirildi.':
        'Диалог удалён.',
    'AI kaliti hali ulanmagan. Bugun, kecha yoki hafta bo‘yicha tezkor savollardan birini bosing, yoki OpenAI kalitini ulang.':
        'Ключ AI ещё не подключён. Нажмите один из быстрых вопросов или подключите ключ OpenAI.',
    # --- Umumiy xatolar ---
    'Buyurtma topilmadi.': 'Заказ не найден.',
    'Mahsulot topilmadi.': 'Продукт не найден.',
    'Stol topilmadi.': 'Стол не найден.',
    'Bu ismli xodim allaqachon bor.':
        'Сотрудник с таким именем уже есть.',
    'Bu xodimda tizim hisobi yo‘q.':
        'У этого сотрудника нет учётной записи.',
    'Login berilsa parol ham kerak.':
        'Если указан логин, нужен и пароль.',
    'Login berilsa rol ham tanlanadi.':
        'Если указан логин, нужно выбрать и роль.',
    'Avval nechtasi sotilganini kiriting — shundan keyin pul yoziladi.':
        'Сначала внесите, сколько продано — только после этого записывается оплата.',
    'Bekor qilingan jo‘natma bo‘yicha hisobot qabul qilinmaydi.':
        'По отменённой отправке отчёт не принимается.',
    'Bekor qilingan jo‘natma bo‘yicha pul qabul qilinmaydi.':
        'По отменённой отправке деньги не принимаются.',
    'Bir qatorni faqat bir marta kiriting.':
        'Вносите каждую строку только один раз.',
    'Bu amal faqat superadminga ochiq.':
        'Это действие доступно только суперадмину.',
    'Bu hamkor faolsizlantirilgan — unga taom jo‘natilmaydi.':
        'Этот партнёр деактивирован — отправлять ему еду нельзя.',
    'Bu hamkorda yopilmagan jo‘natma bor. Avval hisobni yoping.':
        'У этого партнёра есть незакрытая отправка. Сначала закройте счёт.',
    'Bu jo‘natma allaqachon bekor qilingan.':
        'Эта отправка уже отменена.',
    'Bu jo‘natma uchun allaqachon {paid} so‘m olingan — hisobotni undan pastga tushirib bo‘lmaydi. Avval to‘lovni bekor qiling.':
        'По этой отправке уже получено {paid} сум — отчёт ниже этой суммы не опустить. Сначала отмените оплату.',
    'Bu narx tannarxdan past: «{name}» har porsiyada {amount} so‘m zarar.':
        'Эта цена ниже себестоимости: «{name}» — {amount} сум убытка на порцию.',
    'Bu nomli hamkor allaqachon bor.':
        'Партнёр с таким названием уже есть.',
    'Bu qator boshqa jo‘natmaga tegishli.':
        'Эта строка относится к другой отправке.',
    'Bu to‘lov allaqachon bekor qilingan.':
        'Эта оплата уже отменена.',
    'Bugun bu hamkorga allaqachon jo‘natilgan. Ikkinchi mashina bo‘lsa davom eting.':
        'Сегодня этому партнёру уже отправляли. Если это вторая машина — продолжайте.',
    'Hamkor ro‘yxatdan olindi.':
        'Партнёр снят с учёта.',
    'Hamkor topilmadi.':
        'Партнёр не найден.',
    'Har bir qator uchun nechta sotilgani kiritilsin.':
        'Укажите, сколько продано, по каждой строке.',
    'Hisobot berilgan jo‘natmani bekor qilib bo‘lmaydi. Hisobotni qaytadan kiriting.':
        'Отправку с отчётом отменить нельзя. Внесите отчёт заново.',
    'Jo‘natma topilmadi.':
        'Отправка не найдена.',
    'Qolgan qarz {amount} so‘m — undan ko‘pini qabul qilib bo‘lmaydi.':
        'Остаток долга {amount} сум — больше принять нельзя.',
    'To‘lov topilmadi.':
        'Оплата не найдена.',
    '{date} kuni allaqachon yopilgan — o‘sha kundagi to‘lovni bekor qilib bo‘lmaydi.':
        'День {date} уже закрыт — оплату за тот день отменить нельзя.',
    '{date} kuni allaqachon yopilgan — o‘sha kunga pul kiritib bo‘lmaydi.':
        'День {date} уже закрыт — вносить деньги за тот день нельзя.',
    '«{name}» narxi menyu narxidan yuqori — tekshiring.':
        'Цена «{name}» выше меню — проверьте.',
    '«{name}» uchun hamkor narxi belgilanmagan — shu sababli jo‘natib bo‘lmaydi. Narxni shartnoma bo‘yicha superadmin kiritadi.':
        'Для «{name}» не задана цена партнёра — отправить нельзя. Цену по договору вносит суперадмин.',
    '«{name}» — {sent} ta jo‘natilgan, {sold} ta sotilgan deb bo‘lmaydi.':
        '«{name}» — отправлено {sent}, продано {sold} быть не может.',
    'Arxivlangan taomga bonus belgilab bo‘lmaydi.':
        'Нельзя назначить бонус на архивное блюдо.',
    'Bonus qoidasi topilmadi.':
        'Правило бонуса не найдено.',
    'Faqat bugungi yozuvni o‘chirish mumkin.':
        'Удалить можно только сегодняшнюю запись.',
    'Kelajakdagi sana mumkin emas.':
        'Будущая дата недопустима.',
    'Qoida o‘chirildi.':
        'Правило удалено.',
    'Saqlandi. Yangi qoida shu paytdan keyingi buyurtmalarga qo‘llanadi.':
        'Сохранено. Новое правило применяется к заказам с этого момента.',
    'Taom topilmadi.':
        'Блюдо не найдено.',
    'Yozuv o‘chirildi va masalliq omborga qaytarildi.':
        'Запись удалена, продукты вернулись на склад.',
    'Yozuv topilmadi.':
        'Запись не найдена.',
    'Bu mahsulotda kirim-chiqim tarixi bor — o‘lchov birligini o‘zgartirib bo‘lmaydi. Yangi nom bilan yangi mahsulot oching.':
        'По этому продукту есть история прихода и расхода — единицу измерения изменить нельзя. Заведите новый продукт с другим названием.',
    '«{name}» {recipes} retseptida ishlatilyapti — avval retseptdan olib tashlang.':
        '«{name}» используется в рецепте {recipes} — сначала уберите его оттуда.',
    'Bu usul bilan bo‘lib to‘lab bo‘lmaydi.':
        'Этим способом разделить оплату нельзя.',
    'Ikkinchi to‘lov usulini tanlang.':
        'Выберите второй способ оплаты.',
    'Ikkinchi usul birinchisidan boshqa bo‘lishi kerak.':
        'Второй способ должен отличаться от первого.',
    'Ikkinchi usuldagi summa hisobdan kichik bo‘lishi kerak. Hammasi shu usul bilan bo‘lsa, uni asosiy qilib tanlang.':
        'Сумма по второму способу должна быть меньше счёта. Если всё оплачено этим способом, выберите его основным.',
    'Ikkinchi usuldagi summa noldan katta bo‘lsin.':
        'Сумма по второму способу должна быть больше нуля.',
    'Yetkazib berish buyurtmasi bo‘lib to‘lanmaydi — pul platformadan keladi.':
        'Заказ доставки нельзя оплатить частями — деньги приходят от платформы.',
    'Xodim topilmadi.': 'Сотрудник не найден.',
    'Kategoriya topilmadi.': 'Категория не найдена.',
    'Bu qator hisobda yo‘q.': 'Этой строки нет в счёте.',
    'Qator olib tashlansa chegirma qolgan summadan katta bo‘lib qoladi. Avval chegirmani o‘zgartiring.':
        'Если убрать строку, скидка станет больше остатка счёта. Сначала измените скидку.',
    'Amal holati o‘zgargan. Ma’lumotni yangilang.':
        'Состояние операции изменилось. Обновите данные.',
    'Amal boshqa so‘rov bilan to‘qnashdi. Shu amalni qayta tekshiring.':
        'Операция столкнулась с другим запросом. Проверьте её ещё раз.',
    'Login yoki parol noto‘g‘ri.': 'Неверный логин или пароль.',
    'Bu login band.': 'Этот логин занят.',

    # --- Buyurtma ---
    'Ayrim taomlar mavjud emas. Menyuni yangilang.':
        'Некоторые блюда недоступны. Обновите меню.',
    'Buyurtma summasi juda katta.': 'Сумма заказа слишком велика.',
    'Bu stolda ochiq hisob bor. Taomni o‘sha hisobga qo‘shing.':
        'На этом столе есть открытый счёт. Добавьте блюдо в него.',
    'To‘langan hisobga taom qo‘shib bo‘lmaydi. Yangi hisob oching.':
        'В оплаченный счёт нельзя добавить блюдо. Откройте новый.',
    'Buyurtma boshqa usul bilan to‘langan.': 'Заказ оплачен другим способом.',
    'Yetkazib berish buyurtmasi faqat o‘sha platforma orqali to‘lanadi.':
        'Заказ на доставку оплачивается только через ту же платформу.',
    'Bir taomni takrorlamang; ko‘pi bilan 100 satr.':
        'Не повторяйте блюдо; не более 100 строк.',
    'Bu oxirgi qator. Butun hisobni bekor qiling.':
        'Это последняя строка. Отмените счёт целиком.',
    'Sababni yozing.': 'Укажите причину.',

    # --- Chegirma ---
    'Chegirma hisob summasidan katta bo‘lolmaydi.':
        'Скидка не может превышать сумму счёта.',
    'To‘liq chegirma o‘rniga hisobni bekor qiling.':
        'Вместо полной скидки отмените счёт.',
    'Chegirma sababini yozing.': 'Укажите причину скидки.',

    # --- Ombor ---
    'Omborda yetarli mahsulot yo‘q.': 'На складе недостаточно продукта.',
    'Dona butun son bo‘lishi kerak.': 'Штуки должны быть целым числом.',
    'Qoldiq chegaradan oshadi.': 'Остаток превышает предел.',
    'Bu mahsulot mavjud.': 'Такой продукт уже есть.',
    'Bu nomli retsept allaqachon bor.': 'Рецепт с таким названием уже есть.',
    'Narx faqat kirimda kiritiladi.': 'Цена указывается только при приходе.',
    'Dastlabki versiyada ombor harakati faqat bugungi sana bilan.':
        'В этой версии движение по складу возможно только сегодняшней датой.',

    # --- Kunlik sarf ---
    'Kelajakdagi kun uchun sarf kiritilmaydi.':
        'Нельзя вносить расход за будущий день.',
    'Bir mahsulotni faqat bir marta kiriting.':
        'Вносите каждый продукт только один раз.',
    'Bir kunda ko‘pi bilan 200 qator.': 'Не более 200 строк за день.',
    'Ayrim mahsulotlar topilmadi.': 'Некоторые продукты не найдены.',

    # --- Kun yakuni ---
    'Kelajakdagi kunni yopib bo‘lmaydi.': 'Нельзя закрыть будущий день.',
    'Bu kun allaqachon yopilgan.': 'Этот день уже закрыт.',

    # --- Davr va sana ---
    'Boshlanish sanasi tugash sanasidan keyin bo‘lishi mumkin emas.':
        'Дата начала не может быть позже даты окончания.',
    'Kelajakdagi sana uchun savdo hisoboti tuzilmaydi.':
        'Отчёт о продажах за будущую дату не строится.',
    'Bir hisobot oralig‘i ko‘pi bilan 3 yil.':
        'Диапазон отчёта — не более 3 лет.',
    'Bir oraliq ko‘pi bilan bir yil.': 'Диапазон — не более одного года.',
    'Oy noto‘g‘ri. Format: YYYY-MM.': 'Неверный месяц. Формат: YYYY-MM.',
    'Oy 01 dan 12 gacha bo‘lishi kerak.': 'Месяц должен быть от 01 до 12.',
    'Kelajak oyi uchun hisobot tuzilmaydi.': 'Отчёт за будущий месяц не строится.',
    'Kelajak oyi uchun oylik hisoboti tuzilmaydi.':
        'Отчёт по зарплате за будущий месяц не строится.',
    'Kelajakdagi xarajatni hisobga olish mumkin emas.':
        'Нельзя учесть расход будущей датой.',

    # --- Oylik ---
    'Bu xodim uchun tanlangan oy oyligi allaqachon to‘langan.':
        'Зарплата этому сотруднику за выбранный месяц уже выплачена.',
    'Superadmin hisobini bu yerdan o‘zgartirib bo‘lmaydi.':
        'Учётную запись суперадмина отсюда изменить нельзя.',
    'Superadmin oyligi bu bo‘limda yuritilmaydi.':
        'Зарплата суперадмина в этом разделе не ведётся.',
    'Kelajakdagi to‘lov sanasi mumkin emas.': 'Дата выплаты не может быть в будущем.',
    'Kelajak oyi uchun to‘lov kiritib bo‘lmaydi.':
        'Нельзя внести выплату за будущий месяц.',

    # --- Stol va menyu ---
    'Bu raqamli stol allaqachon bor.': 'Стол с таким номером уже существует.',
    'Bu stolda ochiq hisob bor. Avval to‘lovni yakunlang.':
        'На этом столе открытый счёт. Сначала завершите оплату.',
    'Taom boshqa filialga tegishli.': 'Блюдо принадлежит другому филиалу.',
    'Mahsulot boshqa filialga tegishli.': 'Продукт принадлежит другому филиалу.',
    'Kategoriya tanlangan taomga tegishli emas.':
        'Категория не относится к выбранному блюду.',
    # --- Qolganlari ---
    '7 yoki 30 kunni tanlang, yoki oyni belgilang.':
        'Выберите 7 или 30 дней либо укажите месяц.',
    'Bir ko‘rinishda ko‘pi bilan 1 yil.': 'В одном представлении — не более 1 года.',
    'Bir xil amal kaliti boshqa ma’lumot bilan yuborildi.':
        'Тот же ключ операции отправлен с другими данными.',
    'Bu kategoriya allaqachon mavjud.': 'Такая категория уже существует.',
    'Davr noto‘g‘ri.': 'Неверный период.',
    'Kamida bitta masalliq kiriting.': 'Укажите хотя бы один ингредиент.',
    'Kategoriya ushbu filialga tegishli emas.': 'Категория не принадлежит этому филиалу.',
    'Kelajakdagi sana uchun savdo ko‘rsatilmaydi.': 'Продажи за будущую дату не показываются.',
    'Oy noto‘g‘ri.': 'Неверный месяц.',
    'Rasm 5 MB dan kichik bo‘lishi kerak.': 'Изображение должно быть меньше 5 МБ.',
    'Rasm formati noto‘g‘ri.': 'Неверный формат изображения.',
    'Rasm o‘lchami juda katta.': 'Размер изображения слишком велик.',
    'Savol kamida 2 belgidan iborat bo‘lsin.': 'Вопрос должен содержать хотя бы 2 символа.',
    'Taom tanlangan kategoriyaga tegishli emas.': 'Блюдо не относится к выбранной категории.',
    # Davomat va ish haqi bo'limi: bu xabarlar tarjimasiz qolib ketgan edi.
    'Bir martada ko‘pi bilan 50 ta xodim.': 'За раз не более 50 сотрудников.',
    'Bir xodim ro‘yxatda ikki marta.': 'Один сотрудник в списке дважды.',
    'Faqat oxirgi {days} kunni belgilash mumkin.': 'Отметить можно только последние {days} дней.',
    'Kelajakdagi hafta uchun davomat yuritilmaydi.': 'Посещаемость за будущую неделю не ведётся.',
    'Kelajakdagi kun uchun davomat belgilanmaydi.': 'Посещаемость за будущий день не отмечается.',
    'Yakshanba — dam olish kuni, unga haq hisoblanmaydi.':
        'Воскресенье — выходной, оплата за него не начисляется.',
    'Superadmin ish haqi bu bo‘limda yuritilmaydi.':
        'Зарплата суперадмина в этом разделе не ведётся.',
    'Saqlandi. Yangi foiz shu paytdan keyingi sotuvlarga qo‘llanadi.':
        'Сохранено. Новый процент применяется к продажам с этого момента.',
    # Ilgari umuman _() ga o'ralmagan, ya'ni har doim o'zbekcha chiqardi.
    'Faqat oxirgi {days} kunni yopish mumkin.': 'Закрыть можно только последние {days} дней.',
    'Faqat oxirgi {days} kun uchun kiritish mumkin.': 'Вносить можно только за последние {days} дней.',
    '{name}: dona butun son bo‘lishi kerak.': '{name}: штуки должны быть целым числом.',
    'Bu hisob «{status}» holatida — o‘zgartirib bo‘lmaydi.':
        'Счёт в статусе «{status}» — изменить нельзя.',
    'Faqat to‘langan hisob qaytariladi. Bu hisob «{status}».':
        'Возврат возможен только по оплаченному счёту. Этот счёт «{status}».',
    'Buyurtma hozir “{state}” holatida. Sahifani yangilang.':
        'Заказ сейчас в статусе «{state}». Обновите страницу.',
    # Yangi tekshiruvlar va amallar.
    'Bu nomli taom allaqachon bor.': 'Блюдо с таким названием уже есть.',
    'Ish haqi to‘lovini bu yerdan o‘zgartirib bo‘lmaydi.':
        'Выплату зарплаты отсюда изменить нельзя.',
    'Bugungi yozuvlar orasida bunday qator yo‘q.': 'Среди сегодняшних записей такой строки нет.',
    'Ofitsiant hisobida {balance} so‘m bor, undan ko‘p berib bo‘lmaydi.':
        'На счету официанта {balance} сум, выдать больше нельзя.',
    'Joriy parol noto‘g‘ri.': 'Текущий пароль неверен.',
    'Parol almashtirildi.': 'Пароль изменён.',
    # Hisob holatlari xabar ichida ko'rsatiladi, shuning uchun ular ham kerak.
    'Ochiq': 'Открыт',
    'To‘langan': 'Оплачен',
    'Bekor qilingan': 'Отменён',
    'Qaytarilgan': 'Возвращён',
    'Yangi': 'Новый',
    'Tayyorlanmoqda': 'Готовится',
    'Tayyor': 'Готово',
    'Topshirildi': 'Передан',
    # --- AI yordamchining tayyor javoblari ---
    'Salom! Savdo, kecha-bugun taqqoslash, xarajat, ombor yoki eng ko‘p sotilgan taomlar haqida so‘rashingiz mumkin.':
        'Здравствуйте! Можно спросить о продажах, сравнении вчера-сегодня, расходах, складе '
        'или самых продаваемых блюдах.',
    'Bugun tushum {revenue} so‘m, {orders} ta to‘langan chek va {spend} so‘m xarajat qayd etildi.':
        'Сегодня выручка {revenue} сум, {orders} оплаченных чеков и {spend} сум расходов.',
    'Kecha bilan solishtirganda tushum {percent}% ga {direction}.':
        'По сравнению со вчера выручка {direction} на {percent}%.',
    'Kecha savdo bo‘lmagani uchun foiz hisoblanmadi.':
        'Вчера продаж не было, поэтому процент не рассчитан.',
    'o‘sdi': 'выросла',
    'kamaydi': 'снизилась',
    'Bugun va kecha': 'Сегодня и вчера',
    'Bugun': 'Сегодня',
    'Kecha': 'Вчера',
    'Oxirgi 7 kunda tushum {revenue} so‘m, xarajat {spend} so‘m.':
        'За последние 7 дней выручка {revenue} сум, расходы {spend} сум.',
    'Oldingi haftada savdo bo‘lmagani uchun foiz hisoblanmadi.':
        'На прошлой неделе продаж не было, поэтому процент не рассчитан.',
    'O‘sish: {percent}%.': 'Рост: {percent}%.',
    'Haftalik tushum': 'Выручка за неделю',
    'Oldingi 7 kun': 'Предыдущие 7 дней',
    'Oxirgi 7 kun': 'Последние 7 дней',
    'Oxirgi 7 kunda to‘langan savdo qayd etilmagan.':
        'За последние 7 дней оплаченных продаж не зафиксировано.',
    '{name} — {count} ta': '{name} — {count} шт.',
    'Oxirgi 7 kundagi eng ko‘p sotilgan taomlar: {names}.':
        'Самые продаваемые блюда за последние 7 дней: {names}.',
    'Eng ko‘p sotilgan taomlar': 'Самые продаваемые блюда',
    'Minimal qoldiqdan past mahsulot yo‘q. Ombor holati hozir me’yorda.':
        'Товаров ниже минимального остатка нет. Склад сейчас в норме.',
    'Quyidagi mahsulotlar minimal qoldiqda yoki undan past: {names}.':
        'Следующие товары на минимальном остатке или ниже: {names}.',
    'Oxirgi 7 kunda {spend} so‘m xarajat va {revenue} so‘m tushum qayd etilgan.':
        'За последние 7 дней зафиксировано {spend} сум расходов и {revenue} сум выручки.',
    '7 kunlik pul oqimi': 'Денежный поток за 7 дней',
    'Tushum': 'Выручка',
    'Xarajat': 'Расход',
}


EN = {
    'Bir taomni faqat bir marta kiriting.': 'Enter each dish only once.',
    'Bir martada ko‘pi bilan 100 ta taom.': '100 dishes at most in one go.',
    'Ayrim taomlar topilmadi.': 'Some dishes were not found.',
    'Ombor harakatlari tarixi faqat superadminga ochiq.':
        'The stock movement history is for the superadmin only.',
    '{name} — bugun tayyorlanmagan': '{name} — not cooked today',
    '{name} — {count} ta qoldi': '{name} — {count} left',
    '{name} — qoldiq {count} ta, undan ko‘pini hisobdan chiqarib bo‘lmaydi.':
        '{name} — {count} left, you cannot write off more than that.',
    'Bu taomlar tayyor emas: {dishes}. «Tayyor taomlar» bo‘limida bugun nechta tayyorlanganini kiriting.':
        'These dishes are not ready: {dishes}. Enter today’s cooked counts under «Ready dishes».',
    'Ofitsiant topilmadi.': 'Waiter not found.',
    'Bu ismli ofitsiant allaqachon bor.': 'A waiter with that name already exists.',
    'Nom bo‘sh bo‘lishi mumkin emas.': 'The name cannot be empty.',
    'Suhbat topilmadi.':
        'Chat not found.',
    'Suhbat o‘chirildi.':
        'Chat deleted.',
    'AI kaliti hali ulanmagan. Bugun, kecha yoki hafta bo‘yicha tezkor savollardan birini bosing, yoki OpenAI kalitini ulang.':
        'The AI key is not connected yet. Use one of the quick questions, or connect an OpenAI key.',
    # --- Umumiy xatolar ---
    'Buyurtma topilmadi.': 'Order not found.',
    'Mahsulot topilmadi.': 'Item not found.',
    'Stol topilmadi.': 'Table not found.',
    'Bu ismli xodim allaqachon bor.':
        'An employee with this name already exists.',
    'Bu xodimda tizim hisobi yo‘q.':
        'This employee has no system account.',
    'Login berilsa parol ham kerak.':
        'A login needs a password too.',
    'Login berilsa rol ham tanlanadi.':
        'A login needs a role as well.',
    'Avval nechtasi sotilganini kiriting — shundan keyin pul yoziladi.':
        'Enter how many were sold first — the payment is recorded after that.',
    'Bekor qilingan jo‘natma bo‘yicha hisobot qabul qilinmaydi.':
        'A cancelled delivery takes no report.',
    'Bekor qilingan jo‘natma bo‘yicha pul qabul qilinmaydi.':
        'A cancelled delivery takes no money.',
    'Bir qatorni faqat bir marta kiriting.':
        'Enter each line only once.',
    'Bu amal faqat superadminga ochiq.':
        'Only the superadmin may do this.',
    'Bu hamkor faolsizlantirilgan — unga taom jo‘natilmaydi.':
        'This partner is deactivated — food cannot be sent to them.',
    'Bu hamkorda yopilmagan jo‘natma bor. Avval hisobni yoping.':
        'This partner has an open delivery. Close the book first.',
    'Bu jo‘natma allaqachon bekor qilingan.':
        'This delivery is already cancelled.',
    'Bu jo‘natma uchun allaqachon {paid} so‘m olingan — hisobotni undan pastga tushirib bo‘lmaydi. Avval to‘lovni bekor qiling.':
        '{paid} so‘m has already been taken for this delivery — the report cannot go below that. Void the payment first.',
    'Bu narx tannarxdan past: «{name}» har porsiyada {amount} so‘m zarar.':
        'This price is below cost: “{name}” loses {amount} so‘m per portion.',
    'Bu nomli hamkor allaqachon bor.':
        'A partner with this name already exists.',
    'Bu qator boshqa jo‘natmaga tegishli.':
        'That line belongs to another delivery.',
    'Bu to‘lov allaqachon bekor qilingan.':
        'This payment is already voided.',
    'Bugun bu hamkorga allaqachon jo‘natilgan. Ikkinchi mashina bo‘lsa davom eting.':
        'Something was already sent to this partner today. If this is a second run, carry on.',
    'Hamkor ro‘yxatdan olindi.':
        'The partner was taken off the list.',
    'Hamkor topilmadi.':
        'Partner not found.',
    'Har bir qator uchun nechta sotilgani kiritilsin.':
        'Say how many were sold for every line.',
    'Hisobot berilgan jo‘natmani bekor qilib bo‘lmaydi. Hisobotni qaytadan kiriting.':
        'A delivery with a report cannot be cancelled. Enter the report again instead.',
    'Jo‘natma topilmadi.':
        'Delivery not found.',
    'Qolgan qarz {amount} so‘m — undan ko‘pini qabul qilib bo‘lmaydi.':
        'The remaining debt is {amount} so‘m — you cannot take more than that.',
    'To‘lov topilmadi.':
        'Payment not found.',
    '{date} kuni allaqachon yopilgan — o‘sha kundagi to‘lovni bekor qilib bo‘lmaydi.':
        '{date} is already closed — a payment from that day cannot be voided.',
    '{date} kuni allaqachon yopilgan — o‘sha kunga pul kiritib bo‘lmaydi.':
        '{date} is already closed — money cannot be entered for that day.',
    '«{name}» narxi menyu narxidan yuqori — tekshiring.':
        'The price for “{name}” is above the menu price — check it.',
    '«{name}» uchun hamkor narxi belgilanmagan — shu sababli jo‘natib bo‘lmaydi. Narxni shartnoma bo‘yicha superadmin kiritadi.':
        'There is no partner price for “{name}”, so it cannot be sent. The superadmin enters the contract price.',
    '«{name}» — {sent} ta jo‘natilgan, {sold} ta sotilgan deb bo‘lmaydi.':
        '“{name}” — {sent} were sent, {sold} sold is impossible.',
    'Arxivlangan taomga bonus belgilab bo‘lmaydi.':
        'A bonus cannot be set on an archived dish.',
    'Bonus qoidasi topilmadi.':
        'The bonus rule was not found.',
    'Faqat bugungi yozuvni o‘chirish mumkin.':
        'Only today’s record can be deleted.',
    'Kelajakdagi sana mumkin emas.':
        'A future date is not allowed.',
    'Qoida o‘chirildi.':
        'The rule was deleted.',
    'Saqlandi. Yangi qoida shu paytdan keyingi buyurtmalarga qo‘llanadi.':
        'Saved. The new rule applies to orders from this moment on.',
    'Taom topilmadi.':
        'Dish not found.',
    'Yozuv o‘chirildi va masalliq omborga qaytarildi.':
        'The record was deleted and the ingredients went back to the warehouse.',
    'Yozuv topilmadi.':
        'Record not found.',
    'Bu mahsulotda kirim-chiqim tarixi bor — o‘lchov birligini o‘zgartirib bo‘lmaydi. Yangi nom bilan yangi mahsulot oching.':
        'This product has a movement history, so its unit cannot be changed. Create a new product under a new name instead.',
    '«{name}» {recipes} retseptida ishlatilyapti — avval retseptdan olib tashlang.':
        '“{name}” is used in the {recipes} recipe — remove it from there first.',
    'Bu usul bilan bo‘lib to‘lab bo‘lmaydi.':
        'A payment cannot be split with this method.',
    'Ikkinchi to‘lov usulini tanlang.':
        'Choose the second payment method.',
    'Ikkinchi usul birinchisidan boshqa bo‘lishi kerak.':
        'The second method has to differ from the first.',
    'Ikkinchi usuldagi summa hisobdan kichik bo‘lishi kerak. Hammasi shu usul bilan bo‘lsa, uni asosiy qilib tanlang.':
        'The amount on the second method has to be less than the bill. If everything was paid that way, make it the main method.',
    'Ikkinchi usuldagi summa noldan katta bo‘lsin.':
        'The amount on the second method has to be above zero.',
    'Yetkazib berish buyurtmasi bo‘lib to‘lanmaydi — pul platformadan keladi.':
        'A delivery order cannot be split — the money comes from the platform.',
    'Xodim topilmadi.': 'Employee not found.',
    'Kategoriya topilmadi.': 'Category not found.',
    'Bu qator hisobda yo‘q.': 'That line is not on this bill.',
    'Qator olib tashlansa chegirma qolgan summadan katta bo‘lib qoladi. Avval chegirmani o‘zgartiring.':
        'Removing that line would leave a discount larger than the bill. Change the discount first.',
    'Amal holati o‘zgargan. Ma’lumotni yangilang.':
        'This has changed since you loaded it. Refresh and try again.',
    'Amal boshqa so‘rov bilan to‘qnashdi. Shu amalni qayta tekshiring.':
        'This clashed with another request. Check it before retrying.',
    'Login yoki parol noto‘g‘ri.': 'Wrong username or password.',
    'Bu login band.': 'That username is taken.',

    # --- Buyurtma ---
    'Ayrim taomlar mavjud emas. Menyuni yangilang.':
        'Some dishes are unavailable. Refresh the menu.',
    'Buyurtma summasi juda katta.': 'The order total is too large.',
    'Bu stolda ochiq hisob bor. Taomni o‘sha hisobga qo‘shing.':
        'This table already has an open bill. Add the dish to it.',
    'To‘langan hisobga taom qo‘shib bo‘lmaydi. Yangi hisob oching.':
        'A paid bill cannot take more dishes. Open a new one.',
    'Buyurtma boshqa usul bilan to‘langan.': 'This order was paid by another method.',
    'Yetkazib berish buyurtmasi faqat o‘sha platforma orqali to‘lanadi.':
        'A delivery order can only be paid through that same platform.',
    'Bir taomni takrorlamang; ko‘pi bilan 100 satr.':
        'Do not repeat a dish; 100 lines at most.',
    'Bu oxirgi qator. Butun hisobni bekor qiling.':
        'That is the last line. Cancel the whole bill instead.',
    'Sababni yozing.': 'Give a reason.',

    # --- Chegirma ---
    'Chegirma hisob summasidan katta bo‘lolmaydi.':
        'The discount cannot exceed the bill.',
    'To‘liq chegirma o‘rniga hisobni bekor qiling.':
        'For a full discount, cancel the bill instead.',
    'Chegirma sababini yozing.': 'Give a reason for the discount.',

    # --- Ombor ---
    'Omborda yetarli mahsulot yo‘q.': 'Not enough stock.',
    'Dona butun son bo‘lishi kerak.': 'Pieces must be a whole number.',
    'Qoldiq chegaradan oshadi.': 'The balance would exceed the limit.',
    'Bu mahsulot mavjud.': 'That item already exists.',
    'Bu nomli retsept allaqachon bor.': 'A recipe with that name already exists.',
    'Narx faqat kirimda kiritiladi.': 'A price is only entered on a receipt.',
    'Dastlabki versiyada ombor harakati faqat bugungi sana bilan.':
        'For now stock movements can only be dated today.',

    # --- Kunlik sarf ---
    'Kelajakdagi kun uchun sarf kiritilmaydi.':
        'Usage cannot be recorded for a future day.',
    'Bir mahsulotni faqat bir marta kiriting.': 'Enter each item only once.',
    'Bir kunda ko‘pi bilan 200 qator.': '200 lines a day at most.',
    'Ayrim mahsulotlar topilmadi.': 'Some items were not found.',

    # --- Kun yakuni ---
    'Kelajakdagi kunni yopib bo‘lmaydi.': 'A future day cannot be closed.',
    'Bu kun allaqachon yopilgan.': 'This day is already closed.',

    # --- Davr va sana ---
    'Boshlanish sanasi tugash sanasidan keyin bo‘lishi mumkin emas.':
        'The start date cannot be after the end date.',
    'Kelajakdagi sana uchun savdo hisoboti tuzilmaydi.':
        'No sales report is produced for a future date.',
    'Bir hisobot oralig‘i ko‘pi bilan 3 yil.': 'A report covers three years at most.',
    'Bir oraliq ko‘pi bilan bir yil.': 'A range covers one year at most.',
    'Oy noto‘g‘ri. Format: YYYY-MM.': 'Invalid month. Use YYYY-MM.',
    'Oy 01 dan 12 gacha bo‘lishi kerak.': 'The month must be between 01 and 12.',
    'Kelajak oyi uchun hisobot tuzilmaydi.': 'No report is produced for a future month.',
    'Kelajak oyi uchun oylik hisoboti tuzilmaydi.':
        'No payroll report is produced for a future month.',
    'Kelajakdagi xarajatni hisobga olish mumkin emas.':
        'An expense cannot be dated in the future.',

    # --- Oylik ---
    'Bu xodim uchun tanlangan oy oyligi allaqachon to‘langan.':
        'This employee has already been paid for that month.',
    'Superadmin hisobini bu yerdan o‘zgartirib bo‘lmaydi.':
        'The owner account cannot be changed here.',
    'Superadmin oyligi bu bo‘limda yuritilmaydi.':
        'The owner salary is not handled in this section.',
    'Kelajakdagi to‘lov sanasi mumkin emas.': 'The payment date cannot be in the future.',
    'Kelajak oyi uchun to‘lov kiritib bo‘lmaydi.':
        'A payment cannot be recorded for a future month.',

    # --- Stol va menyu ---
    'Bu raqamli stol allaqachon bor.': 'A table with that number already exists.',
    'Bu stolda ochiq hisob bor. Avval to‘lovni yakunlang.':
        'This table has an open bill. Settle it first.',
    'Taom boshqa filialga tegishli.': 'That dish belongs to another branch.',
    'Mahsulot boshqa filialga tegishli.': 'That item belongs to another branch.',
    'Kategoriya tanlangan taomga tegishli emas.':
        'The category does not match the selected dish.',
    # --- Qolganlari ---
    '7 yoki 30 kunni tanlang, yoki oyni belgilang.':
        'Choose 7 or 30 days, or pick a month.',
    'Bir ko‘rinishda ko‘pi bilan 1 yil.': 'One view covers a year at most.',
    'Bir xil amal kaliti boshqa ma’lumot bilan yuborildi.':
        'The same request key arrived with different data.',
    'Bu kategoriya allaqachon mavjud.': 'That category already exists.',
    'Davr noto‘g‘ri.': 'Invalid period.',
    'Kamida bitta masalliq kiriting.': 'Add at least one ingredient.',
    'Kategoriya ushbu filialga tegishli emas.': 'That category belongs to another branch.',
    'Kelajakdagi sana uchun savdo ko‘rsatilmaydi.': 'Sales are not shown for a future date.',
    'Oy noto‘g‘ri.': 'Invalid month.',
    'Rasm 5 MB dan kichik bo‘lishi kerak.': 'The image must be under 5 MB.',
    'Rasm formati noto‘g‘ri.': 'Unsupported image format.',
    'Rasm o‘lchami juda katta.': 'The image is too large.',
    'Savol kamida 2 belgidan iborat bo‘lsin.': 'The question needs at least 2 characters.',
    'Taom tanlangan kategoriyaga tegishli emas.': 'The dish does not belong to the selected category.',
    # Davomat va ish haqi bo'limi: bu xabarlar tarjimasiz qolib ketgan edi.
    'Bir martada ko‘pi bilan 50 ta xodim.': '50 people at most in one go.',
    'Bir xodim ro‘yxatda ikki marta.': 'The same person appears twice in the list.',
    'Faqat oxirgi {days} kunni belgilash mumkin.': 'Only the last {days} days can be marked.',
    'Kelajakdagi hafta uchun davomat yuritilmaydi.': 'Attendance is not kept for a future week.',
    'Kelajakdagi kun uchun davomat belgilanmaydi.': 'Attendance is not marked for a future day.',
    'Yakshanba — dam olish kuni, unga haq hisoblanmaydi.':
        'Sunday is the rest day; no wage is earned for it.',
    'Superadmin ish haqi bu bo‘limda yuritilmaydi.':
        'The owner’s pay is not handled in this section.',
    'Saqlandi. Yangi foiz shu paytdan keyingi sotuvlarga qo‘llanadi.':
        'Saved. The new rate applies to sales from now on.',
    # Ilgari umuman _() ga o'ralmagan, ya'ni har doim o'zbekcha chiqardi.
    'Faqat oxirgi {days} kunni yopish mumkin.': 'Only the last {days} days can be closed.',
    'Faqat oxirgi {days} kun uchun kiritish mumkin.': 'Entries are allowed for the last {days} days only.',
    '{name}: dona butun son bo‘lishi kerak.': '{name}: pieces must be a whole number.',
    'Bu hisob «{status}» holatida — o‘zgartirib bo‘lmaydi.':
        'This bill is «{status}» — it cannot be changed.',
    'Faqat to‘langan hisob qaytariladi. Bu hisob «{status}».':
        'Only a paid bill can be refunded. This one is «{status}».',
    'Buyurtma hozir “{state}” holatida. Sahifani yangilang.':
        'The order is now “{state}”. Refresh the page.',
    # Yangi tekshiruvlar va amallar.
    'Bu nomli taom allaqachon bor.': 'A dish with that name already exists.',
    'Ish haqi to‘lovini bu yerdan o‘zgartirib bo‘lmaydi.':
        'A salary payment cannot be changed from here.',
    'Bugungi yozuvlar orasida bunday qator yo‘q.': 'No such row among today’s entries.',
    'Ofitsiant hisobida {balance} so‘m bor, undan ko‘p berib bo‘lmaydi.':
        'The waiter has {balance} so‘m on account; you cannot hand over more.',
    'Joriy parol noto‘g‘ri.': 'The current password is wrong.',
    'Parol almashtirildi.': 'Password changed.',
    # Hisob holatlari xabar ichida ko'rsatiladi, shuning uchun ular ham kerak.
    'Ochiq': 'Open',
    'To‘langan': 'Paid',
    'Bekor qilingan': 'Cancelled',
    'Qaytarilgan': 'Refunded',
    'Yangi': 'New',
    'Tayyorlanmoqda': 'Cooking',
    'Tayyor': 'Ready',
    'Topshirildi': 'Served',
    # --- AI yordamchining tayyor javoblari ---
    'Salom! Savdo, kecha-bugun taqqoslash, xarajat, ombor yoki eng ko‘p sotilgan taomlar haqida so‘rashingiz mumkin.':
        'Hello! You can ask about sales, today against yesterday, expenses, stock '
        'or the best-selling dishes.',
    'Bugun tushum {revenue} so‘m, {orders} ta to‘langan chek va {spend} so‘m xarajat qayd etildi.':
        'Today: {revenue} so‘m in takings, {orders} paid bills and {spend} so‘m of expenses.',
    'Kecha bilan solishtirganda tushum {percent}% ga {direction}.':
        'Against yesterday, takings {direction} by {percent}%.',
    'Kecha savdo bo‘lmagani uchun foiz hisoblanmadi.':
        'There were no sales yesterday, so no percentage was calculated.',
    'o‘sdi': 'rose',
    'kamaydi': 'fell',
    'Bugun va kecha': 'Today and yesterday',
    'Bugun': 'Today',
    'Kecha': 'Yesterday',
    'Oxirgi 7 kunda tushum {revenue} so‘m, xarajat {spend} so‘m.':
        'Over the last 7 days: {revenue} so‘m in takings, {spend} so‘m of expenses.',
    'Oldingi haftada savdo bo‘lmagani uchun foiz hisoblanmadi.':
        'There were no sales the week before, so no percentage was calculated.',
    'O‘sish: {percent}%.': 'Growth: {percent}%.',
    'Haftalik tushum': 'Weekly takings',
    'Oldingi 7 kun': 'Previous 7 days',
    'Oxirgi 7 kun': 'Last 7 days',
    'Oxirgi 7 kunda to‘langan savdo qayd etilmagan.':
        'No paid sales were recorded in the last 7 days.',
    '{name} — {count} ta': '{name} — {count}',
    'Oxirgi 7 kundagi eng ko‘p sotilgan taomlar: {names}.':
        'Best-selling dishes of the last 7 days: {names}.',
    'Eng ko‘p sotilgan taomlar': 'Best-selling dishes',
    'Minimal qoldiqdan past mahsulot yo‘q. Ombor holati hozir me’yorda.':
        'Nothing is below its minimum level. Stock is fine right now.',
    'Quyidagi mahsulotlar minimal qoldiqda yoki undan past: {names}.':
        'These items are at or below their minimum level: {names}.',
    'Oxirgi 7 kunda {spend} so‘m xarajat va {revenue} so‘m tushum qayd etilgan.':
        'The last 7 days recorded {spend} so‘m of expenses and {revenue} so‘m of takings.',
    '7 kunlik pul oqimi': 'Cash flow over 7 days',
    'Tushum': 'Takings',
    'Xarajat': 'Expense',
}

