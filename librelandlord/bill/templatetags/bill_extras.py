from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """Template filter to get a value from a dictionary by key."""
    if dictionary is None:
        return ''
    return dictionary.get(key, '')
