"""Tayyor porsiyalar hisobi va ularning qoldig'i.

    Qoldiq = shu kungacha kiritilgan − birinchi kiritishdan beri sotilgan

Qoldiq kundan kunga O'TADI: kechqurun ortib qolgan porsiyalar ertasi kuni
nolga aylanmaydi, chunki ular jismonan yo'qolmaydi. Kun boshidagi qoldiq
«kecha qolgan» ustunida alohida ko'rinadi, «bugun tayyorlandi» esa faqat
shu kungi kiritishni ko'rsatadi — ikkalasi aralashmaydi.

Nega birinchi kiritishdan beri: tizimda savdo tayyor taomlar hisobidan
oldin boshlangan. Butun tarix bo'yicha ayirilsa, hisobga olinmagan kunlarning
sotuvi qoldiqni minusga tushirib, hamma taomni «yo'q» qilib qo'yardi.
Shuning uchun har bir taom o'z hisobini birinchi kiritilgan kunidan
boshlaydi.

Ikkita guruh bor va ular boshqacha yuritiladi:
  · oshxona taomi — ertalab pishiriladi, tayyori tugasa SOTILMAYDI;
  · tayyor mahsulot — suv va ichimlik, tashqaridan tayyor keladi va hech
    qachon sotuvni to'xtatmaydi, qoldig'i faqat sanab boriladi.

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
from django.db.models import Min, Q, Sum
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.models import Dish, StockKind
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


def intake_upto(branch, day):
    """Shu kungacha kiritilgan jami — kirim va chiqim yozuvlari bilan birga."""
    rows = DishPrep.objects.filter(branch=branch, date__lte=day).values('dish_id').annotate(
        total=Sum('quantity'),
    ).order_by()
    return {row['dish_id']: row['total'] or 0 for row in rows}


def first_intake(branch, day):
    """Har bir taomning hisobi qaysi kundan boshlangani.

    `created_at` emas, `date`: partiya kechqurun kiritilib, ertangi kunga
    yozilishi mumkin — o'sha holda hisob yozuv yaratilgan kundan emas,
    ish kunidan boshlanishi kerak.
    """
    rows = DishPrep.objects.filter(branch=branch, date__lte=day).values('dish_id').annotate(
        first=Min('date'),
    ).order_by()
    return {row['dish_id']: row['first'] for row in rows}


def sold_since(branch, epochs, day):
    """Har bir taomdan o'z hisobi boshlangan kundan beri nechta ketgani.

    Taomlar odatda bir kunda hisobga olinadi, shuning uchun so'rov har bir
    boshlanish sanasi uchun bittadan bo'ladi — amalda bitta so'rov.
    """
    totals = {}
    by_epoch = {}
    for dish_id, start in epochs.items():
        by_epoch.setdefault(start, []).append(dish_id)
    for start, dish_ids in by_epoch.items():
        since, until = day_window(start, day)
        rows = OrderLine.objects.filter(
            order__branch=branch,
            order__created_at__gte=since,
            order__created_at__lt=until,
            order__status__in=CONSUMING_STATUSES,
            dish_id__in=dish_ids,
        ).values('dish_id').annotate(total=Sum('quantity')).order_by()
        for row in rows:
            totals[row['dish_id']] = row['total'] or 0
    return totals


def stock_status(branch, day=None):
    """Bugungi holat: nima tayyorlandi, nechtasi ketdi, nechtasi qoldi.

    Qoldiq uzluksiz: kecha qolgani bugunga o'tadi. Shuning uchun uchta
    raqam yonma-yon turadi va bir-biriga aniq bog'lanadi:

        kecha qolgan + bugun tayyorlandi − bugun sotildi = qoldiq
    """
    day = day or timezone.localdate()
    prepared = prepared_today(branch, day)
    sold = sold_today(branch, day)
    intake = intake_upto(branch, day)
    epochs = first_intake(branch, day)
    earlier = sold_since(branch, epochs, day)
    # Arxivlangan taom ham ro'yxatda qoladi, agar bugun u tayyorlangan yoki
    # sotilgan bo'lsa: aks holda kun o'rtasida menyudan olib tashlangan taom
    # bilan birga uning bugungi porsiyalari ham hisobdan yo'qolardi.
    touched = set(prepared) | set(sold) | set(intake)
    dishes = {
        dish.id: dish
        for dish in Dish.objects.filter(branch=branch).select_related('category')
        .filter(Q(archived=False) | Q(id__in=touched))
    }

    rows = []
    for dish_id, dish in dishes.items():
        made = prepared.get(dish_id, 0)
        gone = sold.get(dish_id, 0)
        # Qoldiq butun hisob bo'yicha: kiritilganlar minus hisob boshlangandan
        # beri sotilganlar.
        left = intake.get(dish_id, 0) - earlier.get(dish_id, 0)
        # Kun boshidagi qoldiq. Bugungi ikki raqam bilan birga u qatorni
        # o'qiladigan qiladi: qaysi porsiya kechadan qolgani ko'rinib turadi.
        carried = left - made + gone
        # «Hisobga olingan» degani — umuman kiritilgan; bugun kiritilmagan
        # bo'lsa ham kechadan qolgan qoldiq o'z kuchida.
        tracked = dish_id in intake
        goods = dish.stock_group == StockKind.GOODS
        # Ogohlantirish chegarasi kun boshidagi zaxiradan olinadi: aks holda
        # 40 ta bilan ochilgan kun bugun hech narsa pishirilmagani uchun
        # bitta porsiyada ogohlantirardi.
        opening = max(carried + made, 0)
        rows.append({
            'dish': dish_id,
            'name': dish.name,
            'prepared': made,
            'sold': gone,
            'carried': carried,
            'remaining': left,
            'group': StockKind.GOODS if goods else StockKind.COOKED,
            # Tayyor mahsulot hech qachon sotuvni to'xtatmaydi: u jismonan
            # javonda turadi va kassir uni berishi mumkin.
            'blocking': not goods,
            # Miqdori kiritilmagan taom cheklanmaydi.
            'tracked': tracked,
            'out': tracked and not goods and left <= 0,
            'low': tracked and 0 < left <= low_at(opening),
            # Chegara kassa ekraniga ham kerak: u savatdagi miqdorni hisobga
            # olib qayta baholaydi. Shu sababli 20% qoidasi faqat shu yerda
            # yoziladi, mijoz tomonida takrorlanmaydi.
            'warn_at': low_at(opening) if tracked else 0,
        })
    rows.sort(key=lambda row: (not row['tracked'], row['remaining'], row['name']))
    tracked_rows = [row for row in rows if row['tracked']]
    cooked_rows = [row for row in tracked_rows if row['blocking']]
    return {
        'date': day,
        'summary': {
            'tracked': len(tracked_rows),
            # «Tugagan» faqat oshxona taomlari uchun ma'noga ega: tayyor
            # mahsulot sotuvni to'xtatmaydi, shuning uchun kassirning
            # ogohlantirishi ham faqat oshxona raqamlaridan chiqadi.
            'out': sum(1 for row in cooked_rows if row['out']),
            'low': sum(1 for row in tracked_rows if row['low']),
            'prepared': sum(row['prepared'] for row in tracked_rows),
            'sold': sum(row['sold'] for row in tracked_rows),
            'carried': sum(max(row['carried'], 0) for row in tracked_rows),
            'remaining': sum(max(row['remaining'], 0) for row in tracked_rows),
            'cooked': len(cooked_rows),
            'goods': len(tracked_rows) - len(cooked_rows),
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
        # Tayyor mahsulot hech qachon to'xtatmaydi — suv javonda turibdi,
        # uni bermaslik uchun sabab yo'q. Qoldig'i minusga tushsa bu
        # «kirim yozilmagan» degan signal bo'lib jurnalga tushadi.
        if not row['blocking']:
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


class WriteOffLineInput(serializers.Serializer):
    dish = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=9999)
    note = serializers.CharField(max_length=200, allow_blank=True, default='')


class DishPrepWriteOffInput(serializers.Serializer):
    lines = WriteOffLineInput(many=True, allow_empty=False)

    def validate_lines(self, lines):
        if len({line['dish'] for line in lines}) != len(lines):
            raise serializers.ValidationError(_('Bir taomni faqat bir marta kiriting.'))
        if len(lines) > 100:
            raise serializers.ValidationError(_('Bir martada ko‘pi bilan 100 ta taom.'))
        return lines


@transaction.atomic
def write_off(user, lines):
    """Qolgan porsiyalarni hisobdan chiqaradi.

    Qoldiq kundan kunga o'tadigan bo'lgach bu yo'l shart bo'lib qoldi:
    dushanbadagi manti jumagacha «bor» bo'lib tursa, oshxona qo'riqchisi
    bir hafta ichida ma'nosini yo'qotadi. Chiqim ham xuddi kirim kabi
    DishPrep qatori bo'lib yoziladi, faqat miqdori manfiy — tarix bitta
    joyda qoladi.
    """
    day = timezone.localdate()
    status = stock_status(user.branch, day)
    by_dish = {row['dish']: row for row in status['dishes']}
    wanted = {line['dish']: line for line in lines}
    dishes = {
        dish.id: dish
        for dish in Dish.objects.filter(branch=user.branch, id__in=wanted)
    }
    if len(dishes) != len(wanted):
        raise serializers.ValidationError({'lines': _('Ayrim taomlar topilmadi.')})

    events = []
    for dish_id, line in wanted.items():
        dish = dishes[dish_id]
        left = by_dish.get(dish_id, {}).get('remaining', 0)
        # Qoldiqdan ko'p chiqarish hisobni yolg'on minusga tushirardi:
        # bo'lmagan narsani hisobdan chiqarib bo'lmaydi.
        if line['quantity'] > left:
            raise serializers.ValidationError({'lines': _(
                '{name} — qoldiq {count} ta, undan ko‘pini hisobdan chiqarib bo‘lmaydi.',
            ).format(name=dish.name, count=max(left, 0))})
        DishPrep.objects.create(
            branch=user.branch, dish=dish, actor=user, date=day,
            quantity=-line['quantity'], note=line['note'] or 'Qoldiq hisobdan chiqarildi',
        )
        events.append(('prep.writeoff', f'{dish.name} · −{line["quantity"]} porsiya hisobdan chiqarildi'))
    audit_many(user, events)
    return stock_status(user.branch, day)


class DishPrepLeftoverView(APIView):
    """Egasi uchun: kun oxirida nima qolgani va ertaga nimasi o'tishi.

    Qoldiq endi yo'qolmaydi — ertangi kunga o'tadi. Shuning uchun bu ro'yxat
    «isrof» emas, «ertaga o'tadigan» ro'yxati. `aged` esa bugungi partiya
    bilan izohlab bo'lmaydigan qismini ko'rsatadi: u kamida bir kunlik va
    aynan shuni hisobdan chiqarish kerak bo'lishi mumkin.
    """

    permission_classes = [OwnerOnly]

    def get(self, request):
        status = stock_status(request.user.branch)
        leftovers = [row for row in status['dishes'] if row['tracked'] and row['remaining'] > 0]
        for row in leftovers:
            row['aged'] = max(row['remaining'] - row['prepared'], 0)
        return Response({
            'date': status['date'],
            'summary': status['summary'],
            'leftovers': sorted(leftovers, key=lambda row: row['remaining'], reverse=True),
        })


class DishPrepWriteOffView(APIView):
    """Qolgan porsiyalarni hisobdan chiqarish — faqat egasi."""

    permission_classes = [OwnerOnly]

    def post(self, request):
        data = DishPrepWriteOffInput(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(write_off(request.user, data.validated_data['lines']), status=201)
