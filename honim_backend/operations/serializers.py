from decimal import Decimal
from django.utils import timezone
from rest_framework import serializers
from .models import Order, OrderLine, Expense, Ingredient, Recipe, RecipeLine, StockMovement


class LineInput(serializers.Serializer):
    dish = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=999)
    note = serializers.CharField(max_length=200, allow_blank=True, default='')


class OrderInput(serializers.Serializer):
    key = serializers.UUIDField()
    table = serializers.CharField(max_length=40, allow_blank=True, default='')
    waiter = serializers.CharField(max_length=100, allow_blank=True, default='')
    lines = LineInput(many=True, allow_empty=False)
    payment_method = serializers.ChoiceField(choices=['cash', 'card', ''], default='')

    def validate_lines(self, lines):
        if len(lines) > 100 or len({line['dish'] for line in lines}) != len(lines):
            raise serializers.ValidationError('Bir taomni takrorlamang; ko‘pi bilan 100 satr.')
        return lines


class OrderLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderLine
        fields = ['id', 'dish', 'name', 'price', 'quantity', 'note']


class OrderSerializer(serializers.ModelSerializer):
    lines = OrderLineSerializer(many=True, read_only=True)
    cashier_name = serializers.CharField(source='cashier.first_name', read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'table', 'waiter', 'status', 'total', 'payment_method', 'created_at', 'paid_at', 'preparation_status', 'started_at', 'ready_at', 'served_at', 'cashier_name', 'lines']


class ExpenseSerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source='actor.first_name', read_only=True)

    class Meta:
        model = Expense
        fields = ['id', 'key', 'category', 'purpose', 'recipient', 'amount', 'payment_method', 'date', 'actor_name']
        extra_kwargs = {'amount': {'min_value': 1}}

    def validate_date(self, value):
        if value > timezone.localdate():
            raise serializers.ValidationError('Kelajakdagi xarajatni hisobga olish mumkin emas.')
        return value


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = ['id', 'name', 'unit', 'quantity', 'minimum']
        read_only_fields = ['quantity']
        extra_kwargs = {'minimum': {'min_value': 0}}

    def validate_name(self, value):
        if Ingredient.objects.filter(branch=self.context['request'].user.branch, name__iexact=value).exists():
            raise serializers.ValidationError('Bu mahsulot mavjud.')
        return value


class MovementInput(serializers.Serializer):
    key = serializers.UUIDField()
    ingredient = serializers.IntegerField(min_value=1)
    kind = serializers.ChoiceField(choices=['receipt', 'consumption'])
    quantity = serializers.DecimalField(max_digits=14, decimal_places=3, min_value=Decimal('0.001'))
    date = serializers.DateField()
    note = serializers.CharField(max_length=250)

    def validate_date(self, value):
        if value != timezone.localdate():
            raise serializers.ValidationError('Dastlabki versiyada ombor harakati faqat bugungi sana bilan.')
        return value


class MovementSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name')
    unit = serializers.CharField(source='ingredient.unit')

    class Meta:
        model = StockMovement
        fields = ['id', 'ingredient_name', 'unit', 'kind', 'quantity', 'date', 'note']


class RecipeLineSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    unit = serializers.CharField(source='ingredient.unit', read_only=True)

    class Meta:
        model = RecipeLine
        fields = ['id', 'ingredient', 'ingredient_name', 'unit', 'quantity', 'batch_cost']
        extra_kwargs = {'batch_cost': {'min_value': 0}, 'quantity': {'min_value': Decimal('0.001')}}


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
            raise serializers.ValidationError({'dish': 'Taom boshqa filialga tegishli.'})
        lines = attrs.get('lines')
        if lines is not None:
            if not lines:
                raise serializers.ValidationError({'lines': 'Kamida bitta masalliq kiriting.'})
            ids = [line['ingredient'].id for line in lines]
            if len(ids) != len(set(ids)):
                raise serializers.ValidationError({'lines': 'Bir mahsulotni faqat bir marta kiriting.'})
            if any(line['ingredient'].branch_id != request.user.branch_id for line in lines):
                raise serializers.ValidationError({'lines': 'Mahsulot boshqa filialga tegishli.'})
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop('lines')
        recipe = Recipe.objects.create(branch=self.context['request'].user.branch, **validated_data)
        RecipeLine.objects.bulk_create([RecipeLine(recipe=recipe, **line) for line in lines])
        return recipe

    def update(self, instance, validated_data):
        lines = validated_data.pop('lines', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if lines is not None:
            instance.lines.all().delete()
            RecipeLine.objects.bulk_create([RecipeLine(recipe=instance, **line) for line in lines])
        return instance
