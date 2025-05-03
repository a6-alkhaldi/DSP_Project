from django.apps import AppConfig
from django.db.models.signals import post_migrate

class RecipesConfig(AppConfig):
    name = 'recipes'

    def ready(self):
        from .models import DietaryRestriction

        def create_dietary_restrictions(sender, **kwargs):
            for code, _label in DietaryRestriction.DIET_CHOICES:
                DietaryRestriction.objects.get_or_create(name=code)

        post_migrate.connect(create_dietary_restrictions, sender=self)