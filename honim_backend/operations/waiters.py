"""Ofitsiantlar va ularning ulushi.

Superadmin ofitsiantni qo'shadi va foizini belgilaydi; kassir esa buyurtmaga
uni bog'laydi. Foiz sotuv paytida buyurtmaga muzlatiladi, shuning uchun
keyin foiz o'zgarsa ham o'tgan hisoblardagi ulush o'zgarmaydi.
"""
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce
from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from users.permissions import OwnerOnly, SalesOnly

from .models import Order, Waiter
from .money import ZERO, day_window, money, percent
from .reports import ReportFilters
from .serializers import WaiterSerializer
from .services import audit


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


class WaiterEarningsView(APIView):
    """Qaysi ofitsiant qancha sotgan va qancha ulush to‘plagani."""

    permission_classes = [OwnerOnly]

    def get(self, request):
        filters = ReportFilters(data=request.query_params, context={'request': request})
        filters.is_valid(raise_exception=True)
        start, end = filters.validated_data['start'], filters.validated_data['end']
        since, until = day_window(start, end)

        paid = Order.objects.filter(
            branch=request.user.branch, status='paid', paid_at__gte=since, paid_at__lt=until,
        ).exclude(waiter_ref__isnull=True)

        # Ulush har buyurtmaning O'Z foizidan hisoblanadi — ofitsiantning
        # bugungi foizidan emas, aks holda eski hisobotlar o'zgarib ketardi.
        # Shuning uchun SQL'da emas, Pythonda yig'iladi.
        rows = {}
        for order in paid.values('waiter_ref', 'waiter_ref__name', 'total', 'waiter_commission'):
            slot = rows.setdefault(order['waiter_ref'], {
                'id': order['waiter_ref'],
                'name': order['waiter_ref__name'],
                'orders': 0,
                'revenue': ZERO,
                'fee': ZERO,
            })
            slot['orders'] += 1
            slot['revenue'] += order['total']
            slot['fee'] += order['total'] * order['waiter_commission'] / 100

        total_revenue = sum((row['revenue'] for row in rows.values()), ZERO)
        total_fee = sum((row['fee'] for row in rows.values()), ZERO)
        result = sorted(
            ({
                'id': row['id'],
                'name': row['name'],
                'orders': row['orders'],
                'revenue': money(row['revenue']),
                'fee': money(row['fee']),
                'share': percent(row['revenue'], total_revenue),
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
            },
            'waiters': result,
        })
