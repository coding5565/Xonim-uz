from decimal import Decimal

from django.core.management.base import BaseCommand

from catalog.models import Dish
from operations.models import Ingredient, Recipe, RecipeLine
from users.models import Branch


class Command(BaseCommand):
    help = "Load the supplied starter recipe calculations and their batch costs."

    def handle(self, *args, **options):
        recipes = [
            {
                "name": "Uyg‘ur manti", "dish": "Uyg‘ur", "yield": "24", "yield_unit": "dona", "price": "11000",
                "lines": [("Go‘sht", "0.375", "60000"), ("Piyoz", "0.250", "1000"), ("Mol yog‘i", "0.125", "2500"), ("Qo‘y yog‘i", "0.125", "3750"), ("Un", "0.100", "600")],
            },
            {
                "name": "O‘rama manti", "dish": "O‘rama manti", "yield": "3", "yield_unit": "porsiya", "price": "13000",
                "lines": [("Kartoshka", "0.750", "3750"), ("Un", "0.400", "2500"), ("Go‘sht", "0.100", "15000"), ("Piyoz", "0.800", "2240"), ("Yog‘", "0.065", "1300"), ("Ziravorlar", "0.001", "1000")],
            },
            {
                "name": "Oddiy manti", "dish": "Oddiy manti", "yield": "24", "yield_unit": "dona", "price": "10000",
                "lines": [("Go‘sht", "0.300", "40000"), ("Piyoz", "0.350", "1250"), ("Kartoshka", "0.150", "750"), ("Yog‘", "0.125", "2400"), ("Un", "0.200", "1200"), ("Ziravorlar", "0.001", "1000")],
            },
            {
                "name": "Bulyon", "dish": None, "yield": "6", "yield_unit": "porsiya", "price": "0",
                "lines": [("Kartoshka", "0.800", "3900"), ("Sabzi", "0.500", "4500"), ("Piyoz", "0.400", "1120"), ("Go‘sht", "0.300", "45000"), ("Balgarskiy qalampir", "0.150", "1200")],
            },
            {
                "name": "Qovoq manti", "dish": "Qovoq manti", "yield": "24", "yield_unit": "dona", "price": "7000",
                "lines": [("Un", "0.400", "2500"), ("Oshqovoq", "1.000", "0"), ("Piyoz", "0.250", "1000"), ("Yog‘", "0.150", "3000"), ("Ziravorlar", "0.001", "1000")],
            },
            {
                "name": "Ko‘k manti", "dish": "Ko‘k manti", "yield": "24", "yield_unit": "dona", "price": "7000",
                "lines": [("Un", "0.400", "2500"), ("Ko‘kat", "1.000", "0"), ("Piyoz", "0.250", "1000"), ("Yog‘", "0.150", "3000")],
            },
        ]

        for branch in Branch.objects.all():
            ingredients = {}
            for recipe_data in recipes:
                for name, _, _ in recipe_data["lines"]:
                    ingredient, _ = Ingredient.objects.get_or_create(branch=branch, name=name, defaults={"unit": "kg", "minimum": Decimal("0")})
                    ingredients[name] = ingredient

            for recipe_data in recipes:
                dish = Dish.objects.filter(branch=branch, name=recipe_data["dish"]).first() if recipe_data["dish"] else None
                recipe, _ = Recipe.objects.update_or_create(
                    branch=branch, name=recipe_data["name"],
                    defaults={"dish": dish, "yield_quantity": Decimal(recipe_data["yield"]), "yield_unit": recipe_data["yield_unit"], "active": True},
                )
                recipe.lines.all().delete()
                RecipeLine.objects.bulk_create([
                    RecipeLine(recipe=recipe, ingredient=ingredients[name], quantity=Decimal(quantity), batch_cost=Decimal(cost))
                    for name, quantity, cost in recipe_data["lines"]
                ])

        self.stdout.write(self.style.SUCCESS(f"{len(recipes)} ta retsept va masalliqlar saqlandi."))
