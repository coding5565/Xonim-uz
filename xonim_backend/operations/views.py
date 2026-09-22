from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Prefetch, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.i18n import _
from users.models import AuditEvent
from users.permissions import BranchMember, KitchenOnly, OwnerOnly, SalesOnly

from .ai_assistant import AssistantQuestion, ask_openai, business_snapshot, local_answer
from .assistant_chats import remember
from .backups import BackupError, latest_backups, run_backup, telegram_status
from .models import (
    DELIVERY_CHANNELS,
    ORDER_STATUSES,
    SALE_CHANNELS,
    SALE_PAYMENT_CHOICES,
    SALE_PAYMENT_LABELS,
    Expense,
    Ingredient,
    Order,
    OrderLine,
    Recipe,
    StockMovement,
    Table,
    WaiterPayment,
)
from .money import money, parse_month, platform_fee
from .printing import PrinterError, print_receipt
from .reports import (
    ReportFilters,
    SalesBoardFilters,
    build_sales_board,
    build_sales_report,
    sales_report_xlsx,
)
from .serializers import (
    AppendLinesInput,
    ExpenseSerializer,
    IngredientSerializer,
    MovementInput,
    MovementSerializer,
    OrderInput,
    OrderSerializer,
    RecipeSerializer,
    TableSerializer,
)
from .services import (
    Conflict,
    append_order_lines,
    apply_discount,
    audit,
    cancel_order,
    create_expense,
    create_order,
    move_stock,
    pay_order,
    quantity_text,
    refund_order,
    remove_order_line,
    reprice_recipes,
    safely,
)


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [SalesOnly]
    serializer_class = OrderSerializer

    def get_queryset(self):
        queryset = Order.objects.filter(branch=self.request.user.branch).select_related('cashier').prefetch_related('lines')
        status = self.request.query_params.get('status')
        return queryset.filter(status=status) if status in dict(ORDER_STATUSES) else queryset

    def create(self, request):
        serializer = OrderInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = safely(create_order, request.user, serializer.validated_data)
        return Response(OrderSerializer(obj).data, status=201)


class PayView(APIView):
    permission_classes = [SalesOnly]

    def post(self, request, pk):
        field = serializers.ChoiceField(choices=SALE_PAYMENT_CHOICES)
        method = field.run_validation(request.data.get('payment_method'))
        return Response(OrderSerializer(safely(pay_order, request.user, pk, method)).data)


class TableViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                   mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Kassir stollarni ko'radi; qo'shish va o'zgartirish admin ishi."""

    serializer_class = TableSerializer

    def get_permissions(self):
        return [BranchMember() if self.action in ('list', 'retrieve') else SalesOnly()]

    def get_queryset(self):
        # Ochiq hisob har stol kartasida ko'rsatiladi, shuning uchun oldindan olinadi.
        return Table.objects.filter(branch=self.request.user.branch).prefetch_related(
            Prefetch('orders', queryset=Order.objects.filter(status='open').prefetch_related('lines')),
        )

    def _describe(self, table):
        return f'{table.label} · {table.get_zone_display()} · {table.get_seating_display()} · {table.seats} o‘rin'

    @transaction.atomic
    def perform_create(self, serializer):
        table = serializer.save(branch=self.request.user.branch)
        audit(self.request.user, 'table.create', self._describe(table))

    @transaction.atomic
    def perform_update(self, serializer):
        table = serializer.save()
        audit(self.request.user, 'table.update', self._describe(table))

    @transaction.atomic
    def perform_destroy(self, instance):
        if instance.orders.filter(status='open').exists():
            raise Conflict(_('Bu stolda ochiq hisob bor. Avval to‘lovni yakunlang.'))
        # Yopilgan buyurtmalar tarixi saqlanishi kerak, shuning uchun o'chirish o'rniga
        # stol faolsizlantiriladi.
        instance.active = False
        instance.save(update_fields=['active'])
        audit(self.request.user, 'table.remove', f'{instance.label} · faolsizlantirildi')


class OrderLinesView(APIView):
    """Adds what the guest ordered after the bill was already open."""

    permission_classes = [SalesOnly]

    def post(self, request, pk):
        serializer = AppendLinesInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = safely(append_order_lines, request.user, pk, serializer.validated_data)
        return Response(OrderSerializer(order).data)


class VoidInput(serializers.Serializer):
    # Sabab majburiy: keyin nima uchun bekor qilinganini bilish shart.
    reason = serializers.CharField(max_length=200, trim_whitespace=True)

    def validate_reason(self, value):
        if len(value.strip()) < 3:
            raise serializers.ValidationError(_('Sababni yozing.'))
        return value.strip()


class OrderLineDetailView(APIView):
    """Ochiq hisobdan noto‘g‘ri qo‘shilgan taomni olib tashlaydi."""

    permission_classes = [SalesOnly]

    def delete(self, request, pk, line_id):
        order = safely(remove_order_line, request.user, pk, line_id)
        return Response(OrderSerializer(order).data)


class OrderCancelView(APIView):
    """To‘lovsiz hisobni bekor qiladi."""

    permission_classes = [SalesOnly]

    def post(self, request, pk):
        data = VoidInput(data=request.data)
        data.is_valid(raise_exception=True)
        order = safely(cancel_order, request.user, pk, data.validated_data['reason'])
        return Response(OrderSerializer(order).data)


class OrderRefundView(APIView):
    """To‘langan hisobni qaytaradi. Faqat admin va superadmin."""

    permission_classes = [OwnerOnly]

    def post(self, request, pk):
        data = VoidInput(data=request.data)
        data.is_valid(raise_exception=True)
        order = safely(refund_order, request.user, pk, data.validated_data['reason'])
        return Response(OrderSerializer(order).data)


class DiscountInput(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'))
    reason = serializers.CharField(max_length=120, allow_blank=True, default='')

    def validate_reason(self, value):
        return value.strip()


class OrderDiscountView(APIView):
    """Ochiq hisobga chegirma qo‘yadi yoki uni olib tashlaydi."""

    permission_classes = [SalesOnly]

    def post(self, request, pk):
        data = DiscountInput(data=request.data)
        data.is_valid(raise_exception=True)
        order = safely(apply_discount, request.user, pk, data.validated_data['amount'], data.validated_data['reason'])
        return Response(OrderSerializer(order).data)


class ReceiptPrintView(APIView):
    """Chekni qayta chop etadi. Avtomatik chop etish to'lov paytida bo'ladi."""

    permission_classes = [SalesOnly]

    def post(self, request, pk):
        order = Order.objects.filter(branch=request.user.branch, pk=pk).prefetch_related('lines').first()
        if not order:
            raise serializers.ValidationError(_('Buyurtma topilmadi.'))
        try:
            print_receipt(order)
        except PrinterError as error:
            # Bu qo'lda bosilgan tugma, shuning uchun kassir sababini ko'rishi kerak.
            audit(request.user, 'print.failed', f'#{order.id} · qayta chop etilmadi · {error}')
            raise Conflict(str(error)) from None
        audit(request.user, 'order.print', f'#{order.id} · {order.total} so‘m')
        return Response({'detail': f'#{order.id} cheki chop etildi.'})


class KitchenView(APIView):
    permission_classes = [KitchenOnly]

    def get(self, request):
        # Bekor qilingan yoki qaytarilgan hisob oshxona taxtasida turmasligi
        # kerak — aks holda pishirilib ketardi.
        # Oxirgi sutka bilan cheklanadi. Talon qog'ozda ishlaganda hech kim
        # buyurtmani «topshirildi» deb belgilamaydi, shuning uchun taxta
        # cheksiz o'sib borardi: bir necha oydan keyin bitta javobda
        # minglab qator qaytarardi.
        since = timezone.now() - timedelta(days=1)
        orders = Order.objects.filter(
            branch=request.user.branch,
            created_at__gte=since,
            preparation_status__in=['queued', 'preparing', 'ready'],
        ).exclude(status__in=['cancelled', 'refunded']).select_related('cashier').prefetch_related('lines').order_by('created_at', 'id')
        return Response(OrderSerializer(orders[:200], many=True).data)


class KitchenStatusView(APIView):
    permission_classes = [KitchenOnly]

    @transaction.atomic
    def post(self, request, pk):
        requested = serializers.ChoiceField(choices=['preparing', 'ready', 'served']).run_validation(request.data.get('status'))
        order = Order.objects.select_for_update().filter(branch=request.user.branch, pk=pk).first()
        if not order:
            raise serializers.ValidationError(_('Buyurtma topilmadi.'))
        transitions = {'queued': 'preparing', 'preparing': 'ready', 'ready': 'served'}
        expected = transitions.get(order.preparation_status)
        if order.preparation_status == requested:
            return Response(OrderSerializer(order).data)
        if requested != expected:
            raise Conflict(_('Buyurtma hozir “{state}” holatida. Sahifani yangilang.').format(
                state=_(order.get_preparation_status_display())))
        now = timezone.now()
        order.preparation_status = requested
        if requested == 'preparing':
            order.started_at = now
        elif requested == 'ready':
            order.ready_at = now
        else:
            order.served_at = now
        order.save(update_fields=['preparation_status', {'preparing':'started_at','ready':'ready_at','served':'served_at'}[requested]])
        AuditEvent.objects.create(branch=request.user.branch, actor=request.user, action=f'kitchen.{requested}', description=f'#{order.id} · {order.get_preparation_status_display()}')
        return Response(OrderSerializer(order).data)


class ExpenseViewSet(mixins.ListModelMixin, mixins.UpdateModelMixin,
                     mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """Kassir xarajat kiritadi; tuzatish va o‘chirish superadmin ishi.

    Xarajat foyda hisobiga to‘g‘ridan-to‘g‘ri kiradi, shuning uchun noto‘g‘ri
    kiritilgan summa tuzatilishi SHART — ilgari uni na tahrirlash, na o‘chirish
    mumkin edi va xato raqam hisobotda abadiy qolardi. Ikkala amal ham
    jurnalga tushadi va faqat egaga ochiq.
    """

    serializer_class = ExpenseSerializer

    def get_permissions(self):
        return [SalesOnly() if self.action in ('list', 'create') else OwnerOnly()]

    def get_queryset(self):
        return Expense.objects.filter(branch=self.request.user.branch).select_related('actor')

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self.get_serializer(safely(create_expense, request.user, serializer.validated_data)).data, status=201)

    def _guard_salary(self, expense):
        """Ish haqi to‘lovi bilan bog‘langan xarajat bu yerdan o‘zgarmaydi.

        U `SalaryPayment` bilan juft yuradi: bittasini yolg‘iz o‘zgartirish
        xodimning balansini yozuvdan ajratib yuborardi.
        """
        if hasattr(expense, 'salary_payment'):
            raise Conflict(_('Ish haqi to‘lovini bu yerdan o‘zgartirib bo‘lmaydi.'))

    @transaction.atomic
    def perform_update(self, serializer):
        self._guard_salary(serializer.instance)
        before = f'{serializer.instance.purpose} · {serializer.instance.amount} so‘m'
        expense = serializer.save()
        audit(self.request.user, 'expense.update',
              f'{before} → {expense.purpose} · {expense.amount} so‘m · {expense.date}')

    @transaction.atomic
    def perform_destroy(self, instance):
        self._guard_salary(instance)
        audit(self.request.user, 'expense.remove',
              f'{instance.category} · {instance.purpose} · {instance.amount} so‘m · {instance.date}')
        instance.delete()


class IngredientViewSet(
    mixins.ListModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
    mixins.DestroyModelMixin, viewsets.GenericViewSet,
):
    """Ombordagi mahsulotlar: qo'shish, tahrirlash va ro'yxatdan chiqarish.

    O'chirish ikki xil ishlaydi va qaysi biri bo'lishini mahsulotning tarixi
    hal qiladi. Hech qachon ishlatilmagan yozuv butunlay o'chadi — u shunchaki
    xato kiritilgan. Kirimi yoki sarfi bo'lgani esa ARXIVLANADI: o'tgan
    oyning ombor hisobotida uning nomi turibdi va u yo'qolsa hisobot
    o'qib bo'lmaydigan bo'lib qolardi.
    """

    permission_classes = [SalesOnly]
    serializer_class = IngredientSerializer

    def get_queryset(self):
        rows = Ingredient.objects.filter(branch=self.request.user.branch)
        # Yashirish FAQAT ro'yxatga tegadi. Bitta yozuvni ochish, tahrirlash
        # va qaytarib olish har doim ishlashi kerak — aks holda arxivlangan
        # mahsulotni hech qachon tiklab bo'lmasdi.
        if self.action != 'list':
            return rows
        if self.request.query_params.get('archived') in ('1', 'true'):
            return rows
        return rows.filter(archived=False)

    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save(branch=self.request.user.branch)
        # Qoldiq faqat kirim orqali to'ladi, shuning uchun bu yerda o'lchov va
        # ogohlantirish chegarasi yoziladi.
        price = f' · 1 {obj.unit} = {obj.unit_cost} so‘m' if obj.unit_cost else ''
        audit(
            self.request.user, 'stock.ingredient',
            f'{obj.name} · o‘lchov {obj.unit}{price} · eng kam qoldiq {quantity_text(obj.minimum)} {obj.unit}',
        )

    @transaction.atomic
    def perform_update(self, serializer):
        before = serializer.instance.unit_cost
        obj = serializer.save()
        if obj.unit_cost != before:
            # Narx o'zgarsa, shu masalliq ishlatilgan retseptlar tannarxi
            # darhol qayta hisoblanadi — har birini qo'lda ochib chiqish shart emas.
            touched = reprice_recipes(obj)
            audit(
                self.request.user, 'stock.price',
                f'{obj.name} · 1 {obj.unit}: {before} → {obj.unit_cost} so‘m · {touched} ta retsept qatori yangilandi',
            )
        else:
            audit(self.request.user, 'stock.ingredient', f'{obj.name} · ma’lumot o‘zgartirildi')

    @transaction.atomic
    def perform_destroy(self, instance):
        # Retseptdagi mahsulot umuman chiqmaydi: retsept tannarxsiz qolib
        # ketardi va buni hech kim sezmasdi.
        recipes = list(
            Recipe.objects.filter(lines__ingredient=instance).distinct().values_list('name', flat=True)[:5]
        )
        if recipes:
            raise serializers.ValidationError(_(
                '«{name}» {recipes} retseptida ishlatilyapti — avval retseptdan olib tashlang.',
            ).format(name=instance.name, recipes=', '.join(recipes)))

        if StockMovement.objects.filter(ingredient=instance).exists():
            # Tarixi bor: o'chirmaymiz, ro'yxatdan olamiz.
            instance.archived = True
            instance.save(update_fields=['archived'])
            audit(
                self.request.user, 'stock.ingredient',
                f'{instance.name} · ro‘yxatdan olindi · qoldiq '
                f'{quantity_text(instance.quantity)} {instance.unit}',
            )
            return
        name = instance.name
        instance.delete()
        audit(self.request.user, 'stock.ingredient', f'{name} · o‘chirildi')


class RecipeViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [OwnerOnly]
    serializer_class = RecipeSerializer

    def get_queryset(self):
        return Recipe.objects.filter(branch=self.request.user.branch).select_related('dish').prefetch_related('lines__ingredient')

    @transaction.atomic
    def perform_create(self, serializer):
        recipe = serializer.save()
        AuditEvent.objects.create(branch=self.request.user.branch, actor=self.request.user, action='recipe.create', description=f'{recipe.name} · tannarx hisoblandi')

    @transaction.atomic
    def perform_update(self, serializer):
        recipe = serializer.save()
        AuditEvent.objects.create(branch=self.request.user.branch, actor=self.request.user, action='recipe.update', description=f'{recipe.name} · retsept yangilandi')


class StockView(APIView):
    """Ombor harakatlari: kirim kassir tomonidan yoziladi, tarix esa egaga.

    Kassir kirim va chiqim kiritadi — bu uning kundalik ishi. Lekin harakatlar
    TARIXI egasining nazorat vositasi: u yerdan qaysi taomga qancha masalliq
    ketgani, retsept bo'yicha sarf va qo'lda yozilgan farq ko'rinadi. Shuning
    uchun ro'yxat faqat egaga ochiq — ekrандan yashirish yetarli emas, so'rov
    ham rad etilishi kerak.
    """

    permission_classes = [SalesOnly]

    def get(self, request):
        if request.user.role != 'owner':
            raise PermissionDenied(_('Ombor harakatlari tarixi faqat superadminga ochiq.'))
        return Response(MovementSerializer(StockMovement.objects.filter(branch=request.user.branch).select_related('ingredient')[:100], many=True).data)

    def post(self, request):
        serializer = MovementInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(MovementSerializer(safely(move_stock, request.user, serializer.validated_data)).data, status=201)


def dashboard_period(params, today):
    """Turns ?month=YYYY-MM or ?days=7|30 into the window and the one before it."""
    month = params.get('month')
    if month:
        first = parse_month(month)
        if first > today.replace(day=1):
            raise serializers.ValidationError(_('Kelajak oyi uchun hisobot tuzilmaydi.'))
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        return first, min(last, today), (first - timedelta(days=1)).replace(day=1), first - timedelta(days=1)
    try:
        days = int(params.get('days', 7))
    except (TypeError, ValueError):
        raise serializers.ValidationError(_('Davr noto‘g‘ri.')) from None
    if days not in (7, 30):
        raise serializers.ValidationError(_('7 yoki 30 kunni tanlang, yoki oyni belgilang.'))
    start = today - timedelta(days=days - 1)
    return start, today, start - timedelta(days=days), start - timedelta(days=1)


def dashboard_months(branch, today):
    """Every month from the first record to now, newest first, so the picker covers the whole history."""
    first_paid = Order.objects.filter(branch=branch, status='paid').order_by('paid_at').values_list('paid_at', flat=True).first()
    first_expense = Expense.objects.filter(branch=branch).order_by('date').values_list('date', flat=True).first()
    known = []
    if first_paid:
        known.append(timezone.localtime(first_paid).date())
    if first_expense:
        known.append(first_expense)
    cursor = min(known).replace(day=1) if known else today.replace(day=1)
    months = []
    while cursor <= today.replace(day=1):
        months.append(cursor.strftime('%Y-%m'))
        cursor = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
    return list(reversed(months))


class DashboardView(APIView):
    permission_classes = [OwnerOnly]

    def get(self, request):
        branch = request.user.branch
        today = timezone.localdate()
        start, end, previous_start, previous_end = dashboard_period(request.query_params, today)
        orders = Order.objects.filter(branch=branch)
        paid = orders.filter(status='paid', paid_at__date__gte=start, paid_at__date__lte=end)
        expenses = Expense.objects.filter(branch=branch, date__gte=start, date__lte=end)
        period_orders = orders.filter(created_at__date__gte=start, created_at__date__lte=end)

        def amount(queryset, field):
            return queryset.aggregate(total=Sum(field))['total'] or Decimal('0')

        revenue = amount(paid, 'total')
        recipe_cost = OrderLine.objects.filter(order__in=paid).aggregate(total=Sum('cost_total'))['total'] or Decimal('0')
        spending = amount(expenses, 'amount')
        # «Sof pul oqimi» Moliya sahifasidagi bilan bir xil formulada bo'lishi
        # shart: ikkala karta ham shu nom bilan turadi. Ombor xaridi ham
        # kassadan chiqadi, shuning uchun u ham ayiriladi.
        settled = amount(expenses.exclude(payment_method='unpaid'), 'amount')
        purchases = StockMovement.objects.filter(
            branch=branch, kind='receipt', date__gte=start, date__lte=end,
        ).aggregate(total=Sum('cost_total'))['total'] or Decimal('0')
        # Yetkazib berish platformasi ushlab qolgan ulush hech qachon hisobga
        # tushmaydi, shuning uchun u ham pul oqimidan ayriladi — Moliya
        # sahifasidagi «Sof pul oqimi» bilan bir xil formula.
        platform_cut = paid.aggregate(total=platform_fee())['total']
        # Ofitsiant xizmat haqi kassaga tushadi, lekin tushum emas: u
        # ofitsiantga berilguncha kassada turadi, berilgach chiqib ketadi.
        service_in = paid.aggregate(total=Coalesce(Sum('service_charge'), Decimal('0')))['total']
        service_out = WaiterPayment.objects.filter(
            branch=branch, paid_on__gte=start, paid_on__lte=end,
        ).aggregate(total=Coalesce(Sum('amount'), Decimal('0')))['total']
        cash_out = settled + purchases + platform_cut + service_out
        previous = amount(orders.filter(status='paid', paid_at__date__gte=previous_start, paid_at__date__lte=previous_end), 'total')
        # One grouped query per series instead of two aggregates per day. order_by() drops the
        # model's default ordering, which Django would otherwise add to GROUP BY and split the totals.
        revenue_by_day = {row['day']: row['total'] for row in paid.annotate(day=TruncDate('paid_at')).values('day').annotate(total=Sum('total')).order_by()}
        expenses_by_day = {row['date']: row['total'] for row in expenses.values('date').annotate(total=Sum('amount')).order_by()}
        by_method = [
            {'method': row['payment_method'],
             'label': SALE_PAYMENT_LABELS.get(row['payment_method'], row['payment_method'] or '—'),
             'revenue': money(row['total'])}
            for row in paid.values('payment_method').annotate(total=Sum('total')).order_by('-total')
        ]
        trend = []
        cursor = start
        while cursor <= end:
            trend.append({'date': cursor, 'revenue': money(revenue_by_day.get(cursor)), 'expenses': money(expenses_by_day.get(cursor))})
            cursor += timedelta(days=1)
        return Response({'revenue': money(revenue), 'expenses': money(spending), 'net_cash': money(revenue + service_in - cash_out), 'platform_fee': money(platform_cut), 'service_charge': money(service_in), 'cost': money(recipe_cost), 'gross_profit': money(revenue - recipe_cost), 'gross_margin': money((revenue - recipe_cost) / revenue * 100 if revenue else Decimal('0')), 'paid_count': paid.count(), 'open_count': orders.filter(status='open').count(), 'previous_revenue': money(previous), 'by_method': by_method, 'low_stock': Ingredient.objects.filter(branch=branch, quantity__lte=F('minimum')).count(), 'trend': trend, 'period': {'kind': 'month' if request.query_params.get('month') else 'days', 'start': start, 'end': end}, 'months': dashboard_months(branch, today), 'expense_categories': list(expenses.values('category').annotate(total=Sum('amount')).order_by('-total')), 'recent_orders': OrderSerializer(period_orders.select_related('cashier').prefetch_related('lines')[:5], many=True).data, 'as_of': timezone.now(), 'basis': 'Yalpi foyda: tushumdan sotuv paytidagi retsept tannarxi ayirilgan qiymat. Oylik, ijara va boshqa xarajatlar bu ko‘rsatkichdan alohida.'})


class SalesSummaryView(APIView):
    """Live takings for the people working the till: cashier, admin and owner."""

    permission_classes = [SalesOnly]

    def get(self, request):
        branch = request.user.branch
        today = timezone.localdate()
        paid = Order.objects.filter(branch=branch, status='paid')
        today_paid = paid.filter(paid_at__date=today)

        def totals(queryset):
            row = queryset.aggregate(total=Sum('total'), orders=Count('id'))
            return {'revenue': money(row['total']), 'orders': row['orders']}

        # Grouped so a new payment method shows up here without touching this view.
        by_method = [
            {'method': row['payment_method'], 'label': SALE_PAYMENT_LABELS.get(row['payment_method'], row['payment_method']), 'revenue': money(row['total'])}
            for row in today_paid.values('payment_method').annotate(total=Sum('total')).order_by('-total')
        ]
        # Kanal kesimi kassirga ham kerak: Uzum va Yandex savdosi alohida
        # kiritiladi, demak kun davomida qanchaligini ham alohida ko'rishi kerak.
        counted = {row['channel']: row for row in
                   today_paid.values('channel').annotate(total=Sum('total'), orders=Count('id'))}
        by_channel = [{
            'channel': channel,
            'label': label,
            'revenue': money(counted.get(channel, {}).get('total')),
            'orders': counted.get(channel, {}).get('orders', 0),
            'delivery': channel in DELIVERY_CHANNELS,
        } for channel, label in SALE_CHANNELS]
        open_row = Order.objects.filter(branch=branch, status='open').aggregate(total=Sum('total'), orders=Count('id'))
        return Response({
            'today': totals(today_paid),
            'yesterday': totals(paid.filter(paid_at__date=today - timedelta(days=1))),
            'last_7_days': totals(paid.filter(paid_at__date__gte=today - timedelta(days=6), paid_at__date__lte=today)),
            'mine_today': totals(today_paid.filter(cashier=request.user)),
            'open': {'revenue': money(open_row['total']), 'orders': open_row['orders']},
            'today_by_method': by_method,
            'today_by_channel': by_channel,
            'as_of': timezone.now(),
        })


class SalesBoardView(APIView):
    """The Sotuv board: what sold, when, and to whose till."""

    permission_classes = [SalesOnly]

    def get(self, request):
        serializer = SalesBoardFilters(data=request.query_params, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(build_sales_board(request.user, serializer.validated_data))


class SalesReportView(APIView):
    permission_classes = [OwnerOnly]

    def get(self, request):
        serializer = ReportFilters(data=request.query_params, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(build_sales_report(request.user, serializer.validated_data))


class SalesReportExportView(APIView):
    permission_classes = [OwnerOnly]

    def get(self, request):
        serializer = ReportFilters(data=request.query_params, context={'request': request})
        serializer.is_valid(raise_exception=True)
        report = build_sales_report(request.user, serializer.validated_data)
        content = sales_report_xlsx(report)
        filename = f'xonim-savdo-{report["filters"]["start"]}-{report["filters"]["end"]}.xlsx'
        response = HttpResponse(content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class BackupThrottle(ScopedRateThrottle):
    """Nusxa olish bazani va diskni bosadi — tugmani ketma-ket bosib
    serverni cho'ktirib bo'lmasin."""

    scope = 'backup'


class BackupView(APIView):
    """Egasi istalgan paytda nusxa olib, uni Telegramga yuboradi.

    Jadval bo‘yicha nusxa kuniga ikki marta cron orqali olinadi; bu tugma
    esa «hozir kerak» degan holat uchun — masalan menyuni katta
    o‘zgartirishdan oldin.
    """

    permission_classes = [OwnerOnly]
    throttle_classes = [BackupThrottle]
    throttle_scope = 'backup'

    def get(self, request):
        return Response({
            'telegram': telegram_status(),
            'backups': latest_backups(),
            'keep_days': settings.BACKUP_KEEP_DAYS,
        })

    def post(self, request):
        who = request.user.first_name or request.user.username
        try:
            result = run_backup(actor=who, source='manual')
        except BackupError as failure:
            audit(request.user, 'backup.failed', str(failure)[:200])
            raise Conflict(str(failure)) from None
        audit(
            request.user, 'backup.create',
            f'{", ".join(item["name"] for item in result["files"])} · '
            f'{"Telegramga yuborildi" if result["sent_to_telegram"] else "faqat serverda"}',
        )
        return Response({
            **result,
            'telegram': telegram_status(),
            'backups': latest_backups(),
            'keep_days': settings.BACKUP_KEEP_DAYS,
        })


class AssistantThrottle(ScopedRateThrottle):
    """Har bir savol tashqi AI xizmatiga pullik so‘rov yuboradi.

    Umumiy 600/min limit bu yerda juda bo‘sh: tugmani ushlab turgan barmoq
    ham hisobni bo‘shatib yuborishi mumkin.
    """

    scope = 'assistant'


class AssistantChatView(APIView):
    permission_classes = [OwnerOnly]
    throttle_classes = [AssistantThrottle]
    throttle_scope = 'assistant'

    def post(self, request):
        serializer = AssistantQuestion(data=request.data)
        serializer.is_valid(raise_exception=True)
        snapshot = business_snapshot(request.user.branch)
        question = serializer.validated_data['question']
        chat_id = serializer.validated_data.get('chat')

        result = local_answer(question, snapshot)
        if result:
            payload = {**result, 'source': 'crm'}
        else:
            # AI xizmati tashqarida: u yiqilsa yoki javob bermasa, bu bizning
            # xatomiz emas. Ilgari RuntimeError DRF orqali o'tib ketib, egaga
            # 500 sahifasi ko'rinardi.
            try:
                answer = ask_openai(question, snapshot)
            except RuntimeError as failure:
                return Response({
                    'answer': str(failure), 'charts': [], 'source': 'offline',
                }, status=503)
            if answer is None:
                payload = {
                    'answer': _('AI kaliti hali ulanmagan. Bugun, kecha yoki hafta bo‘yicha tezkor savollardan birini bosing, yoki OpenAI kalitini ulang.'),
                    'charts': [], 'source': 'setup',
                }
            else:
                payload = {'answer': answer, 'charts': [], 'source': 'ai'}

        # Savol ham, javob ham saqlanadi — suhbat keyin ochilganda tiklanadi.
        chat = remember(request.user, chat_id, question, payload['answer'], payload.get('charts'))
        return Response({**payload, 'chat': chat.id, 'chat_title': chat.title})
