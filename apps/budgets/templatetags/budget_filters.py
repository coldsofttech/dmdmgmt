from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()


@register.filter(name='gbp')
def gbp(value):
    if value is None or value == '':
        return '—'
    try:
        return f'£{Decimal(str(value)):,.2f}'
    except (InvalidOperation, TypeError, ValueError):
        return '—'