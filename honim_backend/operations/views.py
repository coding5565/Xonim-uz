from datetime import timedelta
from decimal import Decimal
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Sum, F
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from users.models import AuditEvent
from users.permissions import KitchenOnly, ManagerOnly, OwnerOnly, SalesOnly
from .models import Order, OrderLine, Expense, Ingredient, Recipe, StockMovement
from .serializers import OrderInput, OrderSerializer, ExpenseSerializer, IngredientSerializer, MovementInput, MovementSerializer, RecipeSerializer
from .services import create_order, pay_order, create_expense, move_stock, Conflict
from .reports import ReportFilters, build_sales_report, sales_report_xlsx
from .ai_assistant import AssistantQuestion, ask_openai, business_snapshot, local_answer


def safely(call, *args):
    try:
        return call(*args)
    except (IntegrityError, OperationalError):
        raise Conflict('Amal boshqa so‘rov bilan to‘qnashdi. Shu amalni qayta tekshiring.')


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [SalesOnly]
    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(branch=self.request.user.branch).select_related('cashier').prefetch_related('lines')

    def create(self, request):
        serializer = OrderInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        obj = safely(create_order, request.user, serializer.validated_data)
        return Response(OrderSerializer(obj).data, status=201)


class PayView(APIView):
    permission_classes = [SalesOnly]

    def post(self, request, pk):
        field = serializers.ChoiceField(choices=['cash', 'card'])
        method = field.run_validation(request.data.get('payment_method'))
        return Response(OrderSerializer(safely(pay_order, request.user, pk, method)).data)


class KitchenView(APIView):
    permission_classes = [KitchenOnly]

    def get(self, request):
        orders = Order.objects.filter(
            branch=request.user.branch,
            preparation_status__in=['queued', 'preparing', 'ready'],
        ).select_related('cashier').prefetch_related('lines').order_by('created_at', 'id')
        return Response(OrderSerializer(orders, many=True).data)


class KitchenStatusView(APIView):
    permission_classes = [KitchenOnly]

    @transaction.atomic
    def post(self, request, pk):
        requested = serializers.ChoiceField(choices=['preparing', 'ready', 'served']).run_validation(request.data.get('status'))
        order = Order.objects.select_for_update().filter(branch=request.user.branch, pk=pk).first()
        if not order:
            raise serializers.ValidationError('Buyurtma topilmadi.')
        transitions = {'queued': 'preparing', 'preparing': 'ready', 'ready': 'served'}
        expected = transitions.get(order.preparation_status)
        if order.preparation_status == requested:
            return Response(OrderSerializer(order).data)
        if requested != expected:
            raise Conflict(f'Buyurtma hozir “{order.get_preparation_status_display()}” holatida. Sahifani yangilang.')
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


class ExpenseViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [ManagerOnly]
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        return Expense.objects.filter(branch=self.request.user.branch).select_related('actor')

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(self.get_serializer(safely(create_expense, request.user, serializer.validated_data)).data, status=201)


class IngredientViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, viewsets.GenericViewSet):
    permission_classes = [ManagerOnly]
    serializer_class = IngredientSerializer

    def get_queryset(self):
        return Ingredient.objects.filter(branch=self.request.user.branch)

    def perform_create(self, serializer):
        serializer.save(branch=self.request.user.branch)


class RecipeViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    permission_classes = [ManagerOnly]
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
    permission_classes = [ManagerOnly]

    def get(self, request):
        return Response(MovementSerializer(StockMovement.objects.filter(branch=request.user.branch).select_related('ingredient')[:100], many=True).data)

    def post(self, request):
        serializer = MovementInput(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(MovementSerializer(safely(move_stock, request.user, serializer.validated_data)).data, status=201)


class DashboardView(APIView):
    permission_classes = [OwnerOnly]

    def get(self, request):
        today = timezone.localdate()
        try:
            days = int(request.query_params.get('days', 7))
        except ValueError:
            raise serializers.ValidationError('Davr noto‘g‘ri.')
        if days not in (7, 30):
            raise serializers.ValidationError('7 yoki 30 kunni tanlang.')
        start = today - timedelta(days=days - 1)
        orders = Order.objects.filter(branch=request.user.branch)
        paid = orders.filter(status='paid', paid_at__date__gte=start, paid_at__date__lte=today)
        expenses = Expense.objects.filter(branch=request.user.branch, date__gte=start, date__lte=today)
        def amount(qs, field):
            return qs.aggregate(total=Sum(field))['total'] or Decimal('0')
        revenue = amount(paid, 'total')
        recipe_cost = OrderLine.objects.filter(order__in=paid).aggregate(total=Sum('cost_total'))['total'] or Decimal('0')
        spending = amount(expenses, 'amount')
        cash_out = amount(expenses.exclude(payment_method='unpaid'), 'amount')
        previous = amount(orders.filter(status='paid', paid_at__date__gte=start - timedelta(days=days), paid_at__date__lt=start), 'total')
        trend = []
        for n in range(days):
            day = start + timedelta(days=n)
            trend.append({'date': day, 'revenue': str(amount(paid.filter(paid_at__date=day), 'total')), 'expenses': str(amount(expenses.filter(date=day), 'amount'))})
        return Response({'revenue': str(revenue), 'expenses': str(spending), 'net_cash': str(revenue - cash_out), 'cost': str(recipe_cost), 'gross_profit': str(revenue - recipe_cost), 'gross_margin': str((revenue - recipe_cost) / revenue * 100 if revenue else 0), 'paid_count': paid.count(), 'open_count': orders.filter(status='open').count(), 'previous_revenue': str(previous), 'cash': str(amount(paid.filter(payment_method='cash'), 'total')), 'card': str(amount(paid.filter(payment_method='card'), 'total')), 'low_stock': Ingredient.objects.filter(branch=request.user.branch, quantity__lte=F('minimum')).count(), 'trend': trend, 'expense_categories': list(expenses.values('category').annotate(total=Sum('amount')).order_by('-total')), 'recent_orders': OrderSerializer(orders.select_related('cashier').prefetch_related('lines')[:5], many=True).data, 'as_of': timezone.now(), 'basis': 'Yalpi foyda: tushumdan sotuv paytidagi retsept tannarxi ayirilgan qiymat. Oylik, ijara va boshqa xarajatlar bu ko‘rsatkichdan alohida.'})


class SalesReportView(APIView):
    permission_classes = [ManagerOnly]

    def get(self, request):
        serializer = ReportFilters(data=request.query_params, context={'request': request})
        serializer.is_valid(raise_exception=True)
        return Response(build_sales_report(request.user, serializer.validated_data))


class SalesReportExportView(APIView):
    permission_classes = [ManagerOnly]

    def get(self, request):
        serializer = ReportFilters(data=request.query_params, context={'request': request})
        serializer.is_valid(raise_exception=True)
        report = build_sales_report(request.user, serializer.validated_data)
        content = sales_report_xlsx(report)
        filename = f'honim-savdo-{report["filters"]["start"]}-{report["filters"]["end"]}.xlsx'
        response = HttpResponse(content, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['X-Content-Type-Options'] = 'nosniff'
        return response


class AssistantChatView(APIView):
    permission_classes = [OwnerOnly]

    def post(self, request):
        serializer = AssistantQuestion(data=request.data)
        serializer.is_valid(raise_exception=True)
        snapshot = business_snapshot(request.user.branch)
        question = serializer.validated_data['question']
        result = local_answer(question, snapshot)
        if result:
            return Response({**result, 'source': 'crm'})
        answer = ask_openai(question, snapshot)
        if answer is None:
            return Response({
                'answer': 'AI kaliti hali ulanmagan. Bugun, kecha yoki hafta bo‘yicha tezkor savollardan birini bosing, yoki OpenAI kalitini ulang.',
                'charts': [], 'source': 'setup',
            })
        return Response({'answer': answer, 'charts': [], 'source': 'ai'})
