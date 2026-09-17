from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from users.views import AuditView, CsrfView, LoginView, LogoutView, MeView, SalaryPaymentExportView, SalaryPaymentView, StaffDetailView, StaffView
from catalog.views import CategoryViewSet, DishViewSet, PublicMenuView
from operations.views import (
    AssistantChatView, DashboardView, ExpenseViewSet, IngredientViewSet, KitchenStatusView,
    KitchenView, OrderViewSet, PayView, RecipeViewSet, SalesReportExportView,
    SalesReportView, StockView,
)

router = DefaultRouter()
router.register('categories', CategoryViewSet, basename='category')
router.register('dishes', DishViewSet, basename='dish')
router.register('orders', OrderViewSet, basename='order')
router.register('expenses', ExpenseViewSet, basename='expense')
router.register('ingredients', IngredientViewSet, basename='ingredient')
router.register('recipes', RecipeViewSet, basename='recipe')

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
    path('api/v1/public/menu/<slug:slug>/', PublicMenuView.as_view()),
    path('api/v1/orders/<int:pk>/pay/', PayView.as_view()),
    path('api/v1/kitchen/orders/', KitchenView.as_view()),
    path('api/v1/kitchen/orders/<int:pk>/status/', KitchenStatusView.as_view()),
    path('api/v1/reports/sales/', SalesReportView.as_view()),
    path('api/v1/reports/sales/export/', SalesReportExportView.as_view()),
    path('api/v1/stock/', StockView.as_view()),
    path('api/v1/dashboard/', DashboardView.as_view()),
    path('api/v1/assistant/chat/', AssistantChatView.as_view()),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
