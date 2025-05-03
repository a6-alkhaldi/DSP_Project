import re
from django import template

from recipes.models import DietaryRestriction, Recipe

register = template.Library()

@register.filter
def split(value, delimiter='\n'):
    """Splits a string by the given delimiter and returns a list."""
    if not value:
        return []
    return value.split(delimiter)

@register.simple_tag
def param_replace(request, **kwargs):
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value is None:
            if key in params:
                del params[key]
        else:
            params[key] = value
    return params.urlencode()

@register.filter
def remove_from_list(value, arg):
    """Removes a value from a comma-separated list"""
    items = arg.split(',')
    return ','.join([i for i in items if i != str(value)])

@register.filter
def get_category_label(value):
    return dict(Recipe.CATEGORY_CHOICES).get(value, value)

@register.filter
def get_dietary_tag(tag_id):
    try:
        return DietaryRestriction.objects.get(id=int(tag_id))
    except (ValueError, DietaryRestriction.DoesNotExist):
        return None
    
@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def filter_by_day(recipes, day):
    return recipes.filter(day=day)

@register.filter
def count_ingredients(value):
    """Count non-empty lines in a string, typically used for ingredient lists."""
    if not value:
        return 0
    # Split by newlines and filter out empty lines
    lines = [line.strip() for line in value.split('\n') if line.strip()]
    return len(lines)

