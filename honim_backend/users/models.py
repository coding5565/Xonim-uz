from django.contrib.auth.models import AbstractUser
from django.db import models


class Branch(models.Model):
    name = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)


class User(AbstractUser):
    class Role(models.TextChoices):
        OWNER = 'owner', 'Superadmin'
        ADMIN = 'admin', 'Admin'
        CASHIER = 'cashier', 'Kassir'
        KITCHEN = 'kitchen', 'Oshxona'

    role = models.CharField(max_length=12, choices=Role.choices, default=Role.CASHIER)
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, null=True)
    phone = models.CharField(max_length=30, blank=True)
    salary = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    hired_at = models.DateField(null=True, blank=True)
    notes = models.CharField(max_length=300, blank=True)


class AuditEvent(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    actor = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    description = models.CharField(max_length=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']
