import datetime
from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Sprint


def _sprint_duration() -> int:
    try:
        from apps.configurations.services import ConfigurationService
        return ConfigurationService.get_int('SPRINT_DURATION_DAYS', fallback=10)
    except Exception:
        return 10


def _resolve_start_number() -> int:
    max_num = Sprint.objects.aggregate(m=__import__('django.db.models', fromlist=['Max']).Max('sprint_number'))['m']
    if max_num is not None:
        return max_num + 1
    # No sprints anywhere — start from configured value
    try:
        from apps.configurations.services import ConfigurationService
        return ConfigurationService.get_int('SPRINT_START_NUMBER', fallback=1)
    except Exception:
        return 1


def _last_working_day_after_n_slots(start: datetime.date, n: int) -> datetime.date:
    count   = 0
    current = start
    one     = datetime.timedelta(days=1)
    while True:
        if current.weekday() < 5:   # Mon–Fri
            count += 1
            if count == n:
                return current
        current += one


def _sprint_end_date(start: datetime.date, n: int) -> datetime.date:
    last_wd = _last_working_day_after_n_slots(start, n)
    # Days until the next Sunday (weekday 6); 0 if already Sunday
    days_to_sunday = (6 - last_wd.weekday()) % 7
    if days_to_sunday == 0:
        # Already a Sunday — shouldn't happen for standard Mon–Fri sprints
        # but handle gracefully
        return last_wd
    return last_wd + datetime.timedelta(days=days_to_sunday)


def _next_sprint_start(sprint_end: datetime.date) -> datetime.date:
    nxt = sprint_end + datetime.timedelta(days=1)
    # Guard: ensure it really is a Monday (handles edge cases like FY boundary caps)
    while nxt.weekday() != 0:   # 0 = Monday
        nxt += datetime.timedelta(days=1)
    return nxt


class SprintService:

    @staticmethod
    def list_sprints(financial_year_id: int = None):
        qs = Sprint.objects.select_related('financial_year').all()
        if financial_year_id:
            qs = qs.filter(financial_year_id=financial_year_id)
        return qs

    @staticmethod
    def get_sprint(sprint_id: int) -> Sprint:
        return Sprint.objects.select_related('financial_year').get(pk=sprint_id)

    @staticmethod
    def get_active_fy():
        try:
            from apps.financial_years.models import FinancialYear
            return FinancialYear.objects.filter(is_active=True).first()
        except Exception:
            return None

    @staticmethod
    @transaction.atomic
    def generate_sprints(financial_year_id: int) -> list:
        # from apps.financial_years.models import FinancialYear
        # fy = FinancialYear.objects.get(pk=financial_year_id)

        # # Block if sprints already exist FOR THIS FY
        # if Sprint.objects.filter(financial_year_id=financial_year_id).exists():
        #     raise ValidationError(
        #         f'Sprints already exist for {fy.long_fy}. '
        #         'Delete all existing sprints for this FY before regenerating.'
        #     )

        # # Determine first sprint start: on or after fy.start_date, must be Monday
        # first_start = fy.start_date
        # while first_start.weekday() != 0:   # advance to next Monday
        #     first_start += datetime.timedelta(days=1)

        # if first_start > fy.end_date:
        #     raise ValidationError(
        #         f'Could not find a Monday within {fy.long_fy}. '
        #         'Check the financial year dates.'
        #     )

        # duration  = _sprint_duration()
        # fy_end    = fy.end_date
        # start_num = _resolve_start_number()

        # sprints = []
        # current = first_start
        # num     = start_num

        # while current <= fy_end:
        #     # Calculate end date (Sunday after last working day)
        #     end = _sprint_end_date(current, duration)

        #     # Cap at FY boundary
        #     if end > fy_end:
        #         end = fy_end

        #     sprint = Sprint(
        #         financial_year_id = financial_year_id,
        #         sprint_number     = num,
        #         name              = f'Sprint {num}',
        #         start_date        = current,
        #         end_date          = end,
        #         is_overridden     = False,
        #     )
        #     sprint.full_clean()
        #     sprint.save()
        #     sprints.append(sprint)

        #     # Next sprint starts the Monday after this sprint ends
        #     next_start = _next_sprint_start(end)
        #     if next_start > fy_end:
        #         break
        #     current = next_start
        #     num    += 1

        # return sprints
        from apps.financial_years.models import FinancialYear
        fy = FinancialYear.objects.get(pk=financial_year_id)
 
        # Block if sprints already exist FOR THIS FY
        if Sprint.objects.filter(financial_year_id=financial_year_id).exists():
            raise ValidationError(
                f'Sprints already exist for {fy.long_fy}. '
                'Delete all existing sprints for this FY before regenerating.'
            )
 
        # Determine first sprint start: on or after fy.start_date, must be Monday
        first_start = fy.start_date
        while first_start.weekday() != 0:   # advance to next Monday
            first_start += datetime.timedelta(days=1)
 
        if first_start > fy.end_date:
            raise ValidationError(
                f'Could not find a Monday within {fy.long_fy}. '
                'Check the financial year dates.'
            )
 
        duration  = _sprint_duration()
        start_num = _resolve_start_number()
 
        # If the FY has no end_date yet (newly created), generate sprints for
        # a full year from start_date.  The FY end_date will be set below to
        # the last sprint's end date once generation is complete.
        if fy.end_date:
            fy_end = fy.end_date
        else:
            # Default boundary: approximately one year from first sprint start
            fy_end = first_start + datetime.timedelta(days=365)
 
        sprints = []
        current = first_start
        num     = start_num
 
        while current <= fy_end:
            # Calculate end date (Sunday after last working day)
            end = _sprint_end_date(current, duration)
 
            # Cap at FY boundary
            if end > fy_end:
                end = fy_end
 
            sprint = Sprint(
                financial_year_id = financial_year_id,
                sprint_number     = num,
                name              = f'Sprint {num}',
                start_date        = current,
                end_date          = end,
                is_overridden     = False,
            )
            sprint.full_clean()
            sprint.save()
            sprints.append(sprint)
 
            # Next sprint starts the Monday after this sprint ends
            next_start = _next_sprint_start(end)
            if next_start > fy_end:
                break
            current = next_start
            num    += 1
 
        # ── Update the FY's end_date to the last sprint's end date ───────────
        # This is the single source of truth for when the financial year ends.
        # if sprints:
        #     last_sprint_end = sprints[-1].end_date
        #     from apps.financial_years.services import FinancialYearService
        #     FinancialYearService.set_end_date(financial_year_id, last_sprint_end)
 
        return sprints

    @staticmethod
    def delete_all_for_fy(financial_year_id: int) -> int:
        deleted, _ = Sprint.objects.filter(
            financial_year_id=financial_year_id
        ).delete()
        return deleted

    @staticmethod
    @transaction.atomic
    def create_sprint(data: dict) -> Sprint:
        sprint = Sprint(
            financial_year_id = data['financial_year_id'],
            sprint_number     = data['sprint_number'],
            name              = data['name'],
            start_date        = data['start_date'],
            end_date          = data['end_date'],
            notes             = data.get('notes', ''),
            is_overridden     = True,
        )
        sprint.full_clean()
        sprint.save()
        return sprint

    @staticmethod
    @transaction.atomic
    def update_sprint(sprint_id: int, data: dict) -> Sprint:
        sprint = Sprint.objects.get(pk=sprint_id)

        changed = any(
            field in data and getattr(sprint, field) != data[field]
            for field in ('name', 'start_date', 'end_date', 'sprint_number')
        )

        if 'sprint_number' in data: sprint.sprint_number = data['sprint_number']
        if 'name'          in data: sprint.name          = data['name']
        if 'start_date'    in data: sprint.start_date    = data['start_date']
        if 'end_date'      in data: sprint.end_date      = data['end_date']
        if 'notes'         in data: sprint.notes         = data['notes']

        if changed:
            sprint.is_overridden = True

        sprint.full_clean()
        sprint.save()
        return sprint

    @staticmethod
    def delete_sprint(sprint_id: int) -> None:
        Sprint.objects.get(pk=sprint_id).delete()

    @staticmethod
    def sprint_capacity(sprint: Sprint) -> dict:
        try:
            from apps.team_members.models import TeamMember
            from apps.leaves.models import Leave, calc_working_days

            member_count = TeamMember.objects.filter(is_active=True).count()
            working_days = sprint.working_days

            gross = member_count * working_days

            # Leave days overlapping this sprint (clipped to the sprint window)
            overlapping_leaves = Leave.objects.filter(
                financial_year_id = sprint.financial_year_id,
                start_date__lte   = sprint.end_date,
                end_date__gte     = sprint.start_date,
            )

            leave_days = 0
            for leave in overlapping_leaves:
                clipped_start = max(leave.start_date, sprint.start_date)
                clipped_end   = min(leave.end_date,   sprint.end_date)
                leave_days += calc_working_days(
                    clipped_start, clipped_end,
                    financial_year_id=sprint.financial_year_id,
                )

            return {
                'member_count':  member_count,
                'working_days':  working_days,
                'gross_days':    gross,
                'leave_days':    leave_days,
                'net_capacity':  max(gross - leave_days, 0),
            }

        except Exception:
            return {
                'member_count': 0,
                'working_days': sprint.working_days,
                'gross_days':   0,
                'leave_days':   0,
                'net_capacity': 0,
            }

    @staticmethod
    def check_consistency(financial_year_id: int) -> list:
        sprints  = list(Sprint.objects.filter(
            financial_year_id=financial_year_id
        ).order_by('start_date'))
        warnings = []
        for i, s in enumerate(sprints):
            if i > 0:
                prev = sprints[i - 1]
                if s.start_date <= prev.end_date:
                    warnings.append({
                        'sprint_id':   s.pk,
                        'sprint_name': s.name,
                        'issue': f'Overlaps with {prev.name} (ends {prev.end_date:%d %b %Y}).',
                    })
                elif (s.start_date - prev.end_date).days > 3:
                    warnings.append({
                        'sprint_id':   s.pk,
                        'sprint_name': s.name,
                        'issue': (
                            f'Gap of {(s.start_date - prev.end_date).days - 1} days '
                            f'after {prev.name}.'
                        ),
                    })
        return warnings