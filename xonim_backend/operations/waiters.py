"""Ofitsiantlar va ularning xizmat haqi.

Superadmin ofitsiantni qo'shadi va foizini belgilaydi; kassir esa buyurtmaga
uni bog'laydi. Foiz sotuv paytida buyurtmaga muzlatiladi, shuning uchun keyin
foiz o'zgarsa ham o'tgan hisoblardagi ulush o'zgarmaydi.

Xizmat haqi hisob ustiga QO'SHILADI: 100 000 lik stol hisobiga 10% qo'shilsa
mijoz 110 000 to'laydi va 10 000 ofitsiantning hisobiga o'tadi. Shuning uchun
u restoran tushumi emas — mijozdan ofitsiant nomiga yig'ilgan pul.

Hisob sodda:

    balans = to'langan hisoblardan yig'ilgan xizmat haqi - berilgan pul

Pul qachon berilsa shunda balansdan ayriladi. Bu restoranning xarajati emas,
shuning uchun Expense yaratilmaydi — aks holda hech qachon tushum bo'lmagan
pul foydadan ayirilardi.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from core.i18n import _
from users.permissions import OwnerOnly, SalesOnly

from .models import Order, Waiter, WaiterPayment
from .money import ZERO, day_window, money, percent
from .reports import ReportFilters
from .serializers import WaiterSerializer
from .services import Conflict, audit


class WaiterViewSet(mixins.ListModelMixin, mixins.CreateModelMixin,
                    mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Kassir ro'yxatni ko'radi; qo'shish va foiz belgilash superadmin ishi."""

    serializer_class = WaiterSerializer

    def get_permissions(self):
        return [SalesOnly() if self.action == 'list' else OwnerOnly()]

    def get_queryset(self):
        return Waiter.objects.filter(branch=self.request.user.branch)

    def perform_create(self, serializer):
        waiter = serializer.save(branch=self.request.user.branch)
        audit(self.request.user, 'waiter.create', f'{waiter.name} · ulushi {waiter.commission}%')

    def perform_update(self, serializer):
        before = serializer.instance.commission
        waiter = serializer.save()
        if waiter.commission != before:
            audit(self.request.user, 'waiter.update', f'{waiter.name} · ulush {before}% → {waiter.commission}%')
        else:
            audit(self.request.user, 'waiter.update', f'{waiter.name} · ma’lumot o‘zgartirildi')

    def perform_destroy(self, instance):
        # Buyurtmalar tarixi saqlanishi kerak, shuning uchun o'chirish
        # o'rniga faolsizlantiriladi.
        instance.active = False
        instance.save(update_fields=['active'])
        audit(self.request.user, 'waiter.remove', f'{instance.name} · faolsizlantirildi')


def waiter_books(branch):
    """Har bir ofitsiantning umrlik hisobi: yig'ilgan va berilgan pul.

    Ikkala yig'indi alohida so'rov bilan olinadi. Bitta so'rovda ikkita
    jadval qo'shilsa qatorlar ko'payib ketardi va summalar bir necha
    barobar bo'lib chiqardi — bu Django agregatlaridagi eng keng tarqalgan
    tuzoq.
    """
    earned = {
        row['waiter_ref']: row['total']
        for row in Order.objects.filter(branch=branch, status='paid', waiter_ref__isnull=False)
        .values('waiter_ref').annotate(total=Coalesce(Sum('service_charge'), ZERO)).order_by()
    }
    handed = {
        row['waiter']: row['total']
        for row in WaiterPayment.objects.filter(branch=branch)
        .values('waiter').annotate(total=Coalesce(Sum('amount'), ZERO)).order_by()
    }
    return earned, handed


def today_books(branch, day):
    """Bugun har bir ofitsiant qancha sotdi va qancha yig'di."""
    since, until = day_window(day)
    return {
        row['waiter_ref']: row
        for row in Order.objects.filter(
            branch=branch, status='paid', waiter_ref__isnull=False,
            paid_at__gte=since, paid_at__lt=until,
        ).values('waiter_ref').annotate(
            sales=Coalesce(Sum('total'), ZERO),
            fee=Coalesce(Sum('service_charge'), ZERO),
            orders=Count('id'),
        ).order_by()
    }


class WaiterEarningsView(APIView):
    """Qaysi ofitsiant qancha sotgan, qancha yig'gan va qancha olgani."""

    permission_classes = [OwnerOnly]

    def get(self, request):
        filters = ReportFilters(data=request.query_params, context={'request': request})
        filters.is_valid(raise_exception=True)
        start, end = filters.validated_data['start'], filters.validated_data['end']
        since, until = day_window(start, end)

        paid = Order.objects.filter(
            branch=request.user.branch, status='paid', paid_at__gte=since, paid_at__lt=until,
        ).exclude(waiter_ref__isnull=True)

        # Ulush har buyurtmaning O'Z foizidan hisoblangan va qatorga
        # muzlatilgan — ofitsiantning bugungi foizidan emas, aks holda eski
        # hisobotlar o'zgarib ketardi.
        rows = {}
        for order in paid.values('waiter_ref', 'waiter_ref__name', 'total', 'service_charge'):
            slot = rows.setdefault(order['waiter_ref'], {
                'id': order['waiter_ref'],
                'name': order['waiter_ref__name'],
                'orders': 0,
                'revenue': ZERO,
                'fee': ZERO,
            })
            slot['orders'] += 1
            slot['revenue'] += order['total']
            slot['fee'] += order['service_charge']

        total_revenue = sum((row['revenue'] for row in rows.values()), ZERO)
        total_fee = sum((row['fee'] for row in rows.values()), ZERO)

        # Balans davrdan qat'i nazar butun vaqt bo'yicha hisoblanadi: o'tgan
        # haftaning ulushi bu hafta berilsa ham raqam to'g'ri qolsin.
        earned, handed = waiter_books(request.user.branch)
        today = today_books(request.user.branch, timezone.localdate())
        names = dict(Waiter.objects.filter(branch=request.user.branch).values_list('id', 'name'))
        # Davrda savdosi bo'lmagan, lekin puli turib qolgan ofitsiant ham
        # ro'yxatda qoladi — aks holda qarz ko'zdan yo'qolardi.
        for waiter_id in set(earned) | set(handed):
            rows.setdefault(waiter_id, {
                'id': waiter_id, 'name': names.get(waiter_id, '—'),
                'orders': 0, 'revenue': ZERO, 'fee': ZERO,
            })

        result = sorted(
            ({
                'id': row['id'],
                'name': row['name'],
                'orders': row['orders'],
                'revenue': money(row['revenue']),
                'fee': money(row['fee']),
                'share': percent(row['revenue'], total_revenue),
                'earned': money(earned.get(row['id'], ZERO)),
                'paid': money(handed.get(row['id'], ZERO)),
                'balance': money(earned.get(row['id'], ZERO) - handed.get(row['id'], ZERO)),
                'today_sales': money(today.get(row['id'], {}).get('sales')),
                'today_fee': money(today.get(row['id'], {}).get('fee')),
                'today_orders': today.get(row['id'], {}).get('orders', 0),
            } for row in rows.values()),
            key=lambda row: Decimal(row['revenue']), reverse=True,
        )

        # Ofitsiantsiz sotilganlar ham ko'rinsin: bog'lash unutilgan bo'lishi mumkin.
        unassigned = Order.objects.filter(
            branch=request.user.branch, status='paid', paid_at__gte=since, paid_at__lt=until,
            waiter_ref__isnull=True,
        ).aggregate(revenue=Coalesce(Sum('total'), ZERO), orders=Count('id'))
        return Response({
            'filters': {'start': start, 'end': end},
            'summary': {
                'revenue': money(total_revenue),
                'fees': money(total_fee),
                'waiters': len(result),
                'unassigned_revenue': money(unassigned['revenue']),
                'unassigned_orders': unassigned['orders'],
                # Bugungi holat: kechga borib «shuncha yig'ildi» degan javob.
                'today_sales': money(sum((row['sales'] for row in today.values()), ZERO)),
                'today_fee': money(sum((row['fee'] for row in today.values()), ZERO)),
                'paid': money(sum(handed.values(), ZERO)),
                'owed': money(sum(earned.values(), ZERO) - sum(handed.values(), ZERO)),
            },
            'waiters': result,
        })


class WaiterPaymentInput(serializers.Serializer):
    """Ofitsiantga pul berish: istalgan kuni, istalgan summada."""

    key = serializers.UUIDField()
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('1'))
    payment_method = serializers.ChoiceField(choices=['cash', 'card'])
    paid_on = serializers.DateField()
    note = serializers.CharField(max_length=250, allow_blank=True, default='')

    def validate_paid_on(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError(_('Kelajakdagi to‘lov sanasi mumkin emas.'))
        return value


def payment_payload(payment, actor_name):
    return {
        'id': payment.id,
        'waiter': payment.waiter_id,
        'amount': str(payment.amount),
        'payment_method': payment.payment_method,
        'payment_label': 'Naqd' if payment.payment_method == 'cash' else 'Karta',
        'paid_on': payment.paid_on,
        'note': payment.note,
        'actor_name': actor_name,
    }


class WaiterPaymentView(APIView):
    """Ofitsiantga yig'ilgan pulni topshirish.

    Kassir ham bera oladi: pul kassada yotadi va odatda uni kassir
    topshiradi. Bu xarajat emas — mijozdan ofitsiant nomiga olingan pul
    egasiga qaytmoqda, shuning uchun foydaga tegmaydi, faqat kassadan
    chiqadi.
    """

    permission_classes = [SalesOnly]

    def waiter_of(self, request, pk):
        waiter = Waiter.objects.filter(branch=request.user.branch, pk=pk).first()
        if not waiter:
            raise serializers.ValidationError(_('Ofitsiant topilmadi.'))
        return waiter

    def get(self, request, pk):
        waiter = self.waiter_of(request, pk)
        payments = WaiterPayment.objects.filter(
            branch=request.user.branch, waiter=waiter).select_related('actor')
        return Response([
            payment_payload(item, item.actor.first_name or item.actor.username) for item in payments
        ])

    @transaction.atomic
    def post(self, request, pk):
        waiter = self.waiter_of(request, pk)
        data = WaiterPaymentInput(data=request.data)
        data.is_valid(raise_exception=True)
        fields = data.validated_data

        # Takroriy yuborish yangi pul bermaydi: avvalgi yozuvning o'zi qaytadi.
        again = WaiterPayment.objects.filter(branch=request.user.branch, key=fields['key']).first()
        if again:
            if again.waiter_id != waiter.id or again.amount != fields['amount']:
                raise Conflict(_('Bir xil amal kaliti boshqa ma’lumot bilan yuborildi.'))
            return Response(payment_payload(again, again.actor.first_name or again.actor.username))

        payment = WaiterPayment.objects.create(
            branch=request.user.branch, waiter=waiter, actor=request.user,
            key=fields['key'], amount=fields['amount'],
            payment_method=fields['payment_method'], paid_on=fields['paid_on'], note=fields['note'],
        )
        audit(
            request.user, 'waiter.pay',
            f'{waiter.name} · {payment.amount} so‘m · {payment.paid_on:%d.%m.%Y}',
        )
        return Response(
            payment_payload(payment, request.user.first_name or request.user.username), status=201)
