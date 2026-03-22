from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Holiday


class HolidayService:
    @staticmethod
    def list_holidays(financial_year_id: int = None):
        qs = Holiday.objects.select_related('financial_year').all()
        if financial_year_id:
            qs = qs.filter(financial_year_id=financial_year_id)
        return qs

    @staticmethod
    def get_holiday(holiday_id: int) -> Holiday:
        return Holiday.objects.select_related('financial_year').get(pk=holiday_id)

    @staticmethod
    def count_for_fy(financial_year_id: int) -> int:
        return Holiday.objects.filter(financial_year_id=financial_year_id).count()

    @staticmethod
    @transaction.atomic
    def create_holiday(data: dict) -> Holiday:
        holiday = Holiday(
            financial_year_id = data['financial_year_id'],
            holiday_date      = data['holiday_date'],
            note              = data.get('note', '').strip(),
        )
        holiday.full_clean()
        holiday.save()
        return holiday

    @staticmethod
    @transaction.atomic
    def update_holiday(holiday_id: int, data: dict) -> Holiday:
        holiday = Holiday.objects.get(pk=holiday_id)
        if 'financial_year_id' in data:
            holiday.financial_year_id = data['financial_year_id']
        if 'holiday_date' in data:
            holiday.holiday_date = data['holiday_date']
        if 'note' in data:
            holiday.note = data['note'].strip()
        holiday.full_clean()
        holiday.save()
        return holiday

    @staticmethod
    def delete_holiday(holiday_id: int) -> None:
        Holiday.objects.get(pk=holiday_id).delete()