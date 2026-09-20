from io import BytesIO
from uuid import uuid4

from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from core.i18n import _

from .models import Category, Dish


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'position', 'station']

    def validate_name(self, name):
        query = Category.objects.filter(branch=self.context['request'].user.branch, name__iexact=name)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError(_('Bu kategoriya allaqachon mavjud.'))
        return name


class DishSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Dish
        fields = ['id', 'category', 'category_name', 'name', 'description', 'price', 'portion', 'image', 'available', 'archived', 'station', 'print_station']
        read_only_fields = ['print_station']
        extra_kwargs = {'price': {'min_value': 1}}

    def validate_category(self, category):
        if category.branch_id != self.context['request'].user.branch_id:
            raise serializers.ValidationError(_('Kategoriya ushbu filialga tegishli emas.'))
        return category

    def validate_name(self, name):
        # Filial ichida nom yagona (UniqueConstraint). Bu yerda tekshirilmasa
        # baza IntegrityError beradi va foydalanuvchi 500 xatosini ko'rardi.
        query = Dish.objects.filter(branch=self.context['request'].user.branch, name__iexact=name)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError(_('Bu nomli taom allaqachon bor.'))
        return name

    def validate_image(self, value):
        if not value:
            return value
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(_('Rasm 5 MB dan kichik bo‘lishi kerak.'))
        try:
            source = Image.open(value)
            if source.width * source.height > 20_000_000:
                raise serializers.ValidationError(_('Rasm o‘lchami juda katta.'))
            source = source.convert('RGB')
            source.thumbnail((1200, 1200))
            output = BytesIO()
            source.save(output, 'JPEG', quality=85)
            return ContentFile(output.getvalue(), name=f'{uuid4().hex}.jpg')
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
            raise serializers.ValidationError(_('Rasm formati noto‘g‘ri.')) from None
