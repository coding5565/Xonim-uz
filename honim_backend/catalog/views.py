from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from users.models import Branch, AuditEvent
from users.permissions import BranchMember, ManagerOnly
from .models import Category, Dish
from .serializers import CategorySerializer, DishSerializer


class CatalogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin, viewsets.GenericViewSet):
    def get_permissions(self):
        return [BranchMember() if self.action in ('list', 'retrieve') else ManagerOnly()]

    def get_queryset(self):
        return self.queryset.filter(branch=self.request.user.branch)

    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save(branch=self.request.user.branch)
        AuditEvent.objects.create(branch=self.request.user.branch, actor=self.request.user, action='catalog.create', description=obj.name)

    @transaction.atomic
    def perform_update(self, serializer):
        obj = serializer.save()
        AuditEvent.objects.create(branch=self.request.user.branch, actor=self.request.user, action='catalog.update', description=obj.name)


class CategoryViewSet(CatalogViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class DishViewSet(CatalogViewSet):
    queryset = Dish.objects.select_related('category').all()
    serializer_class = DishSerializer


class PublicMenuView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug):
        branch = get_object_or_404(Branch, slug=slug)
        return Response({'name': branch.name, 'categories': CategorySerializer(Category.objects.filter(branch=branch), many=True).data, 'dishes': DishSerializer(Dish.objects.filter(branch=branch, archived=False).select_related('category'), many=True, context={'request': request}).data})
