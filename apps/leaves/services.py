from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Leave


class LeaveService:
    @staticmethod
    def list_leaves(financial_year_id: int = None, team_member_id: int = None,
                    team_id: int = None, search: str = None):
        qs = (
            Leave.objects
            .select_related('team_member', 'team_member__team', 'financial_year')
            .all()
        )
        if financial_year_id:
            qs = qs.filter(financial_year_id=financial_year_id)
        if team_member_id:
            qs = qs.filter(team_member_id=team_member_id)
        if team_id:
            qs = qs.filter(team_member__team_id=team_id)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(team_member__display_name__icontains=search) |
                Q(team_member__first_name__icontains=search)   |
                Q(team_member__last_name__icontains=search)
            )
        return qs

    @staticmethod
    def get_leave(leave_id: int) -> Leave:
        return (
            Leave.objects
            .select_related('team_member', 'team_member__team', 'financial_year')
            .get(pk=leave_id)
        )

    @staticmethod
    def get_active_fy():
        try:
            from apps.financial_years.models import FinancialYear
            return FinancialYear.objects.filter(is_active=True).first()
        except Exception:
            return None

    @staticmethod
    def get_member_leaves_current_fy(team_member_id: int):
        fy = LeaveService.get_active_fy()
        if not fy:
            return Leave.objects.none()
        return LeaveService.list_leaves(
            financial_year_id=fy.pk,
            team_member_id=team_member_id,
        )

    @staticmethod
    def get_team_leaves_current_fy(team_id: int):
        fy = LeaveService.get_active_fy()
        if not fy:
            return Leave.objects.none()
        return LeaveService.list_leaves(
            financial_year_id=fy.pk,
            team_id=team_id,
        )
    
    @staticmethod
    def get_holiday_dates_for_fy(financial_year_id: int) -> list:
        try:
            from apps.holidays.models import Holiday
            return list(
                Holiday.objects
                .filter(financial_year_id=financial_year_id)
                .values_list('holiday_date', flat=True)
                .order_by('holiday_date')
            )
        except Exception:
            return []

    @staticmethod
    @transaction.atomic
    def create_leave(data: dict) -> Leave:
        leave = Leave(
            team_member_id  = data['team_member_id'],
            financial_year_id = data['financial_year_id'],
            start_date      = data['start_date'],
            end_date        = data['end_date'],
            note            = data.get('note', ''),
        )
        leave.full_clean()
        leave.save()
        return leave

    @staticmethod
    @transaction.atomic
    def update_leave(leave_id: int, data: dict) -> Leave:
        leave = Leave.objects.get(pk=leave_id)
        if 'team_member_id'   in data: leave.team_member_id   = data['team_member_id']
        if 'financial_year_id' in data: leave.financial_year_id = data['financial_year_id']
        if 'start_date'       in data: leave.start_date       = data['start_date']
        if 'end_date'         in data: leave.end_date         = data['end_date']
        if 'note'             in data: leave.note             = data['note']
        leave.full_clean()
        leave.save()
        return leave

    @staticmethod
    def delete_leave(leave_id: int) -> None:
        Leave.objects.get(pk=leave_id).delete()

    @staticmethod
    def total_days_for_member_fy(team_member_id: int, financial_year_id: int) -> int:
        from django.db.models import Sum
        result = Leave.objects.filter(
            team_member_id=team_member_id,
            financial_year_id=financial_year_id,
        ).aggregate(total=Sum('days'))
        return result['total'] or 0