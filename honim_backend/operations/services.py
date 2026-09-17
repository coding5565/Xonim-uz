import hashlib
import json
from uuid import NAMESPACE_URL, uuid5
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import ValidationError, APIException
from catalog.models import Dish
from users.models import AuditEvent
from .models import Order, OrderLine, Expense, Ingredient, Recipe, StockMovement


class Conflict(APIException):
    status_code = 409
    default_detail = 'Amal holati o‘zgargan. Ma’lumotni yangilang.'


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def existing(model, user, data):
    obj = model.objects.filter(branch=user.branch, key=data['key']).first()
    if obj and obj.request_hash != fingerprint(data):
        raise Conflict('Bir xil amal kaliti boshqa ma’lumot bilan yuborildi.')
    return obj


def audit(user, action, description):
    AuditEvent.objects.create(branch=user.branch, actor=user, action=action, description=description)


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
        raise ValidationError({'stock': 'Ombor yetarli emas. Kirimni tekshiring: ' + '; '.join(missing)})

    for ingredient_id, quantity in required.items():
        ingredient = ingredients[ingredient_id]
        Ingredient.objects.filter(pk=ingredient_id).update(quantity=F('quantity') - quantity)

    for line, recipe_line, quantity in usage_rows:
        key = uuid5(NAMESPACE_URL, f'honim-sale-stock:{order.id}:{line.id}:{recipe_line.ingredient_id}')
        StockMovement.objects.create(
            branch=user.branch, ingredient=ingredients[recipe_line.ingredient_id], actor=user,
            key=key, request_hash=fingerprint({'order': order.id, 'line': line.id, 'ingredient': recipe_line.ingredient_id, 'quantity': str(quantity)}),
            kind='sale_consumption', quantity=quantity, date=timezone.localdate(),
            note=f'#{order.id} buyurtma · {line.name}',
        )
    audit(user, 'stock.sale_consumption', f'#{order.id} buyurtma retsept bo‘yicha ombordan ayrildi')


@transaction.atomic
def create_order(user, data):
    previous = existing(Order, user, data)
    if previous:
        return previous
    dishes = {dish.id: dish for dish in Dish.objects.select_for_update().filter(branch=user.branch, archived=False, available=True, id__in=[line['dish'] for line in data['lines']])}
    if len(dishes) != len(data['lines']):
        raise ValidationError('Ayrim taomlar mavjud emas. Menyuni yangilang.')
    total = sum((dishes[line['dish']].price * line['quantity'] for line in data['lines']), Decimal('0'))
    if total > Decimal('999999999999.99'):
        raise ValidationError('Buyurtma summasi juda katta.')
    paid = bool(data['payment_method'])
    recipes = _recipes_for_dishes(user.branch, dishes)
    order = Order.objects.create(branch=user.branch, cashier=user, key=data['key'], request_hash=fingerprint(data), table=data['table'], waiter=data['waiter'], total=total, status='paid' if paid else 'open', payment_method=data['payment_method'], paid_at=timezone.now() if paid else None)
    for line in data['lines']:
        dish = dishes[line['dish']]
        recipe = recipes.get(dish.id)
        unit_cost = (recipe_cost(recipe) / recipe.yield_quantity).quantize(Decimal('0.01')) if recipe else Decimal('0')
        OrderLine.objects.create(order=order, dish=dish, name=dish.name, price=dish.price, quantity=line['quantity'], note=line['note'], cost_per_unit=unit_cost, cost_total=unit_cost * line['quantity'])
    if paid:
        consume_order_stock(user, order)
    audit(user, 'order.create', f'#{order.id} · {total} so‘m')
    return order


@transaction.atomic
def pay_order(user, order_id, method):
    order = Order.objects.select_for_update().filter(branch=user.branch, id=order_id).first()
    if not order:
        raise ValidationError('Buyurtma topilmadi.')
    if order.status == 'paid':
        if order.payment_method != method:
            raise Conflict('Buyurtma boshqa usul bilan to‘langan.')
        return order
    consume_order_stock(user, order)
    changed = Order.objects.filter(pk=order.pk, status='open').update(status='paid', payment_method=method, paid_at=timezone.now())
    if not changed:
        raise Conflict()
    order.refresh_from_db()
    audit(user, 'order.pay', f'#{order.id} · {method}')
    return order


@transaction.atomic
def create_expense(user, data):
    previous = existing(Expense, user, data)
    if previous:
        return previous
    obj = Expense.objects.create(branch=user.branch, actor=user, request_hash=fingerprint(data), **data)
    audit(user, 'expense.create', f'{obj.purpose} · {obj.amount} so‘m')
    return obj


@transaction.atomic
def move_stock(user, data):
    previous = existing(StockMovement, user, data)
    if previous:
        return previous
    stock = Ingredient.objects.select_for_update().filter(branch=user.branch, pk=data['ingredient']).first()
    if not stock:
        raise ValidationError('Mahsulot topilmadi.')
    quantity = data['quantity']
    if stock.unit == 'dona' and quantity != quantity.to_integral_value():
        raise ValidationError('Dona butun son bo‘lishi kerak.')
    if data['kind'] == 'consumption':
        changed = Ingredient.objects.filter(pk=stock.pk, quantity__gte=quantity).update(quantity=F('quantity') - quantity)
        if not changed:
            raise ValidationError('Omborda yetarli mahsulot yo‘q.')
    else:
        if stock.quantity + quantity > Decimal('99999999999.999'):
            raise ValidationError('Qoldiq chegaradan oshadi.')
        Ingredient.objects.filter(pk=stock.pk).update(quantity=F('quantity') + quantity)
    obj = StockMovement.objects.create(branch=user.branch, actor=user, ingredient=stock, request_hash=fingerprint(data), **{key: value for key, value in data.items() if key != 'ingredient'})
    audit(user, f'stock.{obj.kind}', f'{stock.name} · {quantity} {stock.unit}')
    return obj
