"""Hamkorlar: maktab va universitetga taom jo'natish va hisob-kitob.

Oqim bitta kun ichida ketadi:

    ertalab   — taom jo'natiladi, hamkor narxida. Holat «Jo'natildi»;
    kechqurun — hamkor nechtasi sotilganini aytadi. Shunda qarz ma'lum
                bo'ladi va holat «Hisobot berildi» ga o'tadi;
    pul       — to'liq berilsa «Yopildi», kam berilsa qarz qolib turadi.

Uchta qoida butun bo'limni ushlab turadi:

1. Ombor JO'NATISH paytida ayriladi. Go'sht oshxonadan chiqib ketgan va
   uni keyingi mijozga sarflab bo'lmaydi — maktab sotdimi yoki yo'qmi,
   bu masalliqqa aloqasi yo'q. Tannarx ham shu kunga yoziladi.

2. Tushum HISOBOT bilan tug'iladi, lekin JO'NATMA kuniga yoziladi. Ovqat
   dushanba chiqqan bo'lsa foyda ham dushanbaniki: aks holda dushanba
   sof xarajat, payshanba esa sof foyda bo'lib ko'rinardi — ikkala kun
   ham yolg'on.

3. Tayyor taomlar qoldig'iga TEGILMAYDI. Bu ovqat alohida pishiriladi;
   shu sababli jo'natma OrderLine emas, o'z jadvalida yoziladi va
   `require_prepared` bu yo'lda ataylab chaqirilmaydi.

Sotilmagan porsiya hech qayerga qaytmaydi: tannarxi qoladi, tushumi yo'q.
Maktabdan sovigan porsiya qaytadi, un bilan go'sht emas — masalliqni
omborga qaytarish omborni yolg'on qilardi. Egasi buni aynan shunday
ko'rishi kerak, chunki bu «ertaga kamroq yuboring» degan signal.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Min, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Dish
from core.i18n import _
from users.permissions import OwnerOnly, SalesOnly

from .models import (
    PARTNER_KIND_LABELS,
    PARTNER_KINDS,
    PARTNER_PAYMENT_METHODS,
    PARTNER_STATUS_LABELS,
    Partner,
    PartnerDelivery,
    PartnerDeliveryLine,
    PartnerPrice,
    PartnerSettlement,
    ShiftClose,
)
from .money import ZERO, money
from .services import (
    Conflict,
    audit,
    consume_delivery_stock,
    existing,
    fingerprint,
    recipe_cost,
    restore_delivery_stock,
    safely,
)
from .services import _recipes_for_dishes as recipes_for

MAX_LINES = 100


def partner_books(branch):
    """Har bir hamkorning umrlik hisobi: qarz va tushgan pul.

    Ikkala yig'indi ALOHIDA so'rov bilan olinadi — bitta so'rovda ikkita
    jadval qo'shilsa qatorlar ko'payib, summalar bir necha barobar chiqib
    ketardi. Bu Django agregatlaridagi eng keng tarqalgan tuzoq va
    `waiters.waiter_books` da ham shu sabab shunday yozilgan.
    """
    due = {
        row['partner']: row['total']
        for row in PartnerDelivery.objects.filter(branch=branch).exclude(status='cancelled')
        .values('partner').annotate(total=Coalesce(Sum('due_total'), ZERO)).order_by()
    }
    received = {
        row['partner']: row['total']
        for row in PartnerSettlement.objects.filter(branch=branch, voided_at__isnull=True)
        .values('partner').annotate(total=Coalesce(Sum('amount'), ZERO)).order_by()
    }
    return due, received


def line_payload(line):
    return {
        'id': line.id,
        'dish': line.dish_id,
        'name': line.name,
        'price': money(line.price),
        'menu_price': money(line.menu_price),
        'quantity': line.quantity,
        'sold': line.sold_quantity,
        'unsold': line.unsold_quantity,
        'cost_total': money(line.cost_total),
        'value': money(line.price * line.quantity),
        'earned': money(line.price * line.sold_quantity),
    }


def delivery_payload(delivery, warnings=None):
    return {
        'id': delivery.id,
        'partner': delivery.partner_id,
        'partner_name': delivery.partner.name,
        'date': delivery.date,
        'status': delivery.status,
        'status_label': PARTNER_STATUS_LABELS.get(delivery.status, delivery.status),
        'total': money(delivery.total),
        'cost_total': money(delivery.cost_total),
        'due_total': money(delivery.due_total),
        'settled_total': money(delivery.settled_total),
        'remaining': money(delivery.remaining),
        'note': delivery.note,
        'created_at': delivery.created_at,
        'reported_at': delivery.reported_at,
        'closed_at': delivery.closed_at,
        'cancel_reason': delivery.cancel_reason,
        'actor_name': delivery.actor.first_name or delivery.actor.username,
        'lines': [line_payload(line) for line in delivery.lines.all()],
        'settlements': [{
            'id': item.id,
            'amount': money(item.amount),
            'payment_method': item.payment_method,
            'paid_on': item.paid_on,
            'note': item.note,
            'voided_at': item.voided_at,
            'void_reason': item.void_reason,
        } for item in delivery.settlements.all() if item.voided_at is None],
        'warnings': warnings or [],
    }


def deliveries_for(branch, **filters):
    return (
        PartnerDelivery.objects.filter(branch=branch, **filters)
        .select_related('partner', 'actor')
        .prefetch_related('lines', 'settlements')
    )


# --- Hamkorlar ro'yxati va shartnoma narxlari ----------------------------

class PartnerInput(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    kind = serializers.ChoiceField(choices=[key for key, _label in PARTNER_KINDS], default='school')
    contact = serializers.CharField(max_length=80, allow_blank=True, default='')
    phone = serializers.CharField(max_length=30, allow_blank=True, default='')
    address = serializers.CharField(max_length=200, allow_blank=True, default='')
    note = serializers.CharField(max_length=300, allow_blank=True, default='')
    active = serializers.BooleanField(default=True)


def price_rows(partner):
    return [{
        'dish': item.dish_id,
        'dish_name': item.dish.name,
        'price': money(item.price),
        'menu_price': money(item.dish.price),
        'archived': item.dish.archived,
    } for item in partner.prices.select_related('dish')]


def partner_payload(partner, due=None, received=None):
    owed = (due or {}).get(partner.id, ZERO) - (received or {}).get(partner.id, ZERO)
    return {
        'id': partner.id,
        'name': partner.name,
        'kind': partner.kind,
        'kind_label': PARTNER_KIND_LABELS.get(partner.kind, partner.kind),
        'contact': partner.contact,
        'phone': partner.phone,
        'address': partner.address,
        'note': partner.note,
        'active': partner.active,
        'debt': money(owed),
        'prices': price_rows(partner),
    }


class PartnerListView(APIView):
    """Hamkorlar ro'yxati. Narxlar ham shu yerda keladi.

    Narxlar ataylab kassirga ochiq ro'yxatda: jo'natish oynasi aynan
    shulardan chiziladi va alohida superadmin endpointidan olinsa, kuniga
    ikki marta ishlatadigan odam uchun sahifa ochilmay qolardi. Yozish esa
    superadminda qoladi.
    """

    permission_classes = [SalesOnly]

    def get(self, request):
        due, received = partner_books(request.user.branch)
        partners = Partner.objects.filter(branch=request.user.branch).prefetch_related('prices__dish')
        return Response([partner_payload(item, due, received) for item in partners])

    def post(self, request):
        if request.user.role != 'owner':
            return Response({'detail': _('Bu amal faqat superadminga ochiq.')}, status=403)
        data = PartnerInput(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data
        if Partner.objects.filter(branch=request.user.branch, name__iexact=fields['name']).exists():
            raise serializers.ValidationError({'name': _('Bu nomli hamkor allaqachon bor.')})
        partner = Partner.objects.create(branch=request.user.branch, **fields)
        audit(request.user, 'partner.create', f'{partner.name} · {PARTNER_KIND_LABELS.get(partner.kind, "")}')
        return Response(partner_payload(partner), status=201)


class PartnerDetailView(APIView):
    """Hamkor kartasini o'zgartirish va faolsizlantirish — superadmin ishi."""

    permission_classes = [OwnerOnly]

    def partner_of(self, request, pk):
        partner = Partner.objects.filter(branch=request.user.branch, pk=pk).first()
        if not partner:
            raise serializers.ValidationError(_('Hamkor topilmadi.'))
        return partner

    def patch(self, request, pk):
        partner = self.partner_of(request, pk)
        data = PartnerInput(data=request.data, partial=True)
        data.is_valid(raise_exception=True)
        fields = data.validated_data
        name = fields.get('name')
        if name and Partner.objects.filter(
                branch=request.user.branch, name__iexact=name).exclude(pk=partner.pk).exists():
            raise serializers.ValidationError({'name': _('Bu nomli hamkor allaqachon bor.')})
        # Yopilmagan jo'natmasi bor hamkorni faolsizlantirib bo'lmaydi:
        # qarz ekrandan yo'qolib, hech kim uni so'ramay qolardi.
        if fields.get('active') is False and self.has_open_work(partner):
            raise serializers.ValidationError(
                {'active': _('Bu hamkorda yopilmagan jo‘natma bor. Avval hisobni yoping.')})
        changed = []
        for field, value in fields.items():
            if getattr(partner, field) != value:
                setattr(partner, field, value)
                changed.append(field)
        if changed:
            partner.save(update_fields=changed)
            audit(request.user, 'partner.update', f'{partner.name} · {", ".join(changed)}')
        due, received = partner_books(request.user.branch)
        return Response(partner_payload(partner, due, received))

    def delete(self, request, pk):
        partner = self.partner_of(request, pk)
        if self.has_open_work(partner):
            raise serializers.ValidationError(
                _('Bu hamkorda yopilmagan jo‘natma bor. Avval hisobni yoping.'))
        partner.active = False
        partner.save(update_fields=['active'])
        audit(request.user, 'partner.update', f'{partner.name} · faolsizlantirildi')
        return Response({'detail': _('Hamkor ro‘yxatdan olindi.')})

    @staticmethod
    def has_open_work(partner):
        return partner.deliveries.exclude(status__in=['settled', 'cancelled']).exists()


class PriceRowInput(serializers.Serializer):
    dish = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('1'))


class PartnerPricesInput(serializers.Serializer):
    rows = PriceRowInput(many=True, allow_empty=True)

    def validate_rows(self, rows):
        if len({row['dish'] for row in rows}) != len(rows):
            raise serializers.ValidationError(_('Bir taomni faqat bir marta kiriting.'))
        if len(rows) > MAX_LINES:
            raise serializers.ValidationError(_('Bir martada ko‘pi bilan 100 ta taom.'))
        return rows


class PartnerPricesView(APIView):
    """Shartnoma narxlari. Ko'rish kassirga, yozish superadminga.

    Narx istalgan kuni o'zgartiriladi, lekin o'zgarish faqat KEYINGI
    jo'natmalarga tegadi: har bir jo'natma o'z narxini qatorga muzlatib
    oladi.
    """

    permission_classes = [SalesOnly]

    def get(self, request, pk):
        partner = Partner.objects.filter(branch=request.user.branch, pk=pk).first()
        if not partner:
            raise serializers.ValidationError(_('Hamkor topilmadi.'))
        return Response(price_rows(partner))

    @transaction.atomic
    def put(self, request, pk):
        if request.user.role != 'owner':
            return Response({'detail': _('Bu amal faqat superadminga ochiq.')}, status=403)
        partner = Partner.objects.filter(branch=request.user.branch, pk=pk).first()
        if not partner:
            raise serializers.ValidationError(_('Hamkor topilmadi.'))
        data = PartnerPricesInput(data=request.data)
        data.is_valid(raise_exception=True)
        rows = data.validated_data['rows']

        dishes = {
            dish.id: dish
            for dish in Dish.objects.filter(branch=request.user.branch, id__in=[row['dish'] for row in rows])
        }
        if len(dishes) != len(rows):
            raise serializers.ValidationError({'rows': _('Ayrim taomlar topilmadi.')})

        warnings = []
        PartnerPrice.objects.filter(partner=partner).delete()
        for row in rows:
            dish = dishes[row['dish']]
            PartnerPrice.objects.create(
                branch=request.user.branch, partner=partner, dish=dish, price=row['price'])
            # Hamkor narxi menyudan qimmat bo'lishi mumkin, lekin bu deyarli
            # doim xato: shartnomaning ma'nosi arzonroq berish edi.
            if row['price'] > dish.price:
                warnings.append(_('«{name}» narxi menyu narxidan yuqori — tekshiring.').format(name=dish.name))
        audit(request.user, 'partner.price', f'{partner.name} · {len(rows)} ta taom narxi yangilandi')
        return Response({'rows': price_rows(partner), 'warnings': warnings})


# --- Jo'natish -----------------------------------------------------------

class DeliveryLineInput(serializers.Serializer):
    dish = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=9999)


class DeliveryInput(serializers.Serializer):
    key = serializers.UUIDField()
    partner = serializers.IntegerField(min_value=1)
    note = serializers.CharField(max_length=250, allow_blank=True, default='')
    lines = DeliveryLineInput(many=True, allow_empty=False)

    def validate_lines(self, lines):
        if len({line['dish'] for line in lines}) != len(lines):
            raise serializers.ValidationError(_('Bir taomni faqat bir marta kiriting.'))
        if len(lines) > MAX_LINES:
            raise serializers.ValidationError(_('Bir martada ko‘pi bilan 100 ta taom.'))
        return lines


def send_delivery(user, data):
    """Jo'natmani yozadi va masalliqni ombordan ayiradi."""
    previous = existing(PartnerDelivery, user, data)
    if previous:
        return previous, [], False
    return safely(_record_delivery, user, data)


@transaction.atomic
def _record_delivery(user, data):
    partner = Partner.objects.filter(branch=user.branch, pk=data['partner']).first()
    if not partner:
        raise serializers.ValidationError({'partner': _('Hamkor topilmadi.')})
    if not partner.active:
        raise serializers.ValidationError(
            {'partner': _('Bu hamkor faolsizlantirilgan — unga taom jo‘natilmaydi.')})

    wanted = {line['dish']: line['quantity'] for line in data['lines']}
    dishes = {
        dish.id: dish
        for dish in Dish.objects.filter(branch=user.branch, archived=False, id__in=wanted)
    }
    if len(dishes) != len(wanted):
        raise serializers.ValidationError({'lines': _('Ayrim taomlar mavjud emas. Menyuni yangilang.')})

    prices = {
        item.dish_id: item.price
        for item in PartnerPrice.objects.filter(partner=partner, dish_id__in=wanted)
    }
    missing = [dishes[dish_id].name for dish_id in wanted if dish_id not in prices]
    if missing:
        # Menyu narxi bilan jo'natib yuborish eng qimmat xato bo'lardi,
        # shuning uchun server hech qachon Dish.price ga qaramaydi.
        raise serializers.ValidationError({'lines': _(
            '«{name}» uchun hamkor narxi belgilanmagan — shu sababli jo‘natib bo‘lmaydi. '
            'Narxni shartnoma bo‘yicha superadmin kiritadi.').format(name=missing[0])})

    day = timezone.localdate()
    warnings = []
    if PartnerDelivery.objects.filter(
            branch=user.branch, partner=partner, date=day).exclude(status='cancelled').exists():
        warnings.append(_('Bugun bu hamkorga allaqachon jo‘natilgan. Ikkinchi mashina bo‘lsa davom eting.'))

    # Summalar AVVAL hisoblanadi: jo'natma nol summa bilan yaratilsa
    # «summa noldan katta» cheklovi darhol ishlab ketardi.
    recipes = recipes_for(user.branch, wanted)
    planned = []
    total = Decimal('0')
    cost_total = Decimal('0')
    for dish_id, quantity in wanted.items():
        dish = dishes[dish_id]
        recipe = recipes.get(dish_id)
        unit_cost = (recipe_cost(recipe) / recipe.yield_quantity).quantize(Decimal('0.01')) if recipe else Decimal('0')
        price = prices[dish_id]
        line_cost = unit_cost * quantity
        planned.append((dish, price, quantity, unit_cost, line_cost))
        total += price * quantity
        cost_total += line_cost
        if unit_cost and price < unit_cost:
            warnings.append(_('Bu narx tannarxdan past: «{name}» har porsiyada {amount} so‘m zarar.').format(
                name=dish.name, amount=money(unit_cost - price)))

    delivery = PartnerDelivery.objects.create(
        branch=user.branch, partner=partner, actor=user,
        key=data['key'], request_hash=fingerprint(data),
        date=day, total=total, cost_total=cost_total, note=data['note'],
    )
    for dish, price, quantity, unit_cost, line_cost in planned:
        PartnerDeliveryLine.objects.create(
            delivery=delivery, dish=dish, name=dish.name, price=price, menu_price=dish.price,
            quantity=quantity, cost_per_unit=unit_cost, cost_total=line_cost,
        )
    # Ombor shu yerda ayriladi. `require_prepared` ataylab chaqirilmaydi:
    # bu ovqat alohida pishiriladi va tayyor taomlar qoldig'iga tegmaydi.
    consume_delivery_stock(user, delivery)
    audit(user, 'partner.send',
          f'{partner.name} · {sum(wanted.values())} porsiya · {total} so‘m')
    return delivery, warnings, True


# --- Hisobot va to'lov ---------------------------------------------------

class ReportLineInput(serializers.Serializer):
    line = serializers.IntegerField(min_value=1)
    sold = serializers.IntegerField(min_value=0, max_value=9999)


class ReportInput(serializers.Serializer):
    lines = ReportLineInput(many=True, allow_empty=False)

    def validate_lines(self, lines):
        if len({row['line'] for row in lines}) != len(lines):
            raise serializers.ValidationError(_('Bir qatorni faqat bir marta kiriting.'))
        return lines


def close_or_open(delivery):
    """Holatni raqamlardan keltirib chiqaradi — hech qachon qo'lda yozilmaydi."""
    if delivery.status == 'cancelled':
        return
    if delivery.reported_at is None:
        delivery.status = 'sent'
        delivery.closed_at = None
        return
    if delivery.settled_total >= delivery.due_total:
        delivery.status = 'settled'
        delivery.closed_at = delivery.closed_at or timezone.now()
    else:
        delivery.status = 'reported'
        delivery.closed_at = None


@transaction.atomic
def report_delivery(user, delivery_id, data):
    """Nechtasi sotilganini yozadi va qarzni hisoblaydi.

    Miqdor USTIGA yoziladi, qo'shilmaydi: «nechta sotildi» — bu fakt, har
    safar qayta aytilishi mumkin. Shu sababli ikki marta yuborilgan bir xil
    hisobot hech narsani o'zgartirmaydi.
    """
    delivery = PartnerDelivery.objects.select_for_update().filter(
        branch=user.branch, pk=delivery_id).first()
    if not delivery:
        raise serializers.ValidationError(_('Jo‘natma topilmadi.'))
    if delivery.status == 'cancelled':
        raise Conflict(_('Bekor qilingan jo‘natma bo‘yicha hisobot qabul qilinmaydi.'))

    lines = {line.id: line for line in delivery.lines.all()}
    reported = {row['line']: row['sold'] for row in data['lines']}
    if set(reported) - set(lines):
        raise serializers.ValidationError({'lines': _('Bu qator boshqa jo‘natmaga tegishli.')})
    if set(lines) - set(reported):
        raise serializers.ValidationError({'lines': _('Har bir qator uchun nechta sotilgani kiritilsin.')})

    due = Decimal('0')
    for line_id, sold in reported.items():
        line = lines[line_id]
        if sold > line.quantity:
            raise serializers.ValidationError({'lines': _(
                '«{name}» — {sent} ta jo‘natilgan, {sold} ta sotilgan deb bo‘lmaydi.').format(
                    name=line.name, sent=line.quantity, sold=sold)})
        line.sold_quantity = sold
        due += line.price * sold
    # Olingan puldan pastga tushirish hisobni manfiyga olib borardi.
    if due < delivery.settled_total:
        raise Conflict(_(
            'Bu jo‘natma uchun allaqachon {paid} so‘m olingan — hisobotni undan pastga '
            'tushirib bo‘lmaydi. Avval to‘lovni bekor qiling.').format(paid=money(delivery.settled_total)))

    PartnerDeliveryLine.objects.bulk_update(lines.values(), ['sold_quantity'])
    delivery.due_total = due
    delivery.reported_at = delivery.reported_at or timezone.now()
    delivery.reported_by = delivery.reported_by or user
    close_or_open(delivery)
    delivery.save(update_fields=['due_total', 'reported_at', 'reported_by', 'status', 'closed_at'])
    audit(user, 'partner.report',
          f'{delivery.partner.name} · H#{delivery.id} · {sum(reported.values())} ta sotildi · {due} so‘m')
    return delivery


class SettleInput(serializers.Serializer):
    key = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('1'))
    payment_method = serializers.ChoiceField(choices=[key for key, _label in PARTNER_PAYMENT_METHODS])
    paid_on = serializers.DateField()
    note = serializers.CharField(max_length=250, allow_blank=True, default='')

    def validate_paid_on(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError(_('Kelajakdagi to‘lov sanasi mumkin emas.'))
        return value


@transaction.atomic
def settle_delivery(user, delivery_id, data):
    """Hamkordan kelgan pulni yozadi va jo'natmani yopadi."""
    again = PartnerSettlement.objects.filter(branch=user.branch, key=data['key']).first()
    if again:
        if again.delivery_id != delivery_id or again.amount != data['amount']:
            raise Conflict(_('Bir xil amal kaliti boshqa ma’lumot bilan yuborildi.'))
        return again.delivery, again, False

    delivery = PartnerDelivery.objects.select_for_update().filter(
        branch=user.branch, pk=delivery_id).first()
    if not delivery:
        raise serializers.ValidationError(_('Jo‘natma topilmadi.'))
    if delivery.status == 'cancelled':
        raise Conflict(_('Bekor qilingan jo‘natma bo‘yicha pul qabul qilinmaydi.'))
    if delivery.reported_at is None:
        raise Conflict(_('Avval nechtasi sotilganini kiriting — shundan keyin pul yoziladi.'))
    # Yopilgan kunga pul kiritib bo'lmaydi: kutilgan naqd o'sha kuni
    # muzlatilgan va farq abadiy qolib ketardi.
    if ShiftClose.objects.filter(branch=user.branch, date=data['paid_on']).exists():
        raise serializers.ValidationError({'paid_on': _(
            '{date} kuni allaqachon yopilgan — o‘sha kunga pul kiritib bo‘lmaydi.').format(
                date=data['paid_on'])})
    remaining = delivery.due_total - delivery.settled_total
    if data['amount'] > remaining:
        raise serializers.ValidationError({'amount': _(
            'Qolgan qarz {amount} so‘m — undan ko‘pini qabul qilib bo‘lmaydi.').format(
                amount=money(remaining))})

    settlement = PartnerSettlement.objects.create(
        branch=user.branch, partner=delivery.partner, delivery=delivery, actor=user,
        key=data['key'], request_hash=fingerprint({'delivery': delivery_id, 'amount': str(data['amount'])}),
        amount=data['amount'], payment_method=data['payment_method'],
        paid_on=data['paid_on'], note=data['note'],
    )
    delivery.settled_total += data['amount']
    close_or_open(delivery)
    delivery.save(update_fields=['settled_total', 'status', 'closed_at'])
    audit(user, 'partner.settle',
          f'{delivery.partner.name} · H#{delivery.id} · {settlement.amount} so‘m')
    return delivery, settlement, True


class VoidInput(serializers.Serializer):
    reason = serializers.CharField(max_length=200, min_length=3)


@transaction.atomic
def cancel_delivery(user, delivery_id, reason):
    """Jo'natmani bekor qiladi va masalliqni omborga qaytaradi.

    Faqat hisobot berilmaganida: ovqat hali sotilmagan, demak masalliqni
    qaytarish halol.
    """
    delivery = PartnerDelivery.objects.select_for_update().filter(
        branch=user.branch, pk=delivery_id).first()
    if not delivery:
        raise serializers.ValidationError(_('Jo‘natma topilmadi.'))
    if delivery.status == 'cancelled':
        raise Conflict(_('Bu jo‘natma allaqachon bekor qilingan.'))
    if delivery.reported_at is not None:
        raise Conflict(_('Hisobot berilgan jo‘natmani bekor qilib bo‘lmaydi. Hisobotni qaytadan kiriting.'))

    restore_delivery_stock(user, delivery)
    delivery.status = 'cancelled'
    delivery.cancel_reason = reason
    delivery.cancelled_at = timezone.now()
    delivery.cancelled_by = user
    delivery.save(update_fields=['status', 'cancel_reason', 'cancelled_at', 'cancelled_by'])
    audit(user, 'partner.cancel', f'{delivery.partner.name} · H#{delivery.id} · {reason}')
    return delivery


@transaction.atomic
def void_settlement(user, settlement_id, reason):
    """To'lovni bekor qiladi. O'chirmaydi — pul kelgani tarixda qoladi."""
    settlement = PartnerSettlement.objects.select_for_update().filter(
        branch=user.branch, pk=settlement_id).first()
    if not settlement:
        raise serializers.ValidationError(_('To‘lov topilmadi.'))
    if settlement.voided_at is not None:
        raise Conflict(_('Bu to‘lov allaqachon bekor qilingan.'))
    if ShiftClose.objects.filter(branch=user.branch, date=settlement.paid_on).exists():
        raise Conflict(_(
            '{date} kuni allaqachon yopilgan — o‘sha kundagi to‘lovni bekor qilib bo‘lmaydi.').format(
                date=settlement.paid_on))

    settlement.voided_at = timezone.now()
    settlement.voided_by = user
    settlement.void_reason = reason
    settlement.save(update_fields=['voided_at', 'voided_by', 'void_reason'])

    delivery = PartnerDelivery.objects.select_for_update().get(pk=settlement.delivery_id)
    delivery.settled_total -= settlement.amount
    close_or_open(delivery)
    delivery.save(update_fields=['settled_total', 'status', 'closed_at'])
    audit(user, 'partner.void', f'{settlement.partner.name} · {settlement.amount} so‘m · {reason}')
    return settlement


# --- Endpointlar ---------------------------------------------------------

class PartnerDeliveryView(APIView):
    """Jo'natma yozish va ro'yxatini ko'rish."""

    permission_classes = [SalesOnly]

    def get(self, request):
        rows = deliveries_for(request.user.branch)
        partner = request.query_params.get('partner')
        status = request.query_params.get('status')
        if partner:
            rows = rows.filter(partner_id=partner)
        if status:
            rows = rows.filter(status=status)
        return Response([delivery_payload(row) for row in rows[:200]])

    def post(self, request):
        data = DeliveryInput(data=request.data)
        data.is_valid(raise_exception=True)
        delivery, warnings, fresh = send_delivery(request.user, data.validated_data)
        return Response(delivery_payload(delivery, warnings), status=201 if fresh else 200)


class PartnerDeliveryReportView(APIView):
    permission_classes = [SalesOnly]

    def post(self, request, pk):
        data = ReportInput(data=request.data)
        data.is_valid(raise_exception=True)
        delivery = report_delivery(request.user, pk, data.validated_data)
        return Response(delivery_payload(delivery))


class PartnerDeliverySettleView(APIView):
    permission_classes = [SalesOnly]

    def post(self, request, pk):
        data = SettleInput(data=request.data)
        data.is_valid(raise_exception=True)
        delivery, _settlement, fresh = safely(settle_delivery, request.user, pk, data.validated_data)
        return Response(delivery_payload(delivery), status=201 if fresh else 200)


class PartnerDeliveryCancelView(APIView):
    permission_classes = [OwnerOnly]

    def post(self, request, pk):
        data = VoidInput(data=request.data)
        data.is_valid(raise_exception=True)
        delivery = cancel_delivery(request.user, pk, data.validated_data['reason'])
        return Response(delivery_payload(delivery))


class PartnerSettlementVoidView(APIView):
    permission_classes = [OwnerOnly]

    def post(self, request, pk):
        data = VoidInput(data=request.data)
        data.is_valid(raise_exception=True)
        settlement = void_settlement(request.user, pk, data.validated_data['reason'])
        return Response(delivery_payload(
            deliveries_for(request.user.branch, pk=settlement.delivery_id).first()))


class PartnerBoardFilters(serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    partner = serializers.IntegerField(min_value=1, required=False)

    def validate(self, attrs):
        today = timezone.localdate()
        attrs['end'] = attrs.get('end', today)
        attrs['start'] = attrs.get('start', attrs['end'])
        if attrs['start'] > attrs['end']:
            raise serializers.ValidationError(_('Boshlanish sanasi tugash sanasidan keyin bo‘lishi mumkin emas.'))
        return attrs


class PartnerBoardView(APIView):
    """Bo'limning bir sahifalik manzarasi: kim qancha qarz, bugun nima ketdi."""

    permission_classes = [SalesOnly]

    def get(self, request):
        filters = PartnerBoardFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        window = filters.validated_data
        branch = request.user.branch

        due, received = partner_books(branch)
        rows = deliveries_for(branch, date__gte=window['start'], date__lte=window['end'])
        if window.get('partner'):
            rows = rows.filter(partner_id=window['partner'])
        rows = list(rows)

        live = [row for row in rows if row.status != 'cancelled']
        pending = [row for row in live if row.status == 'sent']
        # Eng eski yopilmagan jo'natma yoshi: qarz qancha vaqtdan beri
        # turganini egasi bir qarashda ko'rishi kerak.
        oldest = {
            row['partner']: row['first']
            for row in PartnerDelivery.objects.filter(branch=branch)
            .exclude(status__in=['settled', 'cancelled'])
            .values('partner').annotate(first=Min('date')).order_by()
        }
        today = timezone.localdate()
        partners = []
        for partner in Partner.objects.filter(branch=branch).prefetch_related('prices__dish'):
            debt = due.get(partner.id, ZERO) - received.get(partner.id, ZERO)
            sent_rows = [row for row in live if row.partner_id == partner.id]
            first_open = oldest.get(partner.id)
            partners.append({
                **partner_payload(partner, due, received),
                'sent_value': money(sum((row.total for row in sent_rows), ZERO)),
                'sent_portions': sum(line.quantity for row in sent_rows for line in row.lines.all()),
                'pending_value': money(sum((row.total for row in sent_rows if row.status == 'sent'), ZERO)),
                'pending_count': sum(1 for row in sent_rows if row.status == 'sent'),
                'debt': money(debt),
                'oldest_days': (today - first_open).days if first_open else 0,
            })
        partners.sort(key=lambda row: (-Decimal(row['debt']), row['name']))

        settlements = PartnerSettlement.objects.filter(
            branch=branch, voided_at__isnull=True,
            paid_on__gte=window['start'], paid_on__lte=window['end'],
        ).aggregate(total=Coalesce(Sum('amount'), ZERO), count=Count('id'))
        reported = [row for row in live if row.status in ('reported', 'settled')]
        return Response({
            'filters': {'start': window['start'], 'end': window['end']},
            'summary': {
                'partners': len(partners),
                'sent_value': money(sum((row.total for row in live), ZERO)),
                'sent_portions': sum(line.quantity for row in live for line in row.lines.all()),
                'pending_value': money(sum((row.total for row in pending), ZERO)),
                'pending_count': len(pending),
                'due': money(sum((row.due_total for row in reported), ZERO)),
                'received': money(settlements['total']),
                'settlements': settlements['count'],
                # Umumiy qarz butun vaqt bo'yicha: o'tgan haftaning qarzi
                # bu hafta ko'rinmay qolmasligi kerak.
                'debt': money(sum(due.values(), ZERO) - sum(received.values(), ZERO)),
            },
            'partners': partners,
            'deliveries': [delivery_payload(row) for row in rows],
            'payment_methods': [
                {'method': key, 'label': label} for key, label in PARTNER_PAYMENT_METHODS
            ],
        })


class PartnerReportView(APIView):
    """Superadmin uchun: hamkorlar bo'yicha davr hisoboti."""

    permission_classes = [OwnerOnly]

    def get(self, request):
        filters = PartnerBoardFilters(data=request.query_params)
        filters.is_valid(raise_exception=True)
        window = filters.validated_data
        branch = request.user.branch
        due, received = partner_books(branch)

        rows = PartnerDelivery.objects.filter(
            branch=branch, date__gte=window['start'], date__lte=window['end'],
        ).exclude(status='cancelled').values('partner', 'partner__name').annotate(
            sent=Coalesce(Sum('total'), ZERO),
            cost=Coalesce(Sum('cost_total'), ZERO),
            earned=Coalesce(Sum('due_total', filter=Q(status__in=['reported', 'settled'])), ZERO),
            deliveries=Count('id'),
        ).order_by('-earned')
        return Response({
            'filters': {'start': window['start'], 'end': window['end']},
            'partners': [{
                'id': row['partner'],
                'name': row['partner__name'],
                'deliveries': row['deliveries'],
                'sent': money(row['sent']),
                'earned': money(row['earned']),
                'cost': money(row['cost']),
                'profit': money(row['earned'] - row['cost']),
                'debt': money(due.get(row['partner'], ZERO) - received.get(row['partner'], ZERO)),
            } for row in rows],
        })
