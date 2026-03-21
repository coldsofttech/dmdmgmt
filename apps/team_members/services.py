import datetime
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction
from .models import TeamMember, TeamMemberHistory


class TeamMemberService:
    @staticmethod
    def list_members(filters=None):
        qs = TeamMember.objects.select_related('team').prefetch_related('skills').all()
        if not filters:
            return qs

        if filters.get('search'):
            term = filters['search']
            qs = qs.filter(
                models_Q(display_name__icontains=term) |
                models_Q(first_name__icontains=term)   |
                models_Q(last_name__icontains=term)
            )
        if filters.get('team_id'):
            qs = qs.filter(team_id=filters['team_id'])
        if filters.get('role'):
            qs = qs.filter(role=filters['role'])
        if filters.get('location'):
            qs = qs.filter(location=filters['location'])
        if filters.get('employee_type'):
            qs = qs.filter(employee_type=filters['employee_type'])
        if filters.get('is_active') is not None:
            qs = qs.filter(is_active=filters['is_active'])
        if filters.get('skill_id'):
            qs = qs.filter(skills__id=filters['skill_id'])

        return qs

    @staticmethod
    def get_member(member_id: int):
        return (
            TeamMember.objects
            .select_related('team')
            .prefetch_related('skills')
            .get(pk=member_id)
        )

    @staticmethod
    def get_team_history(member_id: int):
        return (
            TeamMemberHistory.objects
            .select_related('from_team', 'to_team')
            .filter(member_id=member_id)
        )

    @staticmethod
    @transaction.atomic
    def create_member(data: dict) -> TeamMember:
        _validate_dates(data.get('start_date'), data.get('end_date'))

        member = TeamMember(
            first_name       = data['first_name'].strip(),
            last_name        = data['last_name'].strip(),
            display_name     = data.get('display_name', '').strip(),
            role             = data.get('role', TeamMember.Role.ENGINEER),
            location         = data.get('location', TeamMember.Location.ONSITE),
            employee_type    = data.get('employee_type', TeamMember.EmployeeType.CONTRACTOR),
            team_id          = data.get('team_id') or None,
            start_date       = data['start_date'],
            end_date         = data.get('end_date') or None,
            default_holidays = data.get('default_holidays', _system_holidays()),
            is_active        = data.get('is_active', True),
        )
        member.full_clean()
        member.save()

        skill_ids = data.get('skill_ids') or []
        if skill_ids:
            member.skills.set(skill_ids)

        if member.team_id:
            TeamMemberHistory.objects.create(
                member    = member,
                from_team = None,
                to_team   = member.team,
                moved_on  = member.start_date,
                note      = 'Initial team assignment.',
            )

        return member

    @staticmethod
    @transaction.atomic
    def update_member(member_id: int, data: dict) -> TeamMember:
        member = TeamMember.objects.get(pk=member_id)
        old_team_id = member.team_id

        if 'first_name'       in data: member.first_name       = data['first_name'].strip()
        if 'last_name'        in data: member.last_name         = data['last_name'].strip()
        if 'role'             in data: member.role              = data['role']
        if 'location'         in data: member.location          = data['location']
        if 'employee_type'    in data: member.employee_type     = data['employee_type']
        if 'start_date'       in data: member.start_date        = data['start_date']
        if 'end_date'         in data: member.end_date          = data.get('end_date') or None
        if 'default_holidays' in data: member.default_holidays  = data['default_holidays']
        if 'is_active'        in data: member.is_active         = data['is_active']

        if 'display_name' in data:
            member.display_name = data['display_name'].strip()
        else:
            member.display_name = ''

        new_team_id = data.get('team_id', old_team_id)
        if new_team_id != old_team_id:
            member.team_id = new_team_id or None
            TeamMemberHistory.objects.create(
                member_id = member_id,
                from_team_id = old_team_id,
                to_team_id   = new_team_id or None,
                moved_on  = datetime.date.today(),
                note      = 'Updated via edit form.',
            )
        elif 'team_id' in data:
            member.team_id = new_team_id or None

        _validate_dates(member.start_date, member.end_date)
        member.full_clean()
        member.save()

        if 'skill_ids' in data:
            member.skills.set(data['skill_ids'] or [])

        return member

    @staticmethod
    @transaction.atomic
    def move_to_team(
        member_id: int,
        to_team_id,         
        moved_on: datetime.date,
        note: str = '',
    ) -> TeamMember:
        member = TeamMember.objects.get(pk=member_id)

        if moved_on < member.start_date:
            raise ValidationError(
                'Move date cannot be before the member\'s start date.'
            )
        if member.end_date and moved_on > member.end_date:
            raise ValidationError(
                'Move date cannot be after the member\'s end date.'
            )

        old_team_id = member.team_id
        if old_team_id == (to_team_id or None):
            raise ValidationError(
                'The member is already assigned to this team.'
            )

        TeamMemberHistory.objects.create(
            member_id    = member_id,
            from_team_id = old_team_id,
            to_team_id   = to_team_id or None,
            moved_on     = moved_on,
            note         = note.strip(),
        )

        member.team_id = to_team_id or None
        member.save(update_fields=['team_id', 'updated_at'])
        return member

    @staticmethod
    def delete_member(member_id: int) -> None:
        TeamMember.objects.get(pk=member_id).delete()


def _validate_dates(start_date, end_date):
    if start_date and end_date and end_date < start_date:
        raise ValidationError({'end_date': 'End date cannot be before start date.'})


def _system_holidays() -> int:
    try:
        from apps.configurations.services import ConfigurationService
        return ConfigurationService.get_int('DEFAULT_HOLIDAYS', fallback=20)
    except Exception:
        return 20


from django.db.models import Q as models_Q  # noqa: E402  (import after definitions)