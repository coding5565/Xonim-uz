from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from catalog.models import Dish


class Command(BaseCommand):
    help = "Attach the locally downloaded temporary photos to the starter menu."

    def handle(self, *args, **options):
        media_root = Path(__file__).resolve().parents[3] / "media" / "dishes"
        image_by_dish = {
            "O‘rama manti": "manti.webp",
            "Bozor manti": "manti.webp",
            "Qovoq manti": "manti.webp",
            "Ko‘k manti": "manti.webp",
            "Oddiy manti": "manti.webp",
            "Tuxum barak": "soup.jpg",
            "Uyg‘ur": "soup.jpg",
            "Qurtoba": "soup.jpg",
            "Mastava": "soup.jpg",
            "Chuchvara": "soup.jpg",
            "Ugra": "soup.jpg",
            "Non": "bread.jpg",
            "Qatlama": "bread.jpg",
            "Sveji salat": "fresh-salad.jpg",
            "Shakarob": "shakarob.jpg",
            "Sous": "fresh-salad.jpg",
        }

        missing = [filename for filename in set(image_by_dish.values()) if not (media_root / filename).is_file()]
        if missing:
            raise CommandError(f"Rasm fayllari topilmadi: {', '.join(missing)}")

        updated = 0
        for dish in Dish.objects.filter(name__in=image_by_dish):
            filename = image_by_dish[dish.name]
            dish.image.name = f"dishes/{filename}"
            dish.save(update_fields=["image"])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f"{updated} ta taomga rasm biriktirildi."))
