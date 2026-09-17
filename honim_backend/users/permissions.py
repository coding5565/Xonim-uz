from rest_framework.permissions import BasePermission


class ManagerOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.branch_id and request.user.role in ('owner', 'admin'))


class BranchMember(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.branch_id)


class SalesOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.branch_id and request.user.role in ('owner', 'admin', 'cashier'))


class KitchenOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.branch_id and request.user.role in ('owner', 'admin', 'kitchen'))


class OwnerOnly(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.branch_id and request.user.role == 'owner')
