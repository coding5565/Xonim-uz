from django.db import models
from django.db.models import Q
from users.models import Branch


class Category(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['position', 'id']
        constraints = [models.UniqueConstraint(fields=['branch', 'name'], name='category_branch_name')]


class Dish(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='dishes')
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=500, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    portion = models.CharField(max_length=50, default='1 porsiya')
    image = models.ImageField(upload_to='dishes/', blank=True)
    available = models.BooleanField(default=True)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['category__position', 'id']
        constraints = [models.CheckConstraint(condition=Q(price__gt=0), name='dish_positive_price')]
