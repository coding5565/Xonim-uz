from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from .models import SALE_PAYMENT_CHOICES, Order, OrderLine, Table, Expense, Ingredient, Recipe, RecipeLine, StockMovement
from core.i18n import _


class LineInput(serializers.Serializer):
    dish = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=999)
    note = serializers.CharField(max_length=200, allow_blank=True, default='')


class TableSerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)
    open_order = serializers.SerializerMethodField()

    class Meta:
        model = Table
        fields = ['id', 'number', 'name', 'seats', 'zone', 'seating', 'active', 'label', 'open_order']

    def get_open_order(self, obj):
        """Stol xaritasi bitta so'rovda chiziladi, shuning uchun ochiq hisob shu yerda."""
        order = next((item for item in obj.orders.all() if item.status == 'open'), None)
        if not order:
            return None
        return {
            'id': order.id,
            'total': str(order.total),
            'items': sum(line.quantity for line in order.lines.all()),
            'waiter': order.waiter,
            'created_at': order.created_at,
        }

    def validate_number(self, value):
        branch = self.context['request'].user.branch
        query = Table.objects.filter(branch=branch, number=value)
        if self.instance:
            query = query.exclude(pk=self.instance.pk)
        if query.exists():
            raise serializers.ValidationError(_('Bu raqamli stol allaqachon bor.'))
        return value


class OrderInput(serializers.Serializer):
    key = serializers.UUIDField()
    table = serializers.CharField(max_length=40, allow_blank=True, default='')
    table_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    waiter = serializers.CharField(max_length=100, allow_blank=True, default='')
    lines = LineInput(many=True, allow_empty=False)
    payment_method = serializers.ChoiceField(choices=SALE_PAYMENT_CHOICES + [''], default='')

    def validate_lines(self, lines):
        if len(lines) > 100 or len({line['dish'] for line in lines}) != len(lines):
            raise serializers.ValidationError(_('Bir taomni takrorlamang; ko‘pi bilan 100 satr.'))
        return lines


class AppendLinesInput(serializers.Serializer):
    key = serializers.UUIDField()
    lines = LineInput(many=True, allow_empty=False)

    def validate_lines(self, lines):
        if len(lines) > 100 or len({line['dish'] for line in lines}) != len(lines):
            raise serializers.ValidationError(_('Bir taomni takrorlamang; ko‘pi bilan 100 satr.'))
        return lines


class OrderLineSerializer(serializers.ModelSerializer):
    added = serializers.SerializerMethodField()

    class Meta:
        model = OrderLine
        fields = ['id', 'dish', 'name', 'price', 'quantity', 'note', 'added']

    def get_added(self, obj):
        return obj.batch_key is not None


class OrderSerializer(serializers.ModelSerializer):
    lines = OrderLineSerializer(many=True, read_only=True)
    cashier_name = serializers.CharField(source='cashier.first_name', read_only=True)
    status_label = serializers.CharField(source='get_status_display', read_only=True)
    voided_by_name = serializers.CharField(source='voided_by.first_name', read_only=True, default='')
    print_problems = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'table', 'waiter', 'status', 'status_label', 'total', 'discount', 'discount_reason', 'payment_method', 'created_at', 'paid_at', 'preparation_status', 'started_at', 'ready_at', 'served_at', 'cashier_name', 'lines', 'print_problems', 'void_reason', 'voided_at', 'voided_by_name']

    def get_print_problems(self, obj):
        """Talon chiqmagan bo'lsa kassir buni ko'rishi shart, aks holda ovqat pishmay qoladi."""
        return getattr(obj, 'print_problems', [])


class ExpenseSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.first_name', read_only=True)

    class Meta:
        model = Expense
        fields = ['id', 'key', 'category', 'purpose', 'recipient', 'amount', 'payment_method', 'date', 'actor_name']
        extra_kwargs = {'amount': {'min_value': 1}}

    def validate_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError(_('Kelajakdagi xarajatni hisobga olish mumkin emas.'))
        return value


class IngredientSerializer(serializers.ModelSerializer):
    # Model xossasi bo'lgani uchun aniq e'lon qilinadi: aks holda DRF uni float
    # qilib yuboradi va boshqa pul maydonlaridan farq qilib qoladi.
    stock_value = serializers.DecimalField(max_digits=18, decimal_places=2, read_only=True)

    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'unit', 'quantity', 'minimum', 'unit_cost', 'stock_value']
        # Qoldiq faqat kirim va sarf orqali o'zgaradi; narxni esa qo'lda
        # kiritish mumkin va keyin har kirim uni o'rtacha tortilgan usulda
        # qayta hisoblaydi.
        read_only_fields = ['quantity']
        extra_kwargs = {
            'minimum': {'min_value': 0},
            'unit_cost': {'min_value': 0, 'required': False},
        }

    def validate_name(self, value):
        if Ingredient.objects.filter(branch=self.context['request'].user.branch, name__iexact=value).exists():
            raise serializers.ValidationError(_('Bu mahsulot mavjud.'))
        return value


class MovementInput(serializers.Serializer):
    key = serializers.UUIDField()
    ingredient = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(choices=['receipt', 'consumption'])
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal('0.001'))
    # Kirimda «qancha so'mga olindi» — ombor tannarxi shundan hisoblanadi.
    # Sarfda kiritilmaydi: narx joriy o'rtacha tannarxdan olinadi.
    cost_total = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal('0'), required=False, default=Decimal('0'))
    date = serializers.DateField()
    note = serializers.CharField(max_length=250)

    def validate_date(self, value):
        if value != timezone.localdate():
            raise serializers.ValidationError(_('Dastlabki versiyada ombor harakati faqat bugungi sana bilan.'))
        return value

    def validate(self, attrs):
        if attrs['kind'] != 'receipt' and attrs.get('cost_total'):
            raise serializers.ValidationError({'cost_total': _('Narx faqat kirimda kiritiladi.')})
        return attrs


class MovementSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name')
    unit = serializers.CharField(source='ingredient.unit')

    class Meta:
        model = StockMovement
        fields = ['id', 'ingredient_name', 'unit', 'kind', 'quantity', 'unit_cost', 'cost_total', 'date', 'note']


class RecipeLineSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    unit = serializers.CharField(source='ingredient.unit', read_only=True)
    unit_price = serializers.DecimalField(
        source='ingredient.unit_cost', max_digits=14, decimal_places=4, read_only=True,
    )

    class Meta:
        model = RecipeLine
        # batch_cost endi kiritilmaydi: u miqdor × masalliq narxi bo'lib
        # avtomatik hisoblanadi. Shunda bir masalliq turli retseptlarda
        # turlicha narxda turib qolmaydi.
        fields = ['id', 'ingredient', 'ingredient_name', 'unit', 'unit_price', 'quantity', 'batch_cost']
        read_only_fields = ['batch_cost']
        extra_kwargs = {'quantity': {'min_value': Decimal('0.001')}}


class RecipeSerializer(serializers.ModelSerializer):
    lines = RecipeLineSerializer(many=True)
    dish_name = serializers.CharField(source='dish.name', read_only=True)
    batch_cost = serializers.SerializerMethodField()
    unit_cost = serializers.SerializerMethodField()
    gross_profit = serializers.SerializerMethodField()

    class Meta:
        model = Recipe
        fields = ['id', 'dish', 'dish_name', 'name', 'yield_quantity', 'yield_unit', 'selling_price', 'active', 'updated_at', 'lines', 'batch_cost', 'unit_cost', 'gross_profit']
        extra_kwargs = {
            'dish': {'required': False, 'allow_null': True},
            'selling_price': {'min_value': 0},
            'yield_quantity': {'min_value': Decimal('0.001')},
        }

    def _cost(self, obj):
        return sum((line.batch_cost for line in obj.lines.all()), Decimal('0'))

    def get_batch_cost(self, obj):
        return self._cost(obj)

    def get_unit_cost(self, obj):
        return self._cost(obj) / obj.yield_quantity

    def get_gross_profit(self, obj):
        return obj.selling_price - self.get_unit_cost(obj)

    def validate(self, attrs):
        request = self.context['request']
        dish = attrs.get('dish', getattr(self.instance, 'dish', None))
        if dish and dish.branch_id != request.user.branch_id:
            raise serializers.ValidationError({'dish': _('Taom boshqa filialga tegishli.')})
        lines = attrs.get('lines')
        if lines is not None:
            if not lines:
                raise serializers.ValidationError({'lines': _('Kamida bitta masalliq kiriting.')})
            ids = [line['ingredient'].id for line in lines]
            if len(ids) != len(set(ids)):
                raise serializers.ValidationError({'lines': _('Bir mahsulotni faqat bir marta kiriting.')})
            if any(line['ingredient'].branch_id != request.user.branch_id for line in lines):
                raise serializers.ValidationError({'lines': _('Mahsulot boshqa filialga tegishli.')})
        return attrs

    @staticmethod
    def _rows(recipe, lines):
        """Qator narxini masalliq narxidan hisoblaydi.

        batch_cost saqlanadi, chunki eski hisobotlar unga tayanadi — lekin
        endi u qo'lda kiritilmaydi, har saqlashda qayta hisoblanadi. Shu bilan
        bitta masalliq ikki retseptda ikki xil narxda turib qolmaydi.
        """
        return [
            RecipeLine(
                recipe=recipe,
                batch_cost=(line['quantity'] * line['ingredient'].unit_cost).quantize(Decimal('0.01')),
                **line,
            )
            for line in lines
        ]

    def create(self, validated_data):
        lines = validated_data.pop('lines')
        recipe = Recipe.objects.create(branch=self.context['request'].user.branch, **validated_data)
        RecipeLine.objects.bulk_create(self._rows(recipe, lines))
        return recipe

    def update(self, instance, validated_data):
        lines = validated_data.pop('lines', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            RecipeLine.objects.bulk_create(self._rows(instance, lines))
        return instance
