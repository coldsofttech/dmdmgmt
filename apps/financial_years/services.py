from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction

from .models import FinancialYear


class FinancialYearService:
    @staticmethod
    def list_financial_years():
        return FinancialYear.objects.all().order_by('-start_date')

    @staticmethod
    def get_financial_year(fy_id: int) -> FinancialYear:
        return FinancialYear.objects.get(pk=fy_id)

    @staticmethod
    def get_active() -> FinancialYear | None:
        return FinancialYear.objects.filter(is_active=True).first()

    @staticmethod
    def get_by_short_fy(short_fy: str) -> FinancialYear:
        return FinancialYear.objects.get(short_fy=short_fy)

    @staticmethod
    @transaction.atomic
    def create_financial_year(data: dict) -> FinancialYear:
        fy = FinancialYear(
            start_date = data['start_date'],
            end_date   = data['end_date'],
            is_active  = data.get('is_active', False),
            notes      = data.get('notes', '').strip(),
        )
        fy.full_clean()
        fy.save()
        return fy

    @staticmethod
    @transaction.atomic
    def update_financial_year(fy_id: int, data: dict) -> FinancialYear:
        fy = FinancialYear.objects.get(pk=fy_id)
        if 'start_date' in data: fy.start_date = data['start_date']
        if 'end_date'   in data: fy.end_date   = data['end_date']
        if 'is_active'  in data: fy.is_active  = data['is_active']
        if 'notes'      in data: fy.notes       = data['notes'].strip()
        fy.full_clean()
        fy.save()
        return fy

    @staticmethod
    @transaction.atomic
    def set_active(fy_id: int) -> FinancialYear:
        FinancialYear.objects.exclude(pk=fy_id).update(is_active=False)
        fy = FinancialYear.objects.get(pk=fy_id)
        fy.is_active = True
        fy.save(update_fields=['is_active', 'updated_at'])
        return fy

    @staticmethod
    def delete_financial_year(fy_id: int) -> None:
        fy = FinancialYear.objects.get(pk=fy_id)
        if fy.is_active:
            raise ValidationError(
                'Cannot delete the active financial year. '
                'Set another year as active first.'
            )
        fy.delete()