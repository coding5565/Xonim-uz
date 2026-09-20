"""Bugun tayyorlangan taomlar va ularning qoldig'i.

    Qoldiq = bugun tayyorlangan − bugun sotilgan

Sotilgan deb nima sanaladi:
  · ochiq hisob — ovqat allaqachon oshxonaga ketgan, sanalmasa ortiqcha sotilardi;
  · to'langan — ovqat berilgan;
  · qaytarilgan — pul qaytdi, lekin PORSIYA qaytmadi, shuning uchun sanaladi;
  · bekor qilingan — oshxonaga «BEKOR» taloni ketgan, sanalmaydi.

Tayyor bo'lmagan taomni sotib BO'LMAYDI. Oshxona buyurtma kelgach pishirmaydi
— u ertalab partiya qilib pishiradi, talon esa «shuni yig'inglar» degan
signal. Demak tayyori yo'q taom uchun yig'adigan narsa ham yo'q. Miqdori
kiritilmagan taom ham sotilmaydi: kiritilmagan degani «yo'q» degani.

Diqqat: bu qoida kassirning ertalabki kiritishiga bog'liq. Kiritmasa sotuv
to'xtaydi — xabar aynan nima qilish kerakligini aytadi.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Dish
from core.i18n import _
from users.permissions import OwnerOnly, SalesOnly

from .models import DishPrep, OrderLine
from .money import day_window
from .services import audit_many

# Qoldiq tayyorlanganning shu ulushiga tushsa «kam qoldi» deb belgilanadi.
# Mutanosib: 20 ta pishirilgan bo'lsa 4 tada, 5 ta bo'lsa 1 tada ogohlantiradi.
LOW_SHARE = Decimal('0.2')
# Porsiya sotilgan deb sanaladigan hisob holatlari.
CONSUMING_STATUSES = ['open', 'paid', 'refunded']


def low_at(prepared):
    """Necha donada ogohlantirish boshlanadi."""
    return max(1, int(prepared * LOW_SHARE))


def sold_today(branch, day):
    """Har taomdan bugun nechta ketgani."""
    since, until = day_window(day)
    rows = OrderLine.objects.filter(
        order__branch=branch,
        order__created_at__gte=since,
        order__created_at__lt=until,
        order__status__in=CONSUMING_STATUSES,
    ).values('dish_id').annotate(total=Sum('quantity')).order_by()
    return {row['dish_id']: row['total'] or 0 for row in rows}


def prepared_today(branch, day):
    rows = DishPrep.objects.filter(branch=branch, date=day).values('dish_id').annotate(
        total=Sum('quantity'),
    ).order_by()
    return {row['dish_id']: row['total'] or 0 for row in rows}


def stock_status(branch, day=None):
    """Bugungi holat: nima tayyorlandi, nechtasi ketdi, nechtasi qoldi."""
    day = day or timezone.localdate()
    prepared = prepared_today(branch, day)
    sold = sold_today(branch, day)
    # Arxivlangan taom ham ro'yxatda qoladi, agar bugun u tayyorlangan yoki
    # sotilgan bo'lsa: aks holda kun o'rtasida menyudan olib tashlangan taom
    # bilan birga uning bugungi porsiyalari ham hisobdan yo'qolardi.
    touched = set(prepared) | set(sold)
    dishes = {
        dish.id: dish
        for dish in Dish.objects.filter(branch=branch).filter(Q(archived=False) | Q(id__in=touched))
    }

    rows = []
    for dish_id, dish in dishes.items():
        made = prepared.get(dish_id, 0)
        gone = sold.get(dish_id, 0)
        left = made - gone
        tracked = dish_id in prepared
        rows.append({
            'dish': dish_id,
            'name': dish.name,
            'prepared': made,
            'sold': gone,
            'remaining': left,
            # Miqdori kiritilmagan taom cheklanmaydi.
            'tracked': tracked,
            'out': tracked and left <= 0,
            'low': tracked and 0 < left <= low_at(made),
            # Chegara kassa ekraniga ham kerak: u savatdagi miqdorni hisobga
            # olib qayta baholaydi. Shu sababli 20% qoidasi faqat shu yerda
            # yoziladi, mijoz tomonida takrorlanmaydi.
            'warn_at': low_at(made) if tracked else 0,
        })
    rows.sort(key=lambda row: (not row['tracked'], row['remaining'], row['name']))
    tracked_rows = [row for row in rows if row['tracked']]
    return {
        'date': day,
        'summary': {
            'tracked': len(tracked_rows),
            'out': sum(1 for row in tracked_rows if row['out']),
            'low': sum(1 for row in tracked_rows if row['low']),
            'prepared': sum(row['prepared'] for row in tracked_rows),
            'sold': sum(row['sold'] for row in tracked_rows),
            'remaining': sum(max(row['remaining'], 0) for row in tracked_rows),
        },
        'dishes': rows,
    }


class PrepLineInput(serializers.Serializer):
    dish = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=9999)
    note = serializers.CharField(max_length=200, allow_blank=True, default='')


class DishPrepInput(serializers.Serializer):
    lines = PrepLineInput(many=True, allow_empty=False)

    def validate_lines(self, lines):
        if len({line['dish'] for line in lines}) != len(lines):
            raise serializers.ValidationError(_('Bir taomni faqat bir marta kiriting.'))
        if len(lines) > 100:
            raise serializers.ValidationError(_('Bir martada ko‘pi bilan 100 ta taom.'))
        return lines


@transaction.atomic
def record_prep(user, lines):
    """Tayyorlangan miqdorni yozadi. Qayta yuborilsa qo'shiladi, almashmaydi."""
    day = timezone.localdate()
    wanted = {line['dish']: line for line in lines}
    dishes = {
        dish.id: dish
        for dish in Dish.objects.filter(branch=user.branch, archived=False, id__in=wanted)
    }
    if len(dishes) != len(wanted):
        raise serializers.ValidationError({'lines': _('Ayrim taomlar topilmadi.')})

    events = []
    for dish_id, line in wanted.items():
        dish = dishes[dish_id]
        DishPrep.objects.create(
            branch=user.branch, dish=dish, actor=user, date=day,
            quantity=line['quantity'], note=line['note'],
        )
        events.append(('prep.record', f'{dish.name} · +{line["quantity"]} porsiya tayyorlandi'))
    audit_many(user, events)
    return stock_status(user.branch, day)


def check_prepared(branch, wanted):
    """Tayyor bo'lmagan taomlar ro'yxatini qaytaradi.

    `wanted` — {taom_id: miqdor}. Bo'sh ro'yxat qaytsa hammasi tayyor.
    Qoldiq sotuvdan OLDIN tekshiriladi, shuning uchun hisobdagi qatorlar
    bu yerga kirmaydi.
    """
    status = stock_status(branch)
    by_dish = {row['dish']: row for row in status['dishes']}
    blocked = []
    for dish_id, quantity in wanted.items():
        row = by_dish.get(dish_id)
        if not row:
            continue
        if not row['tracked']:
            blocked.append(_('{name} — bugun tayyorlanmagan').format(name=row['name']))
        elif row['remaining'] < quantity:
            blocked.append(_('{name} — {count} ta qoldi').format(
                name=row['name'], count=max(row['remaining'], 0)))
    return blocked


def require_prepared(branch, wanted):
    """Tayyor bo'lmasa sotuvni to'xtatadi."""
    blocked = check_prepared(branch, wanted)
    if blocked:
        raise serializers.ValidationError({'prepared': _(
            'Bu taomlar tayyor emas: {dishes}. «Tayyor taomlar» bo‘limida '
            'bugun nechta tayyorlanganini kiriting.',
        ).format(dishes=', '.join(blocked))})


def note_oversell(user, order):
    """Qoldiqdan ko'p sotilgan bo'lsa jurnalga yozadi.

    Sotuv to'xtatilmaydi — oshxona qo'shimcha pishirgan bo'lishi mumkin va
    kiritish kechikadi. Lekin egasi buni ko'rib turishi kerak.
    """
    status = stock_status(user.branch)
    by_dish = {row['dish']: row for row in status['dishes']}
    events = []
    for line in order.lines.all():
        row = by_dish.get(line.dish_id)
        if row and row['tracked'] and row['remaining'] < 0:
            events.append((
                'prep.oversell',
                f'{line.name} · tayyorlangan {row["prepared"]}, sotilgan {row["sold"]} · '
                f'{abs(row["remaining"])} porsiya ortiqcha',
            ))
    audit_many(user, events)


class DishPrepView(APIView):
    """Kassir tayyorlangan miqdorni kiritadi va qoldiqni ko‘radi."""

    permission_classes = [SalesOnly]

    def get(self, request):
        return Response(stock_status(request.user.branch))

    def post(self, request):
        data = DishPrepInput(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(record_prep(request.user, data.validated_data['lines']), status=201)


class DishPrepRowView(APIView):
    """Noto‘g‘ri kiritilgan tayyorlash yozuvini olib tashlaydi.

    Yozuvlar qo‘shilib boradi va manfiy miqdor kiritib bo‘lmaydi, shuning
    uchun «20 o‘rniga 200» xatosini tuzatishning boshqa yo‘li yo‘q edi —
    kun oxirigacha qoldiq soxta bo‘lib turardi.

    Faqat BUGUNGI yozuv o‘chiriladi: o‘tgan kunning tayyorlash tarixi
    hisobotlarga kirgan va uni qayta yozish nazoratni buzardi.
    """

    permission_classes = [SalesOnly]

    @transaction.atomic
    def delete(self, request, pk):
        day = timezone.localdate()
        row = DishPrep.objects.select_related('dish').filter(
            branch=request.user.branch, pk=pk, date=day,
        ).first()
        if not row:
            raise serializers.ValidationError(_('Bugungi yozuvlar orasida bunday qator yo‘q.'))
        audit_many(request.user, [(
            'prep.remove',
            f'{row.dish.name} · −{row.quantity} porsiya · yozuv o‘chirildi',
        )])
        row.delete()
        return Response(stock_status(request.user.branch, day))


class DishPrepHistoryView(APIView):
    """Bugun kim nima kiritgani — kassirga ham, egasiga ham."""

    permission_classes = [SalesOnly]

    def get(self, request):
        day = timezone.localdate()
        rows = DishPrep.objects.filter(branch=request.user.branch, date=day).select_related('dish', 'actor')
        return Response({
            'date': day,
            'rows': [{
                'id': row.id,
                'dish': row.dish_id,
                'name': row.dish.name,
                'quantity': row.quantity,
                'note': row.note,
                'actor': row.actor.first_name or row.actor.username,
                'created_at': row.created_at,
            } for row in rows],
        })


class DishPrepLeftoverView(APIView):
    """Egasi uchun: bugun nima pishirildi va nechtasi sotilmay qoldi."""

    permission_classes = [OwnerOnly]

    def get(self, request):
        status = stock_status(request.user.branch)
        leftovers = [row for row in status['dishes'] if row['tracked'] and row['remaining'] > 0]
        return Response({
            'date': status['date'],
            'summary': status['summary'],
            'leftovers': sorted(leftovers, key=lambda row: row['remaining'], reverse=True),
        })
