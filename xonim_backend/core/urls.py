from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from catalog.views import CategoryViewSet, DishViewSet, PublicMenuView
from core.version import VersionView
from operations.assistant_chats import AssistantChatDetailView, AssistantChatListView
from operations.bonuses import BonusReportView, BonusRuleView
from operations.channel_fees import ChannelFeeView
from operations.daily_usage import DailyUsageView, UsageComparisonView
from operations.dish_prep import (
    DishPrepHistoryView,
    DishPrepLeftoverView,
    DishPrepRowView,
    DishPrepView,
    DishPrepWriteOffView,
)
from operations.finance import FinanceView
from operations.partners import (
    PartnerBoardView,
    PartnerDeliveryCancelView,
    PartnerDeliveryReportView,
    PartnerDeliverySettleView,
    PartnerDeliveryView,
    PartnerDetailView,
    PartnerListView,
    PartnerPricesView,
    PartnerReportView,
    PartnerSettlementVoidView,
)
from operations.print_queue import PrintAckView, PrintClaimView
from operations.shift import ShiftHistoryView, ShiftView
from operations.staff_meals import StaffMealRowView, StaffMealView
from operations.stock_usage import StockUsageView
from operations.telegram_bot import TelegramWebhookView
from operations.views import (
    AssistantChatView,
    BackupView,
    DashboardView,
    ExpenseViewSet,
    IngredientViewSet,
    KitchenStatusView,
    KitchenView,
    OrderCancelView,
    OrderDiscountView,
    OrderLineDetailView,
    OrderLinesView,
    OrderRefundView,
    OrderViewSet,
    PayView,
    ReceiptPrintView,
    RecipeViewSet,
    SalesBoardView,
    SalesReportExportView,
    SalesReportView,
    SalesSummaryView,
    StockView,
    TableViewSet,
)
from operations.waiters import WaiterEarningsView, WaiterPaymentView, WaiterViewSet
from users.payroll import AttendanceHistoryView, AttendanceView, PayrollView
from users.views import (
    AuditView,
    CsrfView,
    LoginView,
    LogoutView,
    MeView,
    PasswordChangeView,
    SalaryPaymentExportView,
    SalaryPaymentView,
    StaffDetailView,
    StaffView,
)

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('dishes', DishViewSet, basename='dish')
router.register('orders', OrderViewSet, basename='order')
router.register('expenses', ExpenseViewSet, basename='expense')
router.register('ingredients', IngredientViewSet, basename='ingredient')
router.register('recipes', RecipeViewSet, basename='recipe')
router.register('tables', TableViewSet, basename='table')
router.register('waiters', WaiterViewSet, basename='waiter')

urlpatterns = [
    path('api/v1/', include(router.urls)),
    path('api/v1/auth/csrf/', CsrfView.as_view()),
    path('api/v1/auth/login/', LoginView.as_view()),
    path('api/v1/auth/me/', MeView.as_view()),
    # Qaysi versiya ishlayapti va unda nima o'zgargani. Hamma rolga ochiq.
    path('api/v1/version/', VersionView.as_view()),
    path('api/v1/auth/logout/', LogoutView.as_view()),
    path('api/v1/auth/password/', PasswordChangeView.as_view()),
    path('api/v1/audit/', AuditView.as_view()),
    path('api/v1/staff/', StaffView.as_view()),
    path('api/v1/staff/<int:pk>/', StaffDetailView.as_view()),
    path('api/v1/staff/<int:pk>/salary-payments/', SalaryPaymentView.as_view()),
    path('api/v1/staff/salary-payments/export/', SalaryPaymentExportView.as_view()),
    path('api/v1/payroll/', PayrollView.as_view()),
    path('api/v1/attendance/', AttendanceView.as_view()),
    path('api/v1/staff/<int:pk>/attendance/', AttendanceHistoryView.as_view()),
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
    path('api/v1/reports/waiters/', WaiterEarningsView.as_view()),
    path('api/v1/waiters/<int:pk>/payments/', WaiterPaymentView.as_view()),
    path('api/v1/reports/sales/export/', SalesReportExportView.as_view()),
    path('api/v1/stock/', StockView.as_view()),
    path('api/v1/stock/usage/', StockUsageView.as_view()),
    path('api/v1/dish-prep/', DishPrepView.as_view()),
    path('api/v1/dish-prep/history/', DishPrepHistoryView.as_view()),
    path('api/v1/dish-prep/<int:pk>/', DishPrepRowView.as_view()),
    path('api/v1/dish-prep/leftovers/', DishPrepLeftoverView.as_view()),
    path('api/v1/dish-prep/write-off/', DishPrepWriteOffView.as_view()),
    path('api/v1/daily-usage/', DailyUsageView.as_view()),
    path('api/v1/daily-usage/compare/', UsageComparisonView.as_view()),
    path('api/v1/dashboard/', DashboardView.as_view()),
    path('api/v1/finance/', FinanceView.as_view()),
    # Hamkorlar: maktab va universitetga taom jo'natish va hisob-kitob.
    path('api/v1/partners/', PartnerListView.as_view()),
    path('api/v1/partners/<int:pk>/', PartnerDetailView.as_view()),
    path('api/v1/partners/<int:pk>/prices/', PartnerPricesView.as_view()),
    path('api/v1/partner-deliveries/', PartnerDeliveryView.as_view()),
    path('api/v1/partner-deliveries/<int:pk>/report/', PartnerDeliveryReportView.as_view()),
    path('api/v1/partner-deliveries/<int:pk>/settle/', PartnerDeliverySettleView.as_view()),
    path('api/v1/partner-deliveries/<int:pk>/cancel/', PartnerDeliveryCancelView.as_view()),
    path('api/v1/partner-settlements/<int:pk>/void/', PartnerSettlementVoidView.as_view()),
    path('api/v1/partner-board/', PartnerBoardView.as_view()),
    path('api/v1/reports/partners/', PartnerReportView.as_view()),
    path('api/v1/channel-fees/', ChannelFeeView.as_view()),
    # Aksiya bonusi: qoidani superadmin belgilaydi, hisobotni kassir ham ko'radi.
    path('api/v1/bonus-rules/', BonusRuleView.as_view()),
    path('api/v1/bonuses/', BonusReportView.as_view()),
    # Hodimlar ovqati: pul olinmaydi, lekin ovqat ombordan chiqadi.
    path('api/v1/staff-meals/', StaffMealView.as_view()),
    path('api/v1/staff-meals/<int:pk>/', StaffMealRowView.as_view()),
    path('api/v1/backup/', BackupView.as_view()),
    path('api/v1/telegram/webhook/', TelegramWebhookView.as_view()),
    path('api/v1/print/claim/', PrintClaimView.as_view()),
    path('api/v1/print/ack/', PrintAckView.as_view()),
    path('api/v1/assistant/chat/', AssistantChatView.as_view()),
    path('api/v1/assistant/chats/', AssistantChatListView.as_view()),
    path('api/v1/assistant/chats/<int:pk>/', AssistantChatDetailView.as_view()),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
