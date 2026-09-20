"""Rol bo'yicha ruxsatlar.

Tizimda uch rol bor: superadmin (owner), kassir (cashier) va oshxona
(kitchen). «Admin» roli olib tashlandi — uning kundalik ishlari kassirga,
qoida va nazorat qismi superadminga o'tdi.

Qoida sodda: kassir kunni olib borishi uchun kerak bo'lgan hamma narsani
qila oladi; menyu narxi, retsept va nazorat hisobotlari superadminda qoladi.
"""
from rest_framework.permissions import BasePermission


def _member(request):
    return bool(request.user.is_authenticated and request.user.branch_id)


class BranchMember(BasePermission):
    """Filialdagi har qanday xodim."""

    def has_permission(self, request, view):
        return _member(request)


class SalesOnly(BasePermission):
    """Kassir ishi: savdo, hisob, ombor, xarajat, kunlik hisobot."""

    def has_permission(self, request, view):
        return _member(request) and request.user.role in ('owner', 'cashier')


class KitchenOnly(BasePermission):
    """Oshxona ekrani."""

    def has_permission(self, request, view):
        return _member(request) and request.user.role in ('owner', 'kitchen')


class OwnerOnly(BasePermission):
    """Qoida va nazorat: menyu, retsept, hisobotlar, xodimlar, jurnal."""

    def has_permission(self, request, view):
        return _member(request) and request.user.role == 'owner'
