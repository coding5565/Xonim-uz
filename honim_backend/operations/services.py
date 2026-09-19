import hashlib
import json
from uuid import NAMESPACE_URL, uuid5
from decimal import Decimal
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError, APIException

from core.i18n import _
from catalog.models import Dish
from users.models import AuditEvent
from .models import CLOSED_STATUSES, DELIVERY_CHANNELS, ORDER_STATUS_LABELS, SALE_PAYMENT_LABELS, Order, OrderLine, Expense, Ingredient, Recipe, RecipeLine, StockMovement, Table, Waiter
from .printing import print_prep_tickets, print_receipt_quietly, print_void_ticket


class Conflict(APIException):
    status_code = 409
    default_detail = 'Amal holati o‘zgargan. Ma’lumotni yangilang.'


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
    """Miqdorni jurnal uchun o'qiladigan holga keltiradi: 20.000 -> 20."""
    trimmed = Decimal(value).quantize(Decimal('0.001'))
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


def consume_order_stock(user, order):
    """Deduct exact recipe quantities once an order is paid.

    All affected ingredients are locked first. A shortage rejects payment instead
    of silently making the warehouse balance incorrect.
    """
    lines = list(order.lines.select_related('dish'))
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
    ingredients = {
        item.id: item for item in Ingredient.objects.select_for_update().filter(branch=user.branch, id__in=required).order_by('id')
    }
    missing = []
    for ingredient_id, quantity in required.items():
        ingredient = ingredients.get(ingredient_id)
        if not ingredient or ingredient.quantity < quantity:
            name = ingredient.name if ingredient else 'noma’lum mahsulot'
            available = ingredient.quantity if ingredient else 0
            missing.append(f'{name}: kerak {quantity.normalize()} {ingredient.unit if ingredient else ""}, qoldiq {available}')
    if missing:
        raise ValidationError({'stock': _('Ombor yetarli emas. Kirimni tekshiring: ') + '; '.join(missing)})

    for ingredient_id, quantity in required.items():
        ingredient = ingredients[ingredient_id]
        Ingredient.objects.filter(pk=ingredient_id).update(quantity=F('quantity') - quantity)

    for line, recipe_line, quantity in usage_rows:
        key = uuid5(NAMESPACE_URL, f'honim-sale-stock:{order.id}:{line.id}:{recipe_line.ingredient_id}')
        ingredient = ingredients[recipe_line.ingredient_id]
        # Sotuv paytidagi ombor tannarxi muzlatiladi: keyin narx o'zgarsa ham
        # eski hisobotlar o'zgarmaydi.
        StockMovement.objects.create(
            branch=user.branch, ingredient=ingredient, actor=user,
            key=key, request_hash=fingerprint({'order': order.id, 'line': line.id, 'ingredient': recipe_line.ingredient_id, 'quantity': str(quantity)}),
            kind='sale_consumption', quantity=quantity, date=timezone.localdate(),
            unit_cost=ingredient.unit_cost, cost_total=(ingredient.unit_cost * quantity).quantize(Decimal('0.01')),
            note=f'#{order.id} buyurtma · {line.name}',
        )
    # Har bir masalliq alohida yoziladi: qaysi mahsulot, qancha va qachon
    # ayrilgani jurnaldan ko'rinib tursin.
    audit_many(user, [
        (
            'stock.sale_consumption',
            f'#{order.id} buyurtma · {ingredients[ingredient_id].name} · -{quantity_text(quantity)} {ingredients[ingredient_id].unit}',
        )
        for ingredient_id, quantity in sorted(required.items(), key=lambda item: ingredients[item[0]].name)
    ])



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


@transaction.atomic
def create_order(user, data):
    previous = existing(Order, user, data)
    if previous:
        return previous
    dishes = {dish.id: dish for dish in Dish.objects.select_for_update().filter(branch=user.branch, archived=False, available=True, id__in=[line['dish'] for line in data['lines']])}
    if len(dishes) != len(data['lines']):
        raise ValidationError(_('Ayrim taomlar mavjud emas. Menyuni yangilang.'))
    total = sum((dishes[line['dish']].price * line['quantity'] for line in data['lines']), Decimal('0'))
    if total > Decimal('999999999999.99'):
        raise ValidationError(_('Buyurtma summasi juda katta.'))
    paid = bool(data['payment_method'])
    check_payment_channel(data.get('channel', 'hall'), data['payment_method'])

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
    order = Order.objects.create(
        branch=user.branch, cashier=user, key=data['key'], request_hash=fingerprint(data),
        table=table_text, table_ref=table, waiter=waiter_text, waiter_ref=waiter,
        waiter_commission=commission, channel=data.get('channel', 'hall'),
        total=total, status='paid' if paid else 'open',
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
    # Tayyorlash talonlari har doim chiqadi: ovqat to'lovni kutmaydi.
    order.print_problems = print_prep_tickets(order)
    _log_print_problems(user, order, order.print_problems)
    # Tayyorlangan miqdordan oshib ketilgan bo'lsa jurnalga tushadi.
    # Import shu yerda: dish_prep moduli services'ga tayanadi, aylanma
    # bog'liqlik bo'lmasligi uchun chaqirilganda yuklanadi.
    from .dish_prep import note_oversell
    note_oversell(user, order)
    audit(user, 'order.create', f'#{order.id} · {table.label if table else (table_text or "olib ketish")} · {total} so‘m · {len(data["lines"])} qator')
    return order


def _line_unit_cost(recipe):
    return (recipe_cost(recipe) / recipe.yield_quantity).quantize(Decimal('0.01')) if recipe else Decimal('0')


@transaction.atomic
def append_order_lines(user, order_id, data):
    """Add what the guest asked for after the bill was opened.

    The row lock serialises concurrent adds to the same bill, so checking the
    batch key before inserting is enough to make a retried request a no-op.
    """
    order = Order.objects.select_for_update().filter(branch=user.branch, id=order_id).first()
    if not order:
        raise ValidationError(_('Buyurtma topilmadi.'))
    if order.status != 'open':
        raise Conflict(_('To‘langan hisobga taom qo‘shib bo‘lmaydi. Yangi hisob oching.'))
    if OrderLine.objects.filter(order=order, batch_key=data['key']).exists():
        order.refresh_from_db()
        return order

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
    fields = ['total']
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
    order.print_problems = print_prep_tickets(order, fresh, addition=True)
    _log_print_problems(user, order, order.print_problems)
    from .dish_prep import note_oversell
    note_oversell(user, order)
    names = ', '.join(f'{dishes[line["dish"]].name} x{line["quantity"]}' for line in data['lines'])
    audit(user, 'order.append', f'#{order.id} · +{added} so‘m · {names}')
    return order


def _open_order(user, order_id):
    """Ochiq hisobni qulflab oladi; yopilgan bo'lsa sababini aytadi."""
    order = Order.objects.select_for_update().filter(branch=user.branch, id=order_id).first()
    if not order:
        raise ValidationError(_('Buyurtma topilmadi.'))
    if order.status != 'open':
        raise Conflict(f'Bu hisob «{ORDER_STATUS_LABELS[order.status]}» holatida — o‘zgartirib bo‘lmaydi.')
    return order


@transaction.atomic
def remove_order_line(user, order_id, line_id):
    """Ochiq hisobdan bitta qatorni olib tashlaydi.

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
    order.save(update_fields=['total'])
    audit(user, 'order.line_remove', f'#{order.id} · {name} x{amount} olib tashlandi · −{removed} so‘m')
    # Oshxona allaqachon talonni olgan bo'lishi mumkin, shuning uchun bekor
    # qilingani ham qog'ozda chiqadi — aks holda taom baribir pishirilardi.
    order.print_problems = print_void_ticket(order, f'{name} x{amount} BEKOR')
    order.refresh_from_db()
    return order


@transaction.atomic
def cancel_order(user, order_id, reason):
    """To'lovsiz hisobni bekor qiladi. Yozuv o'chmaydi — tarixda qoladi."""
    order = _open_order(user, order_id)
    order.status = 'cancelled'
    order.void_reason = reason
    order.voided_at = timezone.now()
    order.voided_by = user
    order.save(update_fields=['status', 'void_reason', 'voided_at', 'voided_by'])
    audit(user, 'order.cancel', f'#{order.id} · {order.total} so‘m · {reason}')
    order.print_problems = print_void_ticket(order, 'HISOB BEKOR QILINDI')
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
        raise Conflict(f'Faqat to‘langan hisob qaytariladi. Bu hisob «{ORDER_STATUS_LABELS[order.status]}».')

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
    moves = list(StockMovement.objects.filter(
        branch=user.branch, kind='sale_consumption', note__startswith=f'#{order.id} buyurtma',
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
        key = uuid5(NAMESPACE_URL, f'honim-refund-stock:{order.id}:{ingredient_id}')
        StockMovement.objects.create(
            branch=user.branch, ingredient=ingredient, actor=user, key=key,
            request_hash=fingerprint({'refund': order.id, 'ingredient': ingredient_id, 'quantity': str(amount)}),
            kind='receipt', quantity=amount, date=timezone.localdate(),
            unit_cost=ingredient.unit_cost, cost_total=Decimal('0'),
            note=f'#{order.id} buyurtma qaytarildi',
        )
        rows.append((
            'stock.receipt',
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
    order.save(update_fields=['discount', 'discount_reason', 'total'])
    if amount:
        audit(
            user, 'order.discount',
            f'#{order.id} · −{amount} so‘m ({percent.quantize(Decimal("0.1"))}%) · {reason}',
        )
    else:
        audit(user, 'order.discount', f'#{order.id} · chegirma olib tashlandi')
    return order



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
