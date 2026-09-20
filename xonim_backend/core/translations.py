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
}


EN = {
    'Bir taomni faqat bir marta kiriting.': 'Enter each dish only once.',
    'Bir martada ko‘pi bilan 100 ta taom.': '100 dishes at most in one go.',
    'Ayrim taomlar topilmadi.': 'Some dishes were not found.',
    'Ombor harakatlari tarixi faqat superadminga ochiq.':
        'The stock movement history is for the superadmin only.',
    '{name} — bugun tayyorlanmagan': '{name} — not cooked today',
    '{name} — {count} ta qoldi': '{name} — {count} left',
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
}

