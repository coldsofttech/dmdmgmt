from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    if not isinstance(dictionary, dict):
        return None
    value = dictionary.get(key)
    if value is None:
        try:
            value = dictionary.get(int(key))
        except (TypeError, ValueError):
            pass
    return value