import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from catalog.models import Dish
from core.i18n import _
from users.models import AuditEvent

from .models import (
    DEFAULT_PLATFORM_COMMISSION,
    DELIVERY_CHANNELS,
    ORDER_STATUS_LABELS,
    SALE_PAYMENT_LABELS,
    ChannelFee,
    Expense,
    Ingredient,
    Order,
    OrderLine,
    Recipe,
    RecipeLine,
    StockMovement,
    Table,
    Waiter,
)
from .printing import print_prep_tickets, print_receipt_quietly, print_void_ticket


class Conflict(APIException):
    status_code = 409

    def __init__(self, detail=None, code=None):
        # Tarjima aynan shu yerda bajariladi: sinf maydonida yozilsa matn
        # modul yuklanayotganda muzlab qolardi va doim o'zbekcha chiqardi.
        super().__init__(detail or _('Amal holati o‘zgargan. Ma’lumotni yangilang.'), code)


def safely(call, *args, **kwargs):
    """Runs a write and turns a lost insert race into 409 instead of 500.

    Every «read, check, then insert» path has a window: another till can commit
    the same row between the check and the insert, and the unique constraint
    then fires. That is a conflict the caller can retry, not a server fault, so
    it must never reach the user as a 500.
    """
    try:
        return call(*args, **kwargs)
    except (IntegrityError, OperationalError):
        raise Conflict(_('Amal boshqa so‘rov bilan to‘qnashdi. Shu amalni qayta tekshiring.')) from None


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def existing(model, user, data):
    obj = model.objects.filter(branch=user.branch, key=data['key']).first()
    if obj and obj.request_hash != fingerprint(data):
        raise Conflict(_('Bir xil amal kaliti boshqa ma’lumot bilan yuborildi.'))
    return obj


def audit(user, action, description):
    AuditEvent.objects.create(branch=user.branch, actor=user, action=action, description=description[:300])


def audit_many(user, rows):
    """Bir nechta yozuvni bitta so'rovda jurnalga qo'yadi.

    Bitta to'lov o'nlab masalliqqa tegishi mumkin, shuning uchun har biri uchun
    alohida INSERT yubormaymiz.
    """
    if not rows:
        return
    AuditEvent.objects.bulk_create([
        AuditEvent(branch=user.branch, actor=user, action=action, description=description[:300])
        for action, description in rows
    ])


def quantity_text(value):
    """Miqdorni jurnal uchun o'qiladigan holga keltiradi: 20.000000 -> 20.

    Olti xonagacha: ziravor kabi mayda masalliq jurnalda «0» bo'lib
    ko'rinmasligi kerak.
    """
    trimmed = Decimal(value).quantize(Decimal('0.000001'))
    return f'{trimmed.normalize():f}'


def reprice_recipes(ingredient):
    """Masalliq narxi o'zgarganda uni ishlatgan retseptlarni qayta hisoblaydi.

    Faqat joriy retsept tannarxi yangilanadi. Sotilgan buyurtmalardagi
    OrderLine.cost_total tegilmaydi — u sotuv paytida muzlatilgan va eski
    hisobotlar shunga tayanadi.
    """
    lines = list(RecipeLine.objects.filter(ingredient=ingredient))
    for line in lines:
        line.batch_cost = (line.quantity * ingredient.unit_cost).quantize(Decimal('0.01'))
    if lines:
        RecipeLine.objects.bulk_update(lines, ['batch_cost'])
    return len(lines)


def recipe_cost(recipe):
    return sum((line.batch_cost for line in recipe.lines.all()), Decimal('0'))


def _recipes_for_dishes(branch, dish_ids):
    return {
        recipe.dish_id: recipe
        for recipe in Recipe.objects.filter(branch=branch, active=True, dish_id__in=dish_ids)
        .prefetch_related('lines__ingredient')
    }


def consume_recipe_stock(user, lines, *, kind, tag, source, key_prefix):
    """Retsept bo'yicha masalliqni ombordan ayiradi.

    Bitta joyda turadi, chunki uni ikki yo'l ishlatadi: zal sotuvi va
    hamkorga jo'natish. Ikki nusxa bo'lsa ular sekin-asta ajralib ketardi
    va ajralgani aynan pulda ko'rinardi.

    `tag`        — jurnal va izohdagi prefiks: «#12 buyurtma» yoki «H#5 hamkor».
    `kind`       — StockMovement turi: 'sale_consumption' yoki 'partner_sale'.
    `source`     — idempotentlik barmoq izidagi hujjat nomi va raqami.
    `key_prefix` — uuid5 uchun: bir xil qator ikki marta ayirmasligi uchun.
    """
    recipes = _recipes_for_dishes(user.branch, [line.dish_id for line in lines])
    required = {}
    usage_rows = []
    for line in lines:
        recipe = recipes.get(line.dish_id)
        if not recipe:
            continue
        factor = Decimal(line.quantity) / recipe.yield_quantity
        for item in recipe.lines.all():
            required[item.ingredient_id] = required.get(item.ingredient_id, Decimal('0')) + item.quantity * factor
            usage_rows.append((line, item, item.quantity * factor))

    if not required:
        return
    # `order_by('id')` shart: jo'natish va to'lov bir vaqtda masalliqlarni
    # boshqa-boshqa tartibda qulflasa, ikkalasi bir-birini kutib qolardi.
    ingredients = {
        item.id: item for item in Ingredient.objects.select_for_update().filter(branch=user.branch, id__in=required).order_by('id')
    }
    # Retsept — TAXMIN, qonun emas: bir taomga ba'zida ko'proq, ba'zida kamroq
    # ketadi. Shuning uchun qoldiq yetmasa ham sotuv to'xtatilmaydi — mijoz
    # oldida turgan kassir omborning taxminiy raqami sababli pul ololmay
    # qolishi mumkin emas. Qoldiq minusga tushadi va bu superadminga
    # «hisob haqiqatdan ajralib ketdi» degan aniq signal bo'ladi.
    shortages = []
    for ingredient_id, quantity in required.items():
        ingredient = ingredients.get(ingredient_id)
        if ingredient and ingredient.quantity < quantity:
            shortages.append((
                'stock.shortage',
                f'{tag} · {ingredient.name} · retsept {quantity_text(quantity)} '
                f'{ingredient.unit} so‘radi, qoldiq {quantity_text(ingredient.quantity)} edi',
            ))
    audit_many(user, shortages)

    for ingredient_id, quantity in required.items():
        if ingredient_id not in ingredients:
            # Masalliq o'chirilgan bo'lsa yozib o'tirmaymiz: retsept eskirgan.
            continue
        Ingredient.objects.filter(pk=ingredient_id).update(quantity=F('quantity') - quantity)

    for line, recipe_line, quantity in usage_rows:
        ingredient = ingredients.get(recipe_line.ingredient_id)
        if not ingredient:
            continue
        key = uuid5(NAMESPACE_URL, f'{key_prefix}:{line.id}:{recipe_line.ingredient_id}')
        # Sotuv paytidagi ombor tannarxi muzlatiladi: keyin narx o'zgarsa ham
        # eski hisobotlar o'zgarmaydi.
        StockMovement.objects.create(
            branch=user.branch, ingredient=ingredient, actor=user,
            key=key, request_hash=fingerprint({**source, 'line': line.id, 'ingredient': recipe_line.ingredient_id, 'quantity': str(quantity)}),
            kind=kind, quantity=quantity, date=timezone.localdate(),
            unit_cost=ingredient.unit_cost, cost_total=(ingredient.unit_cost * quantity).quantize(Decimal('0.01')),
            note=f'{tag} · {line.name}',
        )
    # Har bir masalliq alohida yoziladi: qaysi mahsulot, qancha va qachon
    # ayrilgani jurnaldan ko'rinib tursin.
    audit_many(user, [
        (
            'stock.sale_consumption',
            f'{tag} · {ingredients[ingredient_id].name} · -{quantity_text(quantity)} {ingredients[ingredient_id].unit}',
        )
        for ingredient_id, quantity in sorted(
            ((key, value) for key, value in required.items() if key in ingredients),
            key=lambda item: ingredients[item[0]].name,
        )
    ])


def consume_order_stock(user, order):
    """Deduct exact recipe quantities once an order is paid.

    All affected ingredients are locked first. A shortage never blocks the
    sale: the recipe is an estimate, and a cashier with a guest in front of
    him must not be stopped by an estimate.
    """
    consume_recipe_stock(
        user, list(order.lines.select_related('dish')),
        kind='sale_consumption',
        tag=f'#{order.id} buyurtma',
        source={'order': order.id},
        key_prefix=f'xonim-sale-stock:{order.id}',
    )



def consume_delivery_stock(user, delivery):
    """Hamkorga jo'natilgan taomlar masallig'ini ombordan ayiradi.

    Ayirish JO'NATISH paytida bo'ladi, sotilganda emas: go'sht oshxonadan
    chiqib ketgan va uni keyingi mijozga sarflab bo'lmaydi. Maktab sotdimi
    yoki yo'qmi — bu masalliqqa aloqasi yo'q.

    Prefiks «H#» ataylab: buyurtma qatorlarining «#12 buyurtma» qidiruvi
    hamkor qatorlarini tutib olmasligi kerak.
    """
    consume_recipe_stock(
        user, list(delivery.lines.select_related('dish')),
        kind='partner_sale',
        tag=f'H#{delivery.id} hamkor',
        source={'delivery': delivery.id},
        key_prefix=f'xonim-partner-stock:{delivery.id}',
    )


def restore_delivery_stock(user, delivery):
    """Bekor qilingan jo'natma masalliqlarini omborga qaytaradi.

    Faqat hisobot berilmagan jo'natma bekor qilinadi, ya'ni ovqat hali
    sotilmagan. Shu sababli masalliqni qaytarish halol: u chiqmagan edi.
    """
    moves = list(StockMovement.objects.filter(
        branch=user.branch, kind='partner_sale', note__startswith=f'H#{delivery.id} hamkor · ',
    ).select_related('ingredient'))
    if not moves:
        return 0
    back = {}
    for move in moves:
        back[move.ingredient_id] = back.get(move.ingredient_id, Decimal('0')) + move.quantity
    locked = {
        item.id: item
        for item in Ingredient.objects.select_for_update().filter(branch=user.branch, id__in=back).order_by('id')
    }
    rows = []
    for ingredient_id, amount in back.items():
        ingredient = locked[ingredient_id]
        Ingredient.objects.filter(pk=ingredient_id).update(quantity=F('quantity') + amount)
        key = uuid5(NAMESPACE_URL, f'xonim-partner-refund:{delivery.id}:{ingredient_id}')
        StockMovement.objects.create(
            branch=user.branch, ingredient=ingredient, actor=user, key=key,
            request_hash=fingerprint({'partner_refund': delivery.id, 'ingredient': ingredient_id, 'quantity': str(amount)}),
            kind='refund', quantity=amount, date=timezone.localdate(),
            unit_cost=ingredient.unit_cost,
            cost_total=(ingredient.unit_cost * amount).quantize(Decimal('0.01')),
            note=f'H#{delivery.id} hamkor jo‘natmasi bekor qilindi',
        )
        rows.append((
            'stock.refund',
            f'H#{delivery.id} bekor qilindi · {ingredient.name} · +{quantity_text(amount)} {ingredient.unit}',
        ))
    audit_many(user, rows)
    return len(rows)


def _autoprint(order):
    """Chekni tranzaksiya yopilgandan keyin chiqaradi.

    on_commit ishlatiladi, chunki savdo allaqachon yozilgan: printer o'chiq
    bo'lsa ham buyurtma bekor bo'lmasligi kerak. print_receipt_quietly hech
    qachon xato ko'tarmaydi, shuning uchun on_commit zanjiri ham buzilmaydi.
    Nosozlik jurnalga tushadi — kassir keyin qayta chop etishi kerakligini
    superadmin ko'rib turishi uchun.
    """
    if not getattr(settings, 'RECEIPT_AUTO_PRINT', False):
        return
    cashier = order.cashier

    def run():
        if not print_receipt_quietly(order) and getattr(settings, 'RECEIPT_PRINTER', ''):
            audit(cashier, 'print.failed', f'#{order.id} · kassa cheki chiqmadi')

    transaction.on_commit(run)


def _log_print_problems(user, order, problems):
    audit_many(user, [('print.failed', f'#{order.id} · {problem}') for problem in problems])


def create_order(user, data):
    """Buyurtmani yozadi, so'ng talonlarni chiqaradi.

    Chop etish ATAYLAB tranzaksiyadan tashqarida: printer javob bermasa
    ulanish 4, yuborish 6 soniya kutadi, ikkita printer bilan bu 20 soniyagacha
    cho'ziladi. O'sha vaqt ichida taom qatorlari `select_for_update` bilan
    qulflangan bo'lardi — SQLite'da esa butun baza yozuvga yopiladi, ya'ni
    printer o'chib qolsa butun kassa to'xtab qolardi.

    Talon natijasi baribir javobda qaytadi: kassir «talon chiqmadi» ogohini
    darhol ko'rishi shart, aks holda oshxona buyurtmani ko'rmay qoladi.
    """
    order, fresh = _record_order(user, data)
    if not fresh:
        # Takroriy so'rov: hisob allaqachon yozilgan, talon ham chiqqan.
        return order
    order.print_problems = print_prep_tickets(order)
    _log_print_problems(user, order, order.print_problems)
    # Tayyorlangan miqdordan oshib ketilgan bo'lsa jurnalga tushadi.
    # Import shu yerda: dish_prep moduli services'ga tayanadi, aylanma
    # bog'liqlik bo'lmasligi uchun chaqirilganda yuklanadi.
    from .dish_prep import note_oversell
    note_oversell(user, order)
    return order


@transaction.atomic
def _record_order(user, data):
    """Hisobni bazaga yozadi. Qaytaradi: (hisob, yangi yozildimi)."""
    previous = existing(Order, user, data)
    if previous:
        return previous, False
    dishes = {dish.id: dish for dish in Dish.objects.select_for_update().filter(branch=user.branch, archived=False, available=True, id__in=[line['dish'] for line in data['lines']])}
    if len(dishes) != len(data['lines']):
        raise ValidationError(_('Ayrim taomlar mavjud emas. Menyuni yangilang.'))
    total = sum((dishes[line['dish']].price * line['quantity'] for line in data['lines']), Decimal('0'))
    if total > Decimal('999999999999.99'):
        raise ValidationError(_('Buyurtma summasi juda katta.'))
    paid = bool(data['payment_method'])
    check_payment_channel(data.get('channel', 'hall'), data['payment_method'])
    # Tayyor bo'lmagan taom buyurtmaga tushmaydi: oshxona talon kelgach
    # pishirmaydi, u faqat tayyoridan yig'adi.
    from .dish_prep import require_prepared
    require_prepared(user.branch, {line['dish']: line['quantity'] for line in data['lines']})

    table = None
    table_text = data['table']
    if data.get('table_id'):
        table = Table.objects.filter(branch=user.branch, pk=data['table_id'], active=True).first()
        if not table:
            raise ValidationError(_('Stol topilmadi.'))
        if Order.objects.filter(table_ref=table, status='open').exists():
            raise Conflict(_('Bu stolda ochiq hisob bor. Taomni o‘sha hisobga qo‘shing.'))
        table_text = str(table.number)

    # Ofitsiant va uning foizi sotuv paytida muzlatiladi: keyin foiz
    # o'zgarsa ham o'tgan buyurtmadagi ulush o'zgarmaydi.
    waiter = None
    waiter_text = data['waiter']
    commission = Decimal('0')
    if data.get('waiter_id'):
        waiter = Waiter.objects.filter(branch=user.branch, pk=data['waiter_id'], active=True).first()
        if not waiter:
            raise ValidationError(_('Ofitsiant topilmadi.'))
        waiter_text = waiter.name
        commission = waiter.commission

    recipes = _recipes_for_dishes(user.branch, dishes)
    channel = data.get('channel', 'hall')
    order = Order.objects.create(
        branch=user.branch, cashier=user, key=data['key'], request_hash=fingerprint(data),
        table=table_text, table_ref=table, waiter=waiter_text, waiter_ref=waiter,
        waiter_commission=commission, channel=channel,
        # Foiz shu yerda muzlatiladi: keyin shartnoma o'zgarsa ham bu
        # buyurtmaning hisobi o'zgarmaydi.
        channel_commission=platform_commission(user.branch, channel),
        total=total, status='paid' if paid else 'open',
        # Xizmat haqi hisob ustiga qo'shiladi va to'liq ofitsiantga o'tadi.
        # Yaxlitlash `service_charge_for` bilan bir xil bo'lishi shart.
        service_charge=(total * commission / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if waiter and channel == 'hall' else Decimal('0'),
        payment_method=data['payment_method'], paid_at=timezone.now() if paid else None,
    )
    for line in data['lines']:
        dish = dishes[line['dish']]
        recipe = recipes.get(dish.id)
        unit_cost = (recipe_cost(recipe) / recipe.yield_quantity).quantize(Decimal('0.01')) if recipe else Decimal('0')
        OrderLine.objects.create(order=order, dish=dish, name=dish.name, price=dish.price, quantity=line['quantity'], note=line['note'], cost_per_unit=unit_cost, cost_total=unit_cost * line['quantity'])
    if paid:
        consume_order_stock(user, order)
        _autoprint(order)
    audit(user, 'order.create', f'#{order.id} · {table.label if table else (table_text or "olib ketish")} · {total} so‘m · {len(data["lines"])} qator')
    return order, True


def _line_unit_cost(recipe):
    return (recipe_cost(recipe) / recipe.yield_quantity).quantize(Decimal('0.01')) if recipe else Decimal('0')


def append_order_lines(user, order_id, data):
    """Hisobga qo'shimcha taom yozadi, so'ng talonini chiqaradi.

    Chop etish tranzaksiyadan tashqarida — sababi `create_order` dagi bilan
    bir xil: javob bermagan printer hisob qatorini qulflab turmasligi kerak.
    """
    order, fresh = _record_extra_lines(user, order_id, data)
    if not fresh:
        return order
    order.print_problems = print_prep_tickets(order, fresh, addition=True)
    _log_print_problems(user, order, order.print_problems)
    from .dish_prep import note_oversell
    note_oversell(user, order)
    return order


@transaction.atomic
def _record_extra_lines(user, order_id, data):
    """Qatorlarni yozadi. Qaytaradi: (hisob, yangi qatorlar yoki None).

    Qator qulfi bir vaqtdagi qo'shishlarni navbatga soladi, shuning uchun
    yozishdan oldin partiya kalitini tekshirish takroriy so'rovni bekor
    qilish uchun yetarli.
    """
    order = Order.objects.select_for_update().filter(branch=user.branch, id=order_id).first()
    if not order:
        raise ValidationError(_('Buyurtma topilmadi.'))
    if order.status != 'open':
        raise Conflict(_('To‘langan hisobga taom qo‘shib bo‘lmaydi. Yangi hisob oching.'))
    if OrderLine.objects.filter(order=order, batch_key=data['key']).exists():
        # Takroriy so'rov: qatorlar allaqachon yozilgan, talon ham chiqqan.
        order.refresh_from_db()
        return order, None

    dishes = {
        dish.id: dish
        for dish in Dish.objects.select_for_update().filter(
            branch=user.branch, archived=False, available=True, id__in=[line['dish'] for line in data['lines']]
        )
    }
    if len(dishes) != len(data['lines']):
        raise ValidationError(_('Ayrim taomlar mavjud emas. Menyuni yangilang.'))
    added = sum((dishes[line['dish']].price * line['quantity'] for line in data['lines']), Decimal('0'))
    if order.total + added > Decimal('999999999999.99'):
        raise ValidationError(_('Buyurtma summasi juda katta.'))
    # Qo'shimcha taom ham tayyor bo'lishi shart — hisob ochiq bo'lgani
    # oshxonada ovqat borligini anglatmaydi.
    from .dish_prep import require_prepared
    require_prepared(user.branch, {line['dish']: line['quantity'] for line in data['lines']})

    recipes = _recipes_for_dishes(user.branch, dishes)
    now = timezone.now()
    for line in data['lines']:
        dish = dishes[line['dish']]
        unit_cost = _line_unit_cost(recipes.get(dish.id))
        OrderLine.objects.create(
            order=order, dish=dish, name=dish.name, price=dish.price, quantity=line['quantity'],
            note=line['note'], cost_per_unit=unit_cost, cost_total=unit_cost * line['quantity'],
            batch_key=data['key'], added_at=now,
        )

    order.total = order.total + added
    fields = refresh_service_charge(order, ['total'])
    # A bill the kitchen already finished has to come back on the board, or the
    # new dishes would never be cooked.
    if order.preparation_status in ('ready', 'served'):
        order.preparation_status = 'queued'
        order.ready_at = None
        order.served_at = None
        fields += ['preparation_status', 'ready_at', 'served_at']
    order.save(update_fields=fields)
    # Faqat shu qo'shimchadagi qatorlar chiqadi, butun buyurtma qayta emas.
    fresh = list(OrderLine.objects.filter(order=order, batch_key=data['key']).select_related('dish__category'))
    names = ', '.join(f'{dishes[line["dish"]].name} x{line["quantity"]}' for line in data['lines'])
    audit(user, 'order.append', f'#{order.id} · +{added} so‘m · {names}')
    return order, fresh


def _open_order(user, order_id):
    """Ochiq hisobni qulflab oladi; yopilgan bo'lsa sababini aytadi."""
    order = Order.objects.select_for_update().filter(branch=user.branch, id=order_id).first()
    if not order:
        raise ValidationError(_('Buyurtma topilmadi.'))
    if order.status != 'open':
        raise Conflict(_('Bu hisob «{status}» holatida — o‘zgartirib bo‘lmaydi.').format(
            status=_(ORDER_STATUS_LABELS[order.status])))
    return order


def remove_order_line(user, order_id, line_id):
    """Ochiq hisobdan bitta qatorni olib tashlaydi, so'ng bekor talonini chiqaradi.

    Chop etish tranzaksiyadan TASHQARIDA — `create_order` dagi bilan bir xil
    sabab: bu yerda hisob qatori `select_for_update` bilan qulflangan, javob
    bermagan printer esa ularni 20 soniyagacha ushlab turardi (SQLite'da bu
    butun bazani yozuvga yopadi).
    """
    order, removed = _record_line_removal(user, order_id, line_id)
    order.print_problems = print_void_ticket(order, removed)
    _log_print_problems(user, order, order.print_problems)
    return order


@transaction.atomic
def _record_line_removal(user, order_id, line_id):
    """Qatorni o'chiradi. Qaytaradi: (hisob, talonga yoziladigan matn).

    Kassir noto'g'ri taom bosib yuborsa shu yo'l bilan qaytaradi. Oxirgi
    qatorni olib tashlab bo'lmaydi: summasi nol hisob mavjud bo'lolmaydi,
    bunday holatda butun hisob bekor qilinadi.
    """
    order = _open_order(user, order_id)
    line = OrderLine.objects.filter(order=order, pk=line_id).select_related('dish').first()
    if not line:
        raise ValidationError(_('Bu qator hisobda yo‘q.'))
    if order.lines.count() == 1:
        raise Conflict(_('Bu oxirgi qator. Butun hisobni bekor qiling.'))

    removed = line.price * line.quantity
    # Chegirma butun hisobga berilgan. Qator olib tashlangach qolgan summa
    # chegirmadan kichik bo'lsa, hisob manfiyga tushardi — baza buni to'xtatadi,
    # lekin kassir «boshqa so'rov bilan to'qnashdi» degan tushunarsiz xabarni
    # olib, qayta-qayta urinib ko'rardi. Shuning uchun shu yerda tekshiriladi.
    if order.discount and order.total + order.discount - removed <= order.discount:
        raise Conflict(_('Qator olib tashlansa chegirma qolgan summadan katta bo‘lib qoladi. Avval chegirmani o‘zgartiring.'))

    name, amount = line.name, line.quantity
    line.delete()
    order.total = order.total - removed
    order.save(update_fields=refresh_service_charge(order, ['total']))
    audit(user, 'order.line_remove', f'#{order.id} · {name} x{amount} olib tashlandi · −{removed} so‘m')
    order.refresh_from_db()
    # Oshxona allaqachon talonni olgan bo'lishi mumkin, shuning uchun bekor
    # qilingani ham qog'ozda chiqadi — aks holda taom baribir pishirilardi.
    return order, f'{name} x{amount} BEKOR'


def cancel_order(user, order_id, reason):
    """To'lovsiz hisobni bekor qiladi, so'ng oshxonaga bekor talonini yuboradi.

    Chop etish tranzaksiyadan tashqarida: qulflangan hisob qatori printer
    javobini kutib turmasligi kerak.
    """
    order = _record_cancellation(user, order_id, reason)
    order.print_problems = print_void_ticket(order, 'HISOB BEKOR QILINDI')
    _log_print_problems(user, order, order.print_problems)
    return order


@transaction.atomic
def _record_cancellation(user, order_id, reason):
    """Hisobni bekor qilingan deb belgilaydi. Yozuv o'chmaydi — tarixda qoladi."""
    order = _open_order(user, order_id)
    order.status = 'cancelled'
    order.void_reason = reason
    order.voided_at = timezone.now()
    order.voided_by = user
    order.save(update_fields=['status', 'void_reason', 'voided_at', 'voided_by'])
    audit(user, 'order.cancel', f'#{order.id} · {order.total} so‘m · {reason}')
    return order


@transaction.atomic
def refund_order(user, order_id, reason):
    """To'langan hisobni qaytaradi: pul ham, ombor ham orqaga qaytadi.

    Sotuv paytida ayrilgan masalliqlar omborga qaytariladi va buni ko'rsatuvchi
    teskari harakat yoziladi — qoldiq yana to'g'ri bo'lishi uchun.
    """
    order = Order.objects.select_for_update().filter(branch=user.branch, id=order_id).first()
    if not order:
        raise ValidationError(_('Buyurtma topilmadi.'))
    if order.status == 'refunded':
        return order
    if order.status != 'paid':
        raise Conflict(_('Faqat to‘langan hisob qaytariladi. Bu hisob «{status}».').format(
            status=_(ORDER_STATUS_LABELS[order.status])))

    restored = restore_order_stock(user, order)
    order.status = 'refunded'
    order.void_reason = reason
    order.voided_at = timezone.now()
    order.voided_by = user
    order.save(update_fields=['status', 'void_reason', 'voided_at', 'voided_by'])
    audit(
        user, 'order.refund',
        f'#{order.id} · {order.total} so‘m qaytarildi · {restored} ta masalliq omborga qaytdi · {reason}',
    )
    return order


@transaction.atomic
def restore_order_stock(user, order):
    """Qaytarilgan buyurtma masalliqlarini omborga qaytaradi."""
    # Prefiks ataylab ajratuvchi bilan: «#1 buyurtma» qidiruvi «#12 buyurtma»
    # qatorlarini ham tutib olmasligi kerak.
    moves = list(StockMovement.objects.filter(
        branch=user.branch, kind='sale_consumption', note__startswith=f'#{order.id} buyurtma · ',
    ).select_related('ingredient'))
    if not moves:
        return 0
    back = {}
    for move in moves:
        back[move.ingredient_id] = back.get(move.ingredient_id, Decimal('0')) + move.quantity
    locked = {
        item.id: item
        for item in Ingredient.objects.select_for_update().filter(branch=user.branch, id__in=back).order_by('id')
    }
    rows = []
    for ingredient_id, amount in back.items():
        ingredient = locked[ingredient_id]
        Ingredient.objects.filter(pk=ingredient_id).update(quantity=F('quantity') + amount)
        key = uuid5(NAMESPACE_URL, f'xonim-refund-stock:{order.id}:{ingredient_id}')
        # Alohida tur: qaytarish XARID emas. Ilgari u «kirim» bo'lib yozilardi
        # va ombor tarixida yangi partiya kabi ko'rinardi. Qiymati ham
        # yoziladi, aks holda «sotilgan tannarx» qaytarilgandan keyin ham
        # kamaymay qolardi.
        StockMovement.objects.create(
            branch=user.branch, ingredient=ingredient, actor=user, key=key,
            request_hash=fingerprint({'refund': order.id, 'ingredient': ingredient_id, 'quantity': str(amount)}),
            kind='refund', quantity=amount, date=timezone.localdate(),
            unit_cost=ingredient.unit_cost,
            cost_total=(ingredient.unit_cost * amount).quantize(Decimal('0.01')),
            note=f'#{order.id} buyurtma qaytarildi',
        )
        rows.append((
            'stock.refund',
            f'#{order.id} qaytarildi · {ingredient.name} · +{quantity_text(amount)} {ingredient.unit}',
        ))
    audit_many(user, rows)
    return len(rows)


@transaction.atomic
def apply_discount(user, order_id, amount, reason):
    """Ochiq hisobga chegirma qo'yadi. Nol yuborilsa chegirma olib tashlanadi.

    `total` — to'lanadigan summa, shuning uchun chegirma unga darhol ta'sir
    qiladi va tushum o'z-o'zidan kamayadi: hech qayerda alohida ayirish
    kerak emas.
    """
    order = _open_order(user, order_id)
    subtotal = order.total + order.discount
    if amount > subtotal:
        raise ValidationError(_('Chegirma hisob summasidan katta bo‘lolmaydi.'))
    if amount == subtotal:
        raise ValidationError(_('To‘liq chegirma o‘rniga hisobni bekor qiling.'))

    percent = (amount / subtotal * 100) if subtotal else Decimal('0')
    # Chegirma miqdorida cheklov yo'q — egasining qarori. Yagona nazorat
    # jurnal: kim, qancha va nima uchun bergani yozib boriladi.
    if amount and not reason:
        raise ValidationError(_('Chegirma sababini yozing.'))

    order.discount = amount
    order.discount_reason = reason if amount else ''
    order.total = subtotal - amount
    # Xizmat haqi chegirmadan KEYINGI summadan olinadi: mijoz to'lagan
    # narsadan hisoblansin.
    order.save(update_fields=refresh_service_charge(order, ['discount', 'discount_reason', 'total']))
    if amount:
        audit(
            user, 'order.discount',
            f'#{order.id} · −{amount} so‘m ({percent.quantize(Decimal("0.1"))}%) · {reason}',
        )
    else:
        audit(user, 'order.discount', f'#{order.id} · chegirma olib tashlandi')
    return order




def platform_commission(branch, channel):
    """Platforma shu kanaldan ushlab qoladigan foiz.

    Sozlanmagan bo'lsa standart qiymat ishlatiladi: yangi filialda ham Uzum
    darhol to'g'ri hisoblansin. Zal va olib ketishda hech kim hech narsa
    ushlamaydi, shuning uchun nol.
    """
    if channel not in DELIVERY_CHANNELS:
        return Decimal('0')
    fee = ChannelFee.objects.filter(branch=branch, channel=channel).first()
    return fee.commission if fee else DEFAULT_PLATFORM_COMMISSION


def service_charge_for(order):
    """Hisobga qo'shiladigan xizmat haqi.

    Faqat zaldagi, ofitsiant biriktirilgan hisobga qo'shiladi: haq stolga
    xizmat uchun. Olib ketish va yetkazib berishda ofitsiant xizmati yo'q,
    demak haq ham yo'q.
    """
    if order.channel != 'hall' or not order.waiter_ref_id or not order.waiter_commission:
        return Decimal('0')
    # ROUND_HALF_UP ataylab: kassa ekrani summani JavaScript'dagi Math.round
    # bilan ko'rsatadi, u ham yarimni yuqoriga yaxlitlaydi. Decimal'ning
    # sukutdagi ROUND_HALF_EVEN qoidasi bilan ular rosa yarim tiyinda
    # ajralib, kassir ekranda boshqa raqam ko'rardi.
    return (order.total * order.waiter_commission / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def refresh_service_charge(order, fields):
    """Hisob summasi o'zgarganda xizmat haqini qayta hisoblaydi.

    Ochiq hisobga taom qo'shilishi yoki chegirma berilishi mumkin, xizmat
    haqi esa oxirgi summadan olinadi. To'langandan keyin hech narsa
    o'zgarmaydi — u yerda hisob allaqachon muzlatilgan.
    """
    charge = service_charge_for(order)
    if order.service_charge != charge:
        order.service_charge = charge
        fields.append('service_charge')
    return fields


def check_payment_channel(channel, method):
    """Yetkazib berish buyurtmasi faqat o'sha platforma orqali to'lanadi.

    Uzum buyurtmasini «naqd» deb belgilash puli kassaga tushgandek ko'rsatadi:
    smena yopishda kutilgan naqd shishib, kassir tushuntira olmaydigan farq
    paydo bo'ladi. Pul aslida platforma hisobiga tushadi.
    """
    if method and channel in DELIVERY_CHANNELS and method != channel:
        raise ValidationError(_('Yetkazib berish buyurtmasi faqat o‘sha platforma orqali to‘lanadi.'))

@transaction.atomic
def pay_order(user, order_id, method):
    order = Order.objects.select_for_update().filter(branch=user.branch, id=order_id).first()
    if not order:
        raise ValidationError(_('Buyurtma topilmadi.'))
    if order.status == 'paid':
        if order.payment_method != method:
            raise Conflict(_('Buyurtma boshqa usul bilan to‘langan.'))
        return order
    check_payment_channel(order.channel, method)
    consume_order_stock(user, order)
    changed = Order.objects.filter(pk=order.pk, status='open').update(status='paid', payment_method=method, paid_at=timezone.now())
    if not changed:
        raise Conflict()
    order.refresh_from_db()
    _autoprint(order)
    audit(user, 'order.pay', f'#{order.id} · {SALE_PAYMENT_LABELS.get(method, method)} · {order.total} so‘m')
    return order


@transaction.atomic
def create_expense(user, data):
    previous = existing(Expense, user, data)
    if previous:
        return previous
    obj = Expense.objects.create(branch=user.branch, actor=user, request_hash=fingerprint(data), **data)
    audit(user, 'expense.create', f'{obj.category} · {obj.purpose} · {obj.amount} so‘m · {obj.date}')
    return obj


def weighted_unit_cost(stock, quantity, spent):
    """Kirimdan keyingi o'rtacha tortilgan tannarx.

    Eski qoldiq o'z narxida, yangi partiya o'z narxida qo'shiladi. Narx
    kiritilmasa eski tannarx saqlanadi — nol narx bilan o'rtachani buzmaydi.
    """
    if spent is None or spent <= 0:
        return stock.unit_cost
    # Manfiy qoldiq — hisob haqiqatdan ajralgani belgisi. Uni o'rtachaga
    # qo'shsak, mavjud bo'lmagan mahsulot yangi partiya narxini pastga
    # tortib yuborardi. Bunday holatda faqat yangi partiya narxi olinadi.
    if stock.quantity <= 0:
        return (spent / quantity).quantize(Decimal('0.0001'))
    total_quantity = stock.quantity + quantity
    if total_quantity <= 0:
        return stock.unit_cost
    return ((stock.quantity * stock.unit_cost + spent) / total_quantity).quantize(Decimal('0.0001'))


@transaction.atomic
def move_stock(user, data):
    previous = existing(StockMovement, user, data)
    if previous:
        return previous
    stock = Ingredient.objects.select_for_update().filter(branch=user.branch, pk=data['ingredient']).first()
    if not stock:
        raise ValidationError(_('Mahsulot topilmadi.'))
    quantity = data['quantity']
    if stock.unit == 'dona' and quantity != quantity.to_integral_value():
        raise ValidationError(_('Dona butun son bo‘lishi kerak.'))
    spent = data.get('cost_total') or Decimal('0')
    if data['kind'] == 'consumption':
        changed = Ingredient.objects.filter(pk=stock.pk, quantity__gte=quantity).update(quantity=F('quantity') - quantity)
        if not changed:
            raise ValidationError(_('Omborda yetarli mahsulot yo‘q.'))
        # Sarf joriy o'rtacha tannarxda baholanadi va shu yerda muzlatiladi.
        unit_cost = stock.unit_cost
        spent = (unit_cost * quantity).quantize(Decimal('0.01'))
    else:
        if stock.quantity + quantity > Decimal('99999999999.999'):
            raise ValidationError(_('Qoldiq chegaradan oshadi.'))
        unit_cost = (spent / quantity).quantize(Decimal('0.0001')) if spent else stock.unit_cost
        average = weighted_unit_cost(stock, quantity, spent)
        Ingredient.objects.filter(pk=stock.pk).update(quantity=F('quantity') + quantity, unit_cost=average)
        if average != stock.unit_cost:
            # Yangi narx retseptlar tannarxiga darhol o'tadi.
            stock.unit_cost = average
            reprice_recipes(stock)
    fields = {key: value for key, value in data.items() if key not in ('ingredient', 'cost_total')}
    obj = StockMovement.objects.create(
        branch=user.branch, actor=user, ingredient=stock, request_hash=fingerprint(data),
        unit_cost=unit_cost, cost_total=spent, **fields,
    )
    sign = '-' if obj.kind == 'consumption' else '+'
    left = Ingredient.objects.values_list('quantity', flat=True).get(pk=stock.pk)
    money_text = f' · {obj.cost_total} so‘m' if obj.cost_total else ''
    audit(user, f'stock.{obj.kind}', f'{stock.name} · {sign}{quantity_text(quantity)} {stock.unit}{money_text} · {obj.date} · qoldiq {quantity_text(left)} {stock.unit}')
    return obj
