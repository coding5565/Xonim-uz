from django.db import models
from django.db.models import Q

from users.models import Branch


class Station(models.TextChoices):
    """Buyurtma berilganda talon qaysi printerdan chiqishini belgilaydi."""

    KITCHEN = 'kitchen', 'Oshxona'
    COUNTER = 'counter', 'Kassa'


class Category(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT)
    name = models.CharField(max_length=100)
    position = models.PositiveIntegerField(default=0)
    station = models.CharField(max_length=10, choices=Station.choices, default=Station.KITCHEN)

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
    # Bo'sh qoldirilsa kategoriyadan meros oladi. Alohida qiymat faqat istisnolar
    # uchun: masalan ichimliklar orasida oshxonada damlanadigan choy.
    station = models.CharField(max_length=10, choices=Station.choices, blank=True)

    class Meta:
        ordering = ['category__position', 'id']
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name='dish_positive_price'),
            # Nom filial ichida yagona: chek, oshxona taloni va hisobotlar
            # taomni NOMI bilan ko'rsatadi, shuning uchun ikkita bir xil nom
            # ularni ajratib bo'lmaydigan qilib qo'yardi. Kategoriyada bu
            # cheklov boshidan bor edi, taomda esa tushib qolgan.
            models.UniqueConstraint(fields=['branch', 'name'], name='dish_branch_name'),
        ]

    @property
    def print_station(self):
        return self.station or self.category.station
