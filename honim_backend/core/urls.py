from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from users.payroll import PayrollView
from users.views import AuditView, CsrfView, LoginView, LogoutView, MeView, SalaryPaymentExportView, SalaryPaymentView, StaffDetailView, StaffView
from catalog.views import CategoryViewSet, DishViewSet, PublicMenuView
from operations.views import (
    AssistantChatView, DashboardView, ExpenseViewSet, IngredientViewSet, KitchenStatusView,
    KitchenView, OrderLinesView, OrderViewSet, ReceiptPrintView, PayView, RecipeViewSet, SalesReportExportView,
    OrderCancelView, OrderDiscountView, OrderLineDetailView, OrderRefundView,
    SalesBoardView, SalesReportView, SalesSummaryView, StockView, TableViewSet,
)
from operations.assistant_chats import AssistantChatDetailView, AssistantChatListView
from operations.daily_usage import DailyUsageView, UsageComparisonView
from operations.finance import FinanceView
from operations.shift import ShiftHistoryView, ShiftView
from operations.stock_usage import StockUsageView

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('dishes', DishViewSet, basename='dish')
router.register('orders', OrderViewSet, basename='order')
router.register('expenses', ExpenseViewSet, basename='expense')
router.register('ingredients', IngredientViewSet, basename='ingredient')
router.register('recipes', RecipeViewSet, basename='recipe')
router.register('tables', TableViewSet, basename='table')

urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('api/v1/auth/csrf/', CsrfView.as_view()),
    path('api/v1/auth/login/', LoginView.as_view()),
    path('api/v1/auth/me/', MeView.as_view()),
    path('api/v1/auth/logout/', LogoutView.as_view()),
    path('api/v1/audit/', AuditView.as_view()),
    path('api/v1/staff/', StaffView.as_view()),
    path('api/v1/staff/<int:pk>/', StaffDetailView.as_view()),
    path('api/v1/staff/<int:pk>/salary-payments/', SalaryPaymentView.as_view()),
    path('api/v1/staff/salary-payments/export/', SalaryPaymentExportView.as_view()),
    path('api/v1/payroll/', PayrollView.as_view()),
    path('api/v1/public/menu/<slug:slug>/', PublicMenuView.as_view()),
    path('api/v1/orders/<int:pk>/pay/', PayView.as_view()),
    path('api/v1/orders/<int:pk>/lines/', OrderLinesView.as_view()),
    path('api/v1/orders/<int:pk>/lines/<int:line_id>/', OrderLineDetailView.as_view()),
    path('api/v1/orders/<int:pk>/cancel/', OrderCancelView.as_view()),
    path('api/v1/orders/<int:pk>/discount/', OrderDiscountView.as_view()),
    path('api/v1/orders/<int:pk>/refund/', OrderRefundView.as_view()),
    path('api/v1/orders/<int:pk>/print/', ReceiptPrintView.as_view()),
    path('api/v1/kitchen/orders/', KitchenView.as_view()),
    path('api/v1/kitchen/orders/<int:pk>/status/', KitchenStatusView.as_view()),
    path('api/v1/sales/summary/', SalesSummaryView.as_view()),
    path('api/v1/shift/', ShiftView.as_view()),
    path('api/v1/shift/history/', ShiftHistoryView.as_view()),
    path('api/v1/sales/board/', SalesBoardView.as_view()),
    path('api/v1/reports/sales/', SalesReportView.as_view()),
    path('api/v1/reports/sales/export/', SalesReportExportView.as_view()),
    path('api/v1/stock/', StockView.as_view()),
    path('api/v1/stock/usage/', StockUsageView.as_view()),
    path('api/v1/daily-usage/', DailyUsageView.as_view()),
    path('api/v1/daily-usage/compare/', UsageComparisonView.as_view()),
    path('api/v1/dashboard/', DashboardView.as_view()),
    path('api/v1/finance/', FinanceView.as_view()),
    path('api/v1/assistant/chat/', AssistantChatView.as_view()),
    path('api/v1/assistant/chats/', AssistantChatListView.as_view()),
    path('api/v1/assistant/chats/<int:pk>/', AssistantChatDetailView.as_view()),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
