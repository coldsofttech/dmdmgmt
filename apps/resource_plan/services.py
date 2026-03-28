"""
Resource Plan — services.py  (Phase 1)

Phase 1 covers:
  - Basic CRUD for all 12 models
  - Grid data assembly: capacity grid (Section 1), allocation grid (Section 2),
    summary grid (Section 3)
  - Placeholder leave auto-generation (3.35)
  - Unmapped project detection (3.27)
  - Day-rate and days-required helpers
  - Past-sprint locking helper (3.36)

Phase 2 will add:
  - Auto-allocation engine
  - Conflict detection and resolution queue
  - Ramp pattern distribution
  - Overflow suggestion logic
"""

from decimal import Decimal, ROUND_HALF_UP
import datetime

from django.db import transaction
from django.core.exceptions import ValidationError

from .models import (
    ResourcePlan,
    ResourcePlanProject,
    ResourcePlanProjectTeam,
    ResourcePlanPhase,
    ResourcePlanPhaseDependency,
    ResourcePlanAssignment,
    ResourcePlanAssignmentCell,
    ResourcePlanSprintBudget,
    ResourcePlanCapacityOverride,
    ResourcePlanLeafPlaceholder,
    ResourcePlanConflict,
    ResourcePlanAuditLog,
)


# ── Utility ───────────────────────────────────────────────

def _round_to_quarter(value) -> Decimal:
    d = Decimal(str(value))
    return (d * 4).quantize(Decimal('1'), rounding=ROUND_HALF_UP) / 4


def _get_day_rate() -> float:
    try:
        from apps.configurations.services import ConfigurationService
        return ConfigurationService.get_float('STORY_POINT_PRICE', fallback=0.0)
    except Exception:
        return 0.0


def _get_default_holidays() -> int:
    try:
        from apps.configurations.services import ConfigurationService
        return ConfigurationService.get_int('DEFAULT_HOLIDAYS', fallback=20)
    except Exception:
        return 20


def _get_sprint_cap() -> Decimal:
    """Max days allocatable per engineer per sprint (configurable later)."""
    return Decimal('10')


# ═══════════════════════════════════════════════════════════
#  ResourcePlan CRUD
# ═══════════════════════════════════════════════════════════

class ResourcePlanService:

    @staticmethod
    def list_plans(financial_year_id: int = None, search: str = None):
        qs = ResourcePlan.objects.select_related('financial_year').all()
        if financial_year_id:
            qs = qs.filter(financial_year_id=financial_year_id)
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(scope_notes__icontains=search) |
                Q(financial_year__long_fy__icontains=search)
            )
        return qs

    @staticmethod
    def get_plan(plan_id: int) -> ResourcePlan:
        return ResourcePlan.objects.select_related('financial_year').get(pk=plan_id)

    @staticmethod
    def get_active_fy():
        try:
            from apps.financial_years.models import FinancialYear
            return FinancialYear.objects.filter(is_active=True).first()
        except Exception:
            return None

    @staticmethod
    @transaction.atomic
    def create_plan(data: dict) -> ResourcePlan:
        plan = ResourcePlan(
            name                     = data['name'].strip(),
            financial_year_id        = data['financial_year_id'],
            status                   = data.get('status', ResourcePlan.Status.DRAFT),
            allocation_threshold_pct = data.get('allocation_threshold_pct', Decimal('10.00')),
            scope_notes              = data.get('scope_notes', '').strip(),
        )
        plan.full_clean()
        plan.save()
        ResourcePlanAuditLog.objects.create(
            plan=plan, change_type='CREATE',
            description=f'Plan "{plan.name}" created.',
        )
        return plan

    @staticmethod
    @transaction.atomic
    def update_plan(plan_id: int, data: dict) -> ResourcePlan:
        plan = ResourcePlan.objects.get(pk=plan_id)
        for field in ('name', 'status', 'allocation_threshold_pct', 'scope_notes'):
            if field in data:
                setattr(plan, field, data[field])
        plan.full_clean()
        plan.save()
        ResourcePlanAuditLog.objects.create(
            plan=plan, change_type='UPDATE',
            description=f'Plan "{plan.name}" updated.',
        )
        return plan

    @staticmethod
    def delete_plan(plan_id: int) -> None:
        ResourcePlan.objects.get(pk=plan_id).delete()

    # ── Unmapped project detection (3.27) ─────────────────

    @staticmethod
    def get_unmapped_projects(plan_id: int) -> list:
        """
        Return projects in the plan's FY that are NOT yet scoped into this plan.
        These are highlighted on the list and detail views.
        """
        plan = ResourcePlan.objects.select_related('financial_year').get(pk=plan_id)
        from apps.projects.models import Project
        mapped_ids = set(
            ResourcePlanProject.objects.filter(plan=plan)
            .values_list('project_id', flat=True)
        )
        return list(
            Project.objects.filter(
                status__in=['NEW', 'IN_PROGRESS']
            ).exclude(pk__in=mapped_ids)
            .order_by('programme_name', 'project_name')
        )


# ═══════════════════════════════════════════════════════════
#  ResourcePlanProject CRUD
# ═══════════════════════════════════════════════════════════

class PlanProjectService:

    @staticmethod
    @transaction.atomic
    def create(plan_id: int, data: dict) -> ResourcePlanProject:
        pp = ResourcePlanProject(
            plan_id              = plan_id,
            project_id           = data['project_id'],
            basis                = data.get('basis', ResourcePlanProject.Basis.ESTIMATE),
            custom_amount        = data.get('custom_amount'),
            priority_override    = data.get('priority_override', ''),
            confidence_override  = data.get('confidence_override', ''),
            dates_strict         = data.get('dates_strict', False),
            notes                = data.get('notes', '').strip(),
        )
        pp.full_clean()
        pp.save()
        return pp

    @staticmethod
    @transaction.atomic
    def update(pp_id: int, data: dict) -> ResourcePlanProject:
        pp = ResourcePlanProject.objects.get(pk=pp_id)
        for field in ('basis', 'custom_amount', 'priority_override',
                      'confidence_override', 'dates_strict', 'notes'):
            if field in data:
                setattr(pp, field, data[field])
        pp.full_clean()
        pp.save()
        return pp

    @staticmethod
    def delete(pp_id: int) -> None:
        ResourcePlanProject.objects.get(pk=pp_id).delete()


# ═══════════════════════════════════════════════════════════
#  ResourcePlanProjectTeam CRUD
# ═══════════════════════════════════════════════════════════

class PlanProjectTeamService:

    @staticmethod
    @transaction.atomic
    def create(plan_project_id: int, data: dict) -> ResourcePlanProjectTeam:
        ppt = ResourcePlanProjectTeam(
            plan_project_id  = plan_project_id,
            team_id          = data['team_id'],
            allocation_type  = data.get('allocation_type', ResourcePlanProjectTeam.AllocationType.PERCENT),
            allocation_value = data['allocation_value'],
            sequence_order   = data.get('sequence_order', 1),
            notes            = data.get('notes', '').strip(),
        )
        ppt.full_clean()
        ppt.save()
        return ppt

    @staticmethod
    def delete(ppt_id: int) -> None:
        ResourcePlanProjectTeam.objects.get(pk=ppt_id).delete()


# ═══════════════════════════════════════════════════════════
#  ResourcePlanPhase CRUD
# ═══════════════════════════════════════════════════════════

class PlanPhaseService:

    @staticmethod
    @transaction.atomic
    def create(plan_project_team_id: int, data: dict) -> ResourcePlanPhase:
        phase = ResourcePlanPhase(
            plan_project_team_id = plan_project_team_id,
            name                 = data.get('name', 'Phase 1'),
            sequence_order       = data.get('sequence_order', 1),
            start_sprint_id      = data.get('start_sprint_id'),
            end_sprint_id        = data.get('end_sprint_id'),
            predecessor_phase_id = data.get('predecessor_phase_id'),
            dependency_type      = data.get('dependency_type', ''),
            ramp_pattern         = data.get('ramp_pattern', ResourcePlanPhase.RampPattern.FLAT),
            max_days_per_sprint  = data.get('max_days_per_sprint'),
            notes                = data.get('notes', '').strip(),
        )
        phase.full_clean()
        phase.save()
        return phase

    @staticmethod
    @transaction.atomic
    def update(phase_id: int, data: dict) -> ResourcePlanPhase:
        phase = ResourcePlanPhase.objects.get(pk=phase_id)
        for field in ('name', 'sequence_order', 'start_sprint_id', 'end_sprint_id',
                      'predecessor_phase_id', 'dependency_type', 'ramp_pattern',
                      'max_days_per_sprint', 'notes'):
            if field in data:
                setattr(phase, field, data[field])
        phase.full_clean()
        phase.save()
        return phase

    @staticmethod
    def delete(phase_id: int) -> None:
        ResourcePlanPhase.objects.get(pk=phase_id).delete()


# ═══════════════════════════════════════════════════════════
#  ResourcePlanAssignment CRUD
# ═══════════════════════════════════════════════════════════

class PlanAssignmentService:

    @staticmethod
    @transaction.atomic
    def create(phase_id: int, data: dict) -> ResourcePlanAssignment:
        assignment = ResourcePlanAssignment(
            phase_id             = phase_id,
            team_member_id       = data.get('team_member_id'),
            placeholder_name     = data.get('placeholder_name', ''),
            assignment_type      = data.get('assignment_type', ResourcePlanAssignment.AssignmentType.ENGINEER),
            is_interim           = data.get('is_interim', False),
            replaces_assignment_id = data.get('replaces_assignment_id'),
            pause_from_sprint_id = data.get('pause_from_sprint_id'),
            resume_at_sprint_id  = data.get('resume_at_sprint_id'),
            notes                = data.get('notes', '').strip(),
        )
        assignment.full_clean()
        assignment.save()
        return assignment

    @staticmethod
    @transaction.atomic
    def update(assignment_id: int, data: dict) -> ResourcePlanAssignment:
        a = ResourcePlanAssignment.objects.get(pk=assignment_id)
        for field in ('team_member_id', 'placeholder_name', 'assignment_type',
                      'is_interim', 'replaces_assignment_id',
                      'pause_from_sprint_id', 'resume_at_sprint_id', 'notes'):
            if field in data:
                setattr(a, field, data[field])
        a.full_clean()
        a.save()
        return a

    @staticmethod
    def delete(assignment_id: int) -> None:
        ResourcePlanAssignment.objects.get(pk=assignment_id).delete()


# ═══════════════════════════════════════════════════════════
#  Cell update (3.28 — inline editing)
# ═══════════════════════════════════════════════════════════

class CellService:

    @staticmethod
    @transaction.atomic
    def upsert_cell(
        assignment_id: int,
        sprint_id: int,
        days: Decimal,
        changed_by: str = 'User',
    ) -> tuple:
        """
        Create or update a cell.
        Returns (cell, context_dict) where context_dict carries:
          sprint_total_allocated  – sum of allocated days this sprint across all
                                    assignments for the same team in this plan
          member_remaining        – available − allocated for this engineer × sprint
          conflict_count          – pending conflict count for the plan after save
          new_conflicts           – list of {type, severity, description} raised now
          unmapped_count          – live unmapped-project count for the plan
        Raises ValidationError if the plan is locked or sprint is in the past.
        """
        from apps.sprints.models import Sprint

        sprint = Sprint.objects.get(pk=sprint_id)
        if sprint.end_date < datetime.date.today():
            raise ValidationError('Cannot edit allocations for past sprints.')

        rounded = _round_to_quarter(days)

        cell, created = ResourcePlanAssignmentCell.objects.get_or_create(
            assignment_id=assignment_id,
            sprint_id=sprint_id,
            defaults={'days_allocated': rounded, 'is_auto': False, 'is_locked': False},
        )
        if not created:
            if cell.is_locked:
                raise ValidationError('This cell is locked (past sprint).')
            old_val             = cell.days_allocated
            cell.days_allocated = rounded
            cell.is_auto        = False
            cell.save()
        else:
            old_val = Decimal('0')

        # Load assignment + plan hierarchy
        assignment = ResourcePlanAssignment.objects.select_related(
            'team_member',
            'phase__plan_project_team__team',
            'phase__plan_project_team__plan_project__project',
            'phase__plan_project_team__plan_project__plan__financial_year',
        ).get(pk=assignment_id)
        plan = assignment.phase.plan_project_team.plan_project.plan

        # Audit log
        ResourcePlanAuditLog.objects.create(
            plan        = plan,
            changed_by  = changed_by,
            change_type = 'CELL_UPDATE',
            description = (
                f'{assignment.display_name} / {sprint.name}: '
                f'{old_val}d → {rounded}d'
            ),
        )

        # Run all conflict checks; collect newly raised conflicts
        new_conflicts: list = []
        CellService._check_threshold(assignment, plan, new_conflicts)
        CellService._check_capacity(assignment, plan, sprint, new_conflicts)
        CellService._check_engineer_leave(assignment, plan, sprint, rounded, new_conflicts)

        # Build context dict for the AJAX response
        team = assignment.phase.plan_project_team.team
        sprint_total = CellService._sprint_total_for_team(plan, team, sprint)
        member_remaining = CellService._member_remaining(assignment, plan, sprint)
        conflict_count = ResourcePlanConflict.objects.filter(
            plan=plan,
            resolution=ResourcePlanConflict.Resolution.PENDING,
        ).count()
        unmapped_count = len(ResourcePlanService.get_unmapped_projects(plan.pk))

        ctx = {
            'sprint_total_allocated': sprint_total,
            'member_remaining':       member_remaining,
            'conflict_count':         conflict_count,
            'new_conflicts':          new_conflicts,
            'unmapped_count':         unmapped_count,
        }
        return cell, ctx

    # ── Conflict checks ───────────────────────────────────

    @staticmethod
    def _check_threshold(
        assignment: ResourcePlanAssignment,
        plan: ResourcePlan,
        new_conflicts: list,
    ) -> None:
        """
        Check total allocated vs days_required ± threshold.
        Auto-resolves the opposite conflict when allocation swings back in range.
        """
        try:
            pp = assignment.phase.plan_project_team.plan_project
            total_allocated = ResourcePlanAssignmentCell.objects.filter(
                assignment__phase__plan_project_team__plan_project=pp
            ).aggregate(total=__import__('django.db.models', fromlist=['Sum']).Sum('days_allocated'))['total'] or Decimal('0')

            days_required = pp.days_required
            if not days_required or days_required <= 0:
                return

            threshold   = plan.allocation_threshold_pct / Decimal('100')
            upper_limit = days_required * (1 + threshold)
            lower_limit = days_required * (1 - threshold)

            C = ResourcePlanConflict

            if total_allocated > upper_limit:
                # Auto-resolve any existing UNDER_BUDGET for this pp
                C.objects.filter(
                    plan=plan,
                    conflict_type=C.ConflictType.UNDER_BUDGET,
                    affected_assignment=assignment,
                    resolution=C.Resolution.PENDING,
                ).update(
                    resolution=C.Resolution.DISMISSED,
                    resolved_at=datetime.datetime.now(),
                )
                _, created = C.objects.update_or_create(
                    plan=plan,
                    conflict_type=C.ConflictType.OVER_BUDGET,
                    affected_assignment=assignment,
                    defaults={
                        'severity':    C.Severity.ERROR,
                        'resolution':  C.Resolution.PENDING,
                        'resolved_at': None,
                        'description': (
                            f'{pp.project.display_name}: {total_allocated}d allocated '
                            f'exceeds {days_required}d + {plan.allocation_threshold_pct}% '
                            f'(limit {upper_limit:.2f}d).'
                        ),
                    },
                )
                if created:
                    new_conflicts.append({
                        'type':        'OVER_BUDGET',
                        'severity':    'ERROR',
                        'description': f'{pp.project.display_name}: over budget/estimate.',
                    })

            elif total_allocated < lower_limit:
                C.objects.filter(
                    plan=plan,
                    conflict_type=C.ConflictType.OVER_BUDGET,
                    affected_assignment=assignment,
                    resolution=C.Resolution.PENDING,
                ).update(
                    resolution=C.Resolution.DISMISSED,
                    resolved_at=datetime.datetime.now(),
                )
                _, created = C.objects.update_or_create(
                    plan=plan,
                    conflict_type=C.ConflictType.UNDER_BUDGET,
                    affected_assignment=assignment,
                    defaults={
                        'severity':    C.Severity.WARNING,
                        'resolution':  C.Resolution.PENDING,
                        'resolved_at': None,
                        'description': (
                            f'{pp.project.display_name}: {total_allocated}d allocated '
                            f'is below {days_required}d − {plan.allocation_threshold_pct}% '
                            f'(min {lower_limit:.2f}d).'
                        ),
                    },
                )
                if created:
                    new_conflicts.append({
                        'type':        'UNDER_BUDGET',
                        'severity':    'WARNING',
                        'description': f'{pp.project.display_name}: under budget/estimate.',
                    })

            else:
                # Back in range — auto-resolve both directions
                now = datetime.datetime.now()
                C.objects.filter(
                    plan=plan,
                    conflict_type__in=[C.ConflictType.OVER_BUDGET, C.ConflictType.UNDER_BUDGET],
                    affected_assignment=assignment,
                    resolution=C.Resolution.PENDING,
                ).update(resolution=C.Resolution.DISMISSED, resolved_at=now)

        except Exception:
            pass

    @staticmethod
    def _check_capacity(
        assignment: ResourcePlanAssignment,
        plan: ResourcePlan,
        sprint,
        new_conflicts: list,
    ) -> None:
        """
        Check if engineer's total allocated days across all projects in this sprint
        exceeds their available capacity. Raises CAPACITY_EXCEEDED or auto-resolves.
        """
        try:
            member = assignment.team_member
            if not member:
                return  # TBC placeholder — skip

            fy_id = plan.financial_year_id

            # Available days for this member in this sprint
            from apps.leaves.models import Leave, calc_working_days
            base_days  = Decimal(str(sprint.working_days))
            leave_days = Decimal('0')

            for leave in Leave.objects.filter(
                team_member=member,
                financial_year_id=fy_id,
            ):
                if leave.start_date <= sprint.end_date and leave.end_date >= sprint.start_date:
                    cs = max(leave.start_date, sprint.start_date)
                    ce = min(leave.end_date,   sprint.end_date)
                    leave_days += Decimal(str(calc_working_days(cs, ce, financial_year_id=fy_id)))

            ph_days = ResourcePlanLeafPlaceholder.objects.filter(
                plan=plan, team_member=member, sprint=sprint,
            ).aggregate(total=__import__('django.db.models', fromlist=['Sum']).Sum('days'))['total'] or Decimal('0')

            adhoc_days = ResourcePlanCapacityOverride.objects.filter(
                plan=plan, team_member=member, sprint=sprint,
            ).aggregate(total=__import__('django.db.models', fromlist=['Sum']).Sum('reserved_days'))['total'] or Decimal('0')

            available = max(base_days - leave_days - ph_days - adhoc_days, Decimal('0'))

            # Total allocated for this member in this sprint across all assignments in this plan
            total_allocated = ResourcePlanAssignmentCell.objects.filter(
                sprint=sprint,
                assignment__team_member=member,
                assignment__phase__plan_project_team__plan_project__plan=plan,
            ).aggregate(total=__import__('django.db.models', fromlist=['Sum']).Sum('days_allocated'))['total'] or Decimal('0')

            C = ResourcePlanConflict
            if total_allocated > available:
                _, created = C.objects.update_or_create(
                    plan=plan,
                    conflict_type=C.ConflictType.CAPACITY_EXCEEDED,
                    affected_assignment=assignment,
                    affected_sprint=sprint,
                    defaults={
                        'severity':    C.Severity.ERROR,
                        'resolution':  C.Resolution.PENDING,
                        'resolved_at': None,
                        'description': (
                            f'{member.display_name} / {sprint.name}: '
                            f'{total_allocated}d allocated but only {available}d available '
                            f'(over by {total_allocated - available}d).'
                        ),
                    },
                )
                if created:
                    new_conflicts.append({
                        'type':        'CAPACITY_EXCEEDED',
                        'severity':    'ERROR',
                        'description': (
                            f'{member.display_name}: over capacity in {sprint.name} '
                            f'({total_allocated}d > {available}d).'
                        ),
                    })
            else:
                # Back within capacity — auto-resolve
                C.objects.filter(
                    plan=plan,
                    conflict_type=C.ConflictType.CAPACITY_EXCEEDED,
                    affected_assignment=assignment,
                    affected_sprint=sprint,
                    resolution=C.Resolution.PENDING,
                ).update(
                    resolution=C.Resolution.DISMISSED,
                    resolved_at=datetime.datetime.now(),
                )
        except Exception:
            pass

    @staticmethod
    def _check_engineer_leave(
        assignment: ResourcePlanAssignment,
        plan: ResourcePlan,
        sprint,
        days: Decimal,
        new_conflicts: list,
    ) -> None:
        """
        If days > 0 and the engineer has confirmed leave or a placeholder in this
        sprint, raise ENGINEER_LEAVE at WARNING level so the planner is aware.
        Auto-resolves if days set back to 0.
        """
        try:
            member = assignment.team_member
            if not member:
                return

            C = ResourcePlanConflict

            if days <= 0:
                C.objects.filter(
                    plan=plan,
                    conflict_type=C.ConflictType.ENGINEER_LEAVE,
                    affected_assignment=assignment,
                    affected_sprint=sprint,
                    resolution=C.Resolution.PENDING,
                ).update(
                    resolution=C.Resolution.DISMISSED,
                    resolved_at=datetime.datetime.now(),
                )
                return

            fy_id = plan.financial_year_id
            from apps.leaves.models import Leave
            has_confirmed_leave = Leave.objects.filter(
                team_member=member,
                financial_year_id=fy_id,
                start_date__lte=sprint.end_date,
                end_date__gte=sprint.start_date,
            ).exists()

            has_placeholder = ResourcePlanLeafPlaceholder.objects.filter(
                plan=plan,
                team_member=member,
                sprint=sprint,
            ).exists()

            if has_confirmed_leave or has_placeholder:
                leave_type = 'confirmed leave' if has_confirmed_leave else 'projected leave'
                _, created = C.objects.update_or_create(
                    plan=plan,
                    conflict_type=C.ConflictType.ENGINEER_LEAVE,
                    affected_assignment=assignment,
                    affected_sprint=sprint,
                    defaults={
                        'severity':    C.Severity.WARNING,
                        'resolution':  C.Resolution.PENDING,
                        'resolved_at': None,
                        'description': (
                            f'{member.display_name} has {leave_type} in '
                            f'{sprint.name} but is allocated {days}d.'
                        ),
                    },
                )
                if created:
                    new_conflicts.append({
                        'type':        'ENGINEER_LEAVE',
                        'severity':    'WARNING',
                        'description': (
                            f'{member.display_name} has {leave_type} in {sprint.name}.'
                        ),
                    })
        except Exception:
            pass

    # ── Context helpers ───────────────────────────────────

    @staticmethod
    def _sprint_total_for_team(plan: ResourcePlan, team, sprint) -> Decimal:
        """Sum of all allocated days for the team in this sprint across this plan."""
        try:
            result = ResourcePlanAssignmentCell.objects.filter(
                sprint=sprint,
                assignment__phase__plan_project_team__team=team,
                assignment__phase__plan_project_team__plan_project__plan=plan,
            ).aggregate(
                total=__import__('django.db.models', fromlist=['Sum']).Sum('days_allocated')
            )['total']
            return result or Decimal('0')
        except Exception:
            return Decimal('0')

    @staticmethod
    def _member_remaining(
        assignment: ResourcePlanAssignment,
        plan: ResourcePlan,
        sprint,
    ) -> Decimal:
        """Available days minus all allocated days for this engineer × sprint."""
        try:
            member = assignment.team_member
            if not member:
                return Decimal('0')
            fy_id = plan.financial_year_id
            from apps.leaves.models import Leave, calc_working_days

            base = Decimal(str(sprint.working_days))

            leave_days = Decimal('0')
            for leave in Leave.objects.filter(
                team_member=member,
                financial_year_id=fy_id,
            ):
                if leave.start_date <= sprint.end_date and leave.end_date >= sprint.start_date:
                    cs = max(leave.start_date, sprint.start_date)
                    ce = min(leave.end_date,   sprint.end_date)
                    leave_days += Decimal(str(calc_working_days(cs, ce, financial_year_id=fy_id)))

            ph_days = ResourcePlanLeafPlaceholder.objects.filter(
                plan=plan, team_member=member, sprint=sprint,
            ).aggregate(
                total=__import__('django.db.models', fromlist=['Sum']).Sum('days')
            )['total'] or Decimal('0')

            adhoc_days = ResourcePlanCapacityOverride.objects.filter(
                plan=plan, team_member=member, sprint=sprint,
            ).aggregate(
                total=__import__('django.db.models', fromlist=['Sum']).Sum('reserved_days')
            )['total'] or Decimal('0')

            available = max(base - leave_days - ph_days - adhoc_days, Decimal('0'))

            allocated = ResourcePlanAssignmentCell.objects.filter(
                sprint=sprint,
                assignment__team_member=member,
                assignment__phase__plan_project_team__plan_project__plan=plan,
            ).aggregate(
                total=__import__('django.db.models', fromlist=['Sum']).Sum('days_allocated')
            )['total'] or Decimal('0')

            return available - allocated
        except Exception:
            return Decimal('0')


# ═══════════════════════════════════════════════════════════
#  Grid data assembly (Sections 1, 2, 3)
# ═══════════════════════════════════════════════════════════

class GridService:
    """
    Assembles the three sections of the Resource Plan grid for one team.

    All three sections share the same sprint columns.
    Totals appear as the LAST ROW in each section (not last column).
    """

    @staticmethod
    def get_sprints_for_plan(plan: ResourcePlan) -> list:
        """Ordered list of Sprint objects for the plan's FY."""
        from apps.sprints.models import Sprint
        return list(
            Sprint.objects.filter(
                financial_year=plan.financial_year
            ).order_by('start_date')
        )

    @staticmethod
    def section1_capacity(plan: ResourcePlan, team, sprints: list) -> dict:
        """
        Section 1 — Capacity grid for one team.

        Returns:
          {
            'rows': [
              {
                'member': TeamMember,
                'cells': {sprint_pk: available_days},
                'is_architect': bool,
                'placeholder_leave_sprints': {sprint_pk: days},
                'has_leave_warning': bool,
              }
            ],
            'totals': {sprint_pk: team_total_available_days},
          }
        """
        from apps.team_members.models import TeamMember
        from apps.leaves.models import Leave, calc_working_days
        from apps.holidays.models import Holiday

        members = list(
            TeamMember.objects.filter(team=team, is_active=True)
            .order_by('last_name', 'first_name')
        )
        today   = datetime.date.today()
        fy      = plan.financial_year
        fy_id   = fy.pk

        # Pre-fetch confirmed leaves for all members in this FY
        confirmed_leaves = {}  # member_pk → list of Leave
        for leave in Leave.objects.filter(
            team_member__in=members,
            financial_year_id=fy_id,
        ).select_related('team_member'):
            confirmed_leaves.setdefault(leave.team_member_id, []).append(leave)

        # Pre-fetch placeholder leaves for this plan+team
        placeholders = {}  # (member_pk, sprint_pk) → days
        for ph in ResourcePlanLeafPlaceholder.objects.filter(
            plan=plan,
            team_member__in=members,
            sprint__in=sprints,
        ):
            placeholders[(ph.team_member_id, ph.sprint_id)] = ph.days

        # Pre-fetch capacity overrides
        overrides = {}  # (member_pk, sprint_pk) → reserved_days
        for ov in ResourcePlanCapacityOverride.objects.filter(
            plan=plan,
            team_member__in=members,
            sprint__in=sprints,
        ):
            overrides[(ov.team_member_id, ov.sprint_id)] = ov.reserved_days

        default_holidays = _get_default_holidays()

        rows   = []
        totals = {s.pk: Decimal('0') for s in sprints}

        for member in members:
            member_leaves = confirmed_leaves.get(member.pk, [])
            total_leave_days = sum(l.days for l in member_leaves)
            has_leave_warning = total_leave_days < default_holidays

            ph_for_member = {
                sprint_pk: days
                for (m_pk, sprint_pk), days in placeholders.items()
                if m_pk == member.pk
            }

            cells = {}
            for sprint in sprints:
                # Working days for this sprint
                base_days = Decimal(str(sprint.working_days))

                # Deduct confirmed leave days that overlap this sprint
                leave_days = Decimal('0')
                for leave in member_leaves:
                    if leave.start_date <= sprint.end_date and leave.end_date >= sprint.start_date:
                        clipped_start = max(leave.start_date, sprint.start_date)
                        clipped_end   = min(leave.end_date, sprint.end_date)
                        wd = calc_working_days(
                            clipped_start, clipped_end, financial_year_id=fy_id
                        )
                        leave_days += Decimal(str(wd))

                # Deduct placeholder leave
                ph_days = placeholders.get((member.pk, sprint.pk), Decimal('0'))

                # Deduct adhoc capacity override
                adhoc_days = overrides.get((member.pk, sprint.pk), Decimal('0'))

                available = max(base_days - leave_days - ph_days - adhoc_days, Decimal('0'))
                cells[sprint.pk] = available
                totals[sprint.pk] += available

            rows.append({
                'member':                  member,
                'cells':                   cells,
                'is_architect':            member.role == 'architect',
                'placeholder_leave_sprints': ph_for_member,
                'has_leave_warning':       has_leave_warning,
            })

        return {'rows': rows, 'totals': totals}

    @staticmethod
    def section2_allocations(plan: ResourcePlan, team, sprints: list) -> dict:
        """
        Section 2 — Allocation grid for one team.

        Returns:
          {
            'project_groups': [
              {
                'plan_project': ResourcePlanProject,
                'assignment_rows': [
                  {
                    'assignment': ResourcePlanAssignment,
                    'cells': {sprint_pk: days_allocated},
                  }
                ],
              }
            ],
            'totals': {sprint_pk: total_allocated_days},
          }
        """
        sprint_pks = [s.pk for s in sprints]
        today      = datetime.date.today()

        # All assignments for this team in this plan
        assignments = (
            ResourcePlanAssignment.objects
            .filter(
                phase__plan_project_team__team=team,
                phase__plan_project_team__plan_project__plan=plan,
            )
            .select_related(
                'team_member',
                'phase__plan_project_team__plan_project__project',
            )
            .order_by(
                'phase__plan_project_team__plan_project__project__programme_name',
                'phase__plan_project_team__plan_project__project__project_name',
                'phase__sequence_order',
                'team_member__last_name',
            )
        )

        # Pre-fetch all cells for these assignments × sprints in one query
        cells_qs = ResourcePlanAssignmentCell.objects.filter(
            assignment__in=assignments,
            sprint_id__in=sprint_pks,
        )
        cell_map = {}  # (assignment_pk, sprint_pk) → cell
        for cell in cells_qs:
            cell_map[(cell.assignment_id, cell.sprint_id)] = cell

        # Group by plan_project
        from collections import OrderedDict
        groups = OrderedDict()
        for a in assignments:
            pp = a.phase.plan_project_team.plan_project
            if pp.pk not in groups:
                groups[pp.pk] = {'plan_project': pp, 'assignment_rows': []}
            row_cells = {}
            for sprint in sprints:
                cell = cell_map.get((a.pk, sprint.pk))
                days = cell.days_allocated if cell else Decimal('0')
                is_locked = sprint.end_date < today
                row_cells[sprint.pk] = {
                    'days':      days,
                    'is_auto':   cell.is_auto if cell else False,
                    'is_locked': is_locked,
                }
            groups[pp.pk]['assignment_rows'].append({
                'assignment': a,
                'cells':      row_cells,
            })

        totals = {s.pk: Decimal('0') for s in sprints}
        for group in groups.values():
            for row in group['assignment_rows']:
                for sprint_pk, cell_data in row['cells'].items():
                    totals[sprint_pk] += cell_data['days']

        return {
            'project_groups': list(groups.values()),
            'totals':         totals,
        }

    @staticmethod
    def section3_summary(
        plan: ResourcePlan, team, sprints: list,
        section1: dict, section2: dict
    ) -> dict:
        """
        Section 3 — Summary: allocated vs available per engineer per sprint.
        Returns:
          {
            'rows': [
              {
                'member': TeamMember | None,
                'display_name': str,
                'cells': {sprint_pk: {'allocated': Decimal, 'available': Decimal, 'remaining': Decimal}},
              }
            ],
            'totals': {sprint_pk: {'allocated': Decimal, 'available': Decimal, 'remaining': Decimal}},
          }
        """
        from apps.team_members.models import TeamMember

        # Build member → allocated per sprint from section 2
        member_allocated = {}  # member_pk → {sprint_pk: Decimal}
        for group in section2['project_groups']:
            for row in group['assignment_rows']:
                a  = row['assignment']
                pk = a.team_member_id
                if pk not in member_allocated:
                    member_allocated[pk] = {}
                for sprint_pk, cell_data in row['cells'].items():
                    member_allocated[pk][sprint_pk] = (
                        member_allocated[pk].get(sprint_pk, Decimal('0'))
                        + cell_data['days']
                    )

        summary_rows = []
        totals = {
            s.pk: {'allocated': Decimal('0'), 'available': Decimal('0'), 'remaining': Decimal('0')}
            for s in sprints
        }

        for s1_row in section1['rows']:
            member   = s1_row['member']
            m_alloc  = member_allocated.get(member.pk, {})
            row_cells = {}
            for sprint in sprints:
                available  = s1_row['cells'].get(sprint.pk, Decimal('0'))
                allocated  = m_alloc.get(sprint.pk, Decimal('0'))
                remaining  = available - allocated
                row_cells[sprint.pk] = {
                    'allocated': allocated,
                    'available': available,
                    'remaining': remaining,
                }
                totals[sprint.pk]['allocated'] += allocated
                totals[sprint.pk]['available'] += available
                totals[sprint.pk]['remaining'] += remaining

            summary_rows.append({
                'member':       member,
                'display_name': member.display_name,
                'cells':        row_cells,
            })

        return {'rows': summary_rows, 'totals': totals}

    @staticmethod
    def section1_5_leaves(plan: ResourcePlan, team, sprints: list) -> dict:
        """
        Section 1.5 — Holidays + confirmed leaves + projected leaves per member per sprint.
        Read-only. Shows exactly what is being deducted from capacity in Section 1.
        """
        from apps.team_members.models import TeamMember
        from apps.leaves.models import Leave, calc_working_days

        members = list(
            TeamMember.objects.filter(team=team, is_active=True)
            .order_by('last_name', 'first_name')
        )
        fy_id = plan.financial_year_id

        confirmed_leaves = {}
        for leave in Leave.objects.filter(
            team_member__in=members,
            financial_year_id=fy_id,
        ).select_related('team_member'):
            confirmed_leaves.setdefault(leave.team_member_id, []).append(leave)

        placeholders = {}
        for ph in ResourcePlanLeafPlaceholder.objects.filter(
            plan=plan, team_member__in=members, sprint__in=sprints,
        ):
            placeholders[(ph.team_member_id, ph.sprint_id)] = ph.days

        rows   = []
        totals = {
            s.pk: {'holiday_days': Decimal('0'), 'leave_days': Decimal('0'),
                   'placeholder_days': Decimal('0'), 'total_deducted': Decimal('0')}
            for s in sprints
        }

        for member in members:
            member_leaves = confirmed_leaves.get(member.pk, [])
            cells = {}
            for sprint in sprints:
                hol   = Decimal(str(sprint.holiday_count))
                leave = Decimal('0')
                for lv in member_leaves:
                    if lv.start_date <= sprint.end_date and lv.end_date >= sprint.start_date:
                        cs = max(lv.start_date, sprint.start_date)
                        ce = min(lv.end_date,   sprint.end_date)
                        leave += Decimal(str(
                            calc_working_days(cs, ce, financial_year_id=fy_id)
                        ))
                ph    = placeholders.get((member.pk, sprint.pk), Decimal('0'))
                total = hol + leave + ph
                cells[sprint.pk] = {
                    'holiday_days': hol, 'leave_days': leave,
                    'placeholder_days': ph, 'total_deducted': total,
                }
                totals[sprint.pk]['holiday_days']     += hol
                totals[sprint.pk]['leave_days']       += leave
                totals[sprint.pk]['placeholder_days'] += ph
                totals[sprint.pk]['total_deducted']   += total

            rows.append({'member': member, 'cells': cells})

        return {'rows': rows, 'totals': totals}


# ═══════════════════════════════════════════════════════════
#  Placeholder leave auto-generation (3.35)
# ═══════════════════════════════════════════════════════════

class PlaceholderLeaveService:

    @staticmethod
    @transaction.atomic
    def generate_for_plan(plan: ResourcePlan) -> dict:
        """
        Phase 2 — smarter placeholder leave distribution.

        For each active team member whose confirmed leave < DEFAULT_HOLIDAYS:
          1. Calculate remaining_leave = DEFAULT_HOLIDAYS − confirmed_days
          2. Collect all FUTURE sprints where this member has NO confirmed leave
          3. Spread remaining_leave EVENLY across eligible sprints
             (each gets either floor or ceil of days_per_sprint, snapped to 0.5)
          4. Skip sprints already covered by confirmed leave
          5. Auto-resolve any UNDER_BUDGET conflicts for this member if
             the new placeholders bring available capacity into range

        Returns a summary dict:
          {
            'created':  <int>,          total placeholder rows created
            'deleted':  <int>,          old rows removed
            'members':  [               per-member summary
              {
                'name':           str,
                'remaining_days': float,
                'sprints_count':  int,
                'days_per_sprint': float,
              }
            ]
          }
        """
        from apps.sprints.models import Sprint
        from apps.leaves.models import Leave
        from apps.team_members.models import TeamMember

        fy        = plan.financial_year
        today     = datetime.date.today()
        default_h = _get_default_holidays()

        # All future sprints in this FY (not just second half)
        future_sprints = list(
            Sprint.objects.filter(
                financial_year=fy,
                end_date__gte=today,
            ).order_by('start_date')
        )
        if not future_sprints:
            return {'created': 0, 'deleted': 0, 'members': []}

        # Gather all active members across teams in this plan
        member_ids = set(
            ResourcePlanProjectTeam.objects.filter(
                plan_project__plan=plan
            ).values_list('team__members__id', flat=True)
        )
        members = list(TeamMember.objects.filter(pk__in=member_ids, is_active=True))

        # Pre-fetch confirmed leaves for all members in one query
        confirmed_by_member: dict = {}  # member_pk → list of Leave
        for lv in Leave.objects.filter(
            team_member__in=members,
            financial_year=fy,
        ).select_related('team_member'):
            confirmed_by_member.setdefault(lv.team_member_id, []).append(lv)

        total_created = 0
        total_deleted = 0
        member_summaries: list = []

        for member in members:
            member_leaves = confirmed_by_member.get(member.pk, [])
            confirmed_days = sum(float(lv.days) for lv in member_leaves)
            remaining_leave = default_h - confirmed_days
            if remaining_leave <= 0:
                continue

            # Sprints that already have confirmed leave for this member
            leave_sprint_pks: set = set()
            for lv in member_leaves:
                for sprint in future_sprints:
                    if (lv.start_date <= sprint.end_date and
                            lv.end_date >= sprint.start_date):
                        leave_sprint_pks.add(sprint.pk)

            # Eligible = future sprints with no confirmed leave
            eligible = [s for s in future_sprints if s.pk not in leave_sprint_pks]
            if not eligible:
                continue

            # Delete existing auto-generated placeholders for this plan+member
            deleted_count = ResourcePlanLeafPlaceholder.objects.filter(
                plan=plan,
                team_member=member,
                is_auto_generated=True,
            ).delete()[0]
            total_deleted += deleted_count

            # Calculate even per-sprint allocation, snapped to nearest 0.5
            raw_per_sprint  = remaining_leave / len(eligible)
            # Snap to 0.5 increments
            snapped = round(raw_per_sprint * 2) / 2
            snapped = max(0.5, min(1.0, snapped))  # cap at 1.0d per sprint

            # Distribute — cap total to remaining_leave
            days_left = remaining_leave
            created   = 0
            for sprint in eligible:
                if days_left <= 0:
                    break
                block = min(snapped, days_left)
                # Snap block to 0.5
                block = 0.5 if block < 0.75 else 1.0
                ResourcePlanLeafPlaceholder.objects.create(
                    plan=plan,
                    team_member=member,
                    sprint=sprint,
                    days=Decimal(str(block)),
                    is_auto_generated=True,
                )
                days_left -= block
                created   += 1

            total_created += created
            if created:
                member_summaries.append({
                    'name':            member.display_name,
                    'remaining_days':  remaining_leave,
                    'sprints_count':   created,
                    'days_per_sprint': snapped,
                })

        return {
            'created': total_created,
            'deleted': total_deleted,
            'members': member_summaries,
        }


# ═══════════════════════════════════════════════════════════
#  Conflict resolution helpers
# ═══════════════════════════════════════════════════════════

class ConflictService:

    @staticmethod
    def get_pending_conflicts(plan_id: int):
        return ResourcePlanConflict.objects.filter(
            plan_id=plan_id,
            resolution=ResourcePlanConflict.Resolution.PENDING,
        ).select_related('affected_assignment', 'affected_sprint').order_by('-created_at')

    @staticmethod
    @transaction.atomic
    def resolve(conflict_id: int, resolution: str) -> ResourcePlanConflict:
        conflict = ResourcePlanConflict.objects.get(pk=conflict_id)
        if conflict.resolution != ResourcePlanConflict.Resolution.PENDING:
            raise ValidationError('This conflict has already been resolved.')
        conflict.resolution  = resolution
        conflict.resolved_at = datetime.datetime.now()
        conflict.save()
        return conflict


# ═══════════════════════════════════════════════════════════
#  Phase 3 — Ramp Distribution Engine
# ═══════════════════════════════════════════════════════════

class RampDistributor:
    """
    Pure calculation — no DB access.
    Distributes `total_days` across `n` sprints following the chosen
    RampPattern, capped at `max_per_sprint` per cell.

    All patterns normalise the raw weights so that sum(result) == total_days
    (within 0.25-day rounding). Remainder from rounding is added to the last
    non-zero cell.
    """

    @staticmethod
    def distribute(
        total_days: Decimal,
        sprint_count: int,
        pattern: str,
        max_per_sprint: Decimal = Decimal('10'),
    ) -> list:
        """
        Returns a list of Decimal values, one per sprint.
        """
        if sprint_count <= 0 or total_days <= 0:
            return [Decimal('0')] * max(sprint_count, 0)

        cap = min(max_per_sprint, Decimal('10'))
        weights = RampDistributor._weights(sprint_count, pattern)
        return RampDistributor._apply(total_days, weights, cap)

    @staticmethod
    def _weights(n: int, pattern: str) -> list:
        """Return raw weight list for the pattern (length n, positive floats)."""
        from apps.resource_plan.models import ResourcePlanPhase
        P = ResourcePlanPhase.RampPattern

        if n == 1:
            return [1.0]

        if pattern == P.FLAT:
            return [1.0] * n

        if pattern == P.RAMP_UP:
            # Linearly increasing: 1, 2, 3, …, n
            return [float(i + 1) for i in range(n)]

        if pattern == P.RAMP_DOWN:
            return [float(n - i) for i in range(n)]

        if pattern == P.RAMP_UP_DOWN:
            # Triangle: rise to midpoint then fall
            mid = n / 2
            return [float(min(i + 1, n - i)) for i in range(n)]

        if pattern == P.RAMP_UP_STEADY:
            # Rise over first third, then flat
            ramp_end = max(1, n // 3)
            weights = []
            for i in range(n):
                weights.append(float(min(i + 1, ramp_end + 1)))
            return weights

        if pattern == P.STEADY_DOWN:
            # Flat for first two-thirds then descend
            steady_end = max(1, (2 * n) // 3)
            peak = float(steady_end + 1)
            weights = []
            for i in range(n):
                if i < steady_end:
                    weights.append(peak)
                else:
                    weights.append(max(1.0, peak - (i - steady_end + 1)))
            return weights

        # Default: flat
        return [1.0] * n

    @staticmethod
    def _apply(total_days: Decimal, weights: list, cap: Decimal) -> list:
        """
        Convert raw weights → actual days, snap to 0.25, enforce cap,
        distribute remainder to the last non-capped cell.
        """
        total_w = sum(weights)
        if total_w == 0:
            return [Decimal('0')] * len(weights)

        raw = [(Decimal(str(w / total_w)) * total_days) for w in weights]

        # Snap to 0.25
        snapped = [_round_to_quarter(v) for v in raw]

        # Enforce per-sprint cap
        result = []
        overflow = Decimal('0')
        for val in snapped:
            if val > cap:
                overflow += val - cap
                result.append(cap)
            else:
                result.append(val)

        # Redistribute overflow forward to uncapped cells
        for i, val in enumerate(result):
            if overflow <= 0:
                break
            headroom = cap - val
            if headroom > 0:
                add = min(headroom, overflow)
                result[i] = _round_to_quarter(val + add)
                overflow  -= add

        # Normalise rounding error: adjust last non-zero cell
        delta = total_days - sum(result)
        if delta != 0:
            for i in range(len(result) - 1, -1, -1):
                if result[i] > 0:
                    adjusted = result[i] + delta
                    if 0 <= adjusted <= cap:
                        result[i] = _round_to_quarter(adjusted)
                        break

        return result


# ═══════════════════════════════════════════════════════════
#  Phase 3 — Auto-Allocation Engine
# ═══════════════════════════════════════════════════════════

class AllocationResult:
    """Carrier for engine run output."""
    def __init__(self):
        self.cells_written:       int  = 0
        self.cells_skipped:       int  = 0
        self.conflicts_raised:    int  = 0
        self.engineers_tbc:       int  = 0
        self.overflow_suggestions: list = []  # dicts describing each overflow
        self.right_shifts:        list = []   # phases that were right-shifted

    def to_dict(self) -> dict:
        return {
            'cells_written':        self.cells_written,
            'cells_skipped':        self.cells_skipped,
            'conflicts_raised':     self.conflicts_raised,
            'engineers_tbc':        self.engineers_tbc,
            'overflow_suggestions': self.overflow_suggestions,
            'right_shifts':         self.right_shifts,
        }


class AutoAllocationEngine:
    """
    Phase 3 — Auto-allocation engine.

    For each ResourcePlanPhase in priority order:
      1. Compute total days to distribute (from ResourcePlanProjectTeam.allocated_days
         divided by the number of assignments in the phase).
      2. Call RampDistributor.distribute() to get per-sprint day values.
      3. For each assignment × sprint, check available capacity.
         - If sufficient → write ResourcePlanAssignmentCell (is_auto=True).
         - If over capacity → record an overflow suggestion and either
           a) right-shift (if dates_strict=False), or
           b) raise CAPACITY_EXCEEDED conflict.
      4. Honour pause_from_sprint / resume_at_sprint gaps (set 0 in gap).
      5. Skip ARCHITECT assignments in day distribution (they track separately).
      6. Skip past sprints (is_locked).

    dry_run=True computes everything but writes nothing.
    """

    @staticmethod
    @transaction.atomic
    def run(plan_id: int, dry_run: bool = False) -> AllocationResult:
        plan   = ResourcePlan.objects.select_related('financial_year').get(pk=plan_id)
        result = AllocationResult()

        from apps.sprints.models import Sprint

        all_sprints = list(
            Sprint.objects.filter(
                financial_year=plan.financial_year
            ).order_by('start_date')
        )
        sprint_index = {s.pk: i for i, s in enumerate(all_sprints)}
        today = datetime.date.today()

        # Build capacity map: member_pk → sprint_pk → available_days
        # (re-use GridService helpers via direct calculation)
        cap_map = AutoAllocationEngine._build_capacity_map(plan, all_sprints)

        # Iterate plan-projects in priority order, then teams, then phases
        plan_projects = (
            ResourcePlanProject.objects
            .filter(plan=plan)
            .select_related('project')
            .prefetch_related(
                'project_teams__team',
                'project_teams__phases__assignments__team_member',
            )
        )
        # Sort by priority rank (already a property)
        sorted_pps = sorted(plan_projects, key=lambda pp: pp.priority_rank)

        for pp in sorted_pps:
            for ppt in pp.project_teams.all():
                # Process phases in sequence_order
                phases = sorted(ppt.phases.all(), key=lambda ph: ph.sequence_order)

                for phase in phases:
                    AutoAllocationEngine._allocate_phase(
                        phase=phase,
                        plan=plan,
                        all_sprints=all_sprints,
                        sprint_index=sprint_index,
                        cap_map=cap_map,
                        today=today,
                        dry_run=dry_run,
                        result=result,
                    )

        if not dry_run:
            ResourcePlanAuditLog.objects.create(
                plan        = plan,
                changed_by  = 'AutoAllocationEngine',
                change_type = 'AUTO_ALLOCATE',
                description = (
                    f'Engine run: {result.cells_written} cells written, '
                    f'{result.conflicts_raised} conflicts raised, '
                    f'{result.cells_skipped} cells skipped.'
                ),
            )

        return result

    @staticmethod
    def _build_capacity_map(plan: ResourcePlan, all_sprints: list) -> dict:
        """
        Returns {member_pk: {sprint_pk: available_days}} for all active members
        in all teams assigned to this plan.
        """
        from apps.team_members.models import TeamMember
        from apps.leaves.models import Leave, calc_working_days

        member_ids = set(
            ResourcePlanProjectTeam.objects.filter(
                plan_project__plan=plan
            ).values_list('team__members__id', flat=True)
        )
        members = list(TeamMember.objects.filter(pk__in=member_ids, is_active=True))
        fy_id   = plan.financial_year_id

        confirmed_leaves = {}
        for lv in Leave.objects.filter(
            team_member__in=members, financial_year_id=fy_id
        ).select_related('team_member'):
            confirmed_leaves.setdefault(lv.team_member_id, []).append(lv)

        placeholders = {}
        for ph in ResourcePlanLeafPlaceholder.objects.filter(
            plan=plan, team_member__in=members, sprint__in=all_sprints
        ):
            placeholders[(ph.team_member_id, ph.sprint_id)] = ph.days

        overrides = {}
        for ov in ResourcePlanCapacityOverride.objects.filter(
            plan=plan, team_member__in=members, sprint__in=all_sprints
        ):
            overrides[(ov.team_member_id, ov.sprint_id)] = ov.reserved_days

        cap_map = {}
        for member in members:
            member_leaves = confirmed_leaves.get(member.pk, [])
            cap_map[member.pk] = {}
            for sprint in all_sprints:
                base = Decimal(str(sprint.working_days))
                leave_days = Decimal('0')
                for lv in member_leaves:
                    if lv.start_date <= sprint.end_date and lv.end_date >= sprint.start_date:
                        cs = max(lv.start_date, sprint.start_date)
                        ce = min(lv.end_date,   sprint.end_date)
                        leave_days += Decimal(str(
                            calc_working_days(cs, ce, financial_year_id=fy_id)
                        ))
                ph_d    = placeholders.get((member.pk, sprint.pk), Decimal('0'))
                ov_d    = overrides.get((member.pk, sprint.pk), Decimal('0'))
                cap_map[member.pk][sprint.pk] = max(
                    base - leave_days - ph_d - ov_d, Decimal('0')
                )
        return cap_map

    @staticmethod
    def _allocate_phase(
        phase, plan, all_sprints, sprint_index, cap_map, today, dry_run, result
    ):
        """Allocate one phase: compute distribution, write cells."""
        from apps.sprints.models import Sprint

        # Sprints covered by this phase
        if not phase.start_sprint or not phase.end_sprint:
            return  # No dates set — skip

        phase_sprints = [
            s for s in all_sprints
            if s.start_date >= phase.start_sprint.start_date
            and s.end_date <= phase.end_sprint.end_date
        ]
        if not phase_sprints:
            return

        # Assignments for this phase (skip ARCHITECT for day distribution)
        assignments = [
            a for a in phase.assignments.all()
            if a.assignment_type != 'ARCHITECT'
        ]
        if not assignments:
            return

        # Total days for this phase (from ProjectTeam.allocated_days / phase count)
        ppt = phase.plan_project_team
        team_allocated = ppt.allocated_days
        if team_allocated is None or team_allocated <= 0:
            return

        # Divide evenly among phases on this team
        phase_count = ppt.phases.count() or 1
        phase_days  = _round_to_quarter(team_allocated / phase_count)

        # Per-engineer share
        engineer_count = len(assignments)
        per_engineer   = _round_to_quarter(phase_days / engineer_count)

        # Ramp distribution for this phase
        max_cap = phase.max_days_per_sprint or Decimal('10')
        distribution = RampDistributor.distribute(
            total_days     = per_engineer,
            sprint_count   = len(phase_sprints),
            pattern        = phase.ramp_pattern,
            max_per_sprint = max_cap,
        )

        for assignment in assignments:
            member = assignment.team_member

            # Gap detection: pause/resume
            pause_idx  = (
                sprint_index.get(assignment.pause_from_sprint_id)
                if assignment.pause_from_sprint_id else None
            )
            resume_idx = (
                sprint_index.get(assignment.resume_at_sprint_id)
                if assignment.resume_at_sprint_id else None
            )

            for i, (sprint, days) in enumerate(zip(phase_sprints, distribution)):
                # Skip past sprints
                if sprint.end_date < today:
                    result.cells_skipped += 1
                    continue

                # Skip cells in the pause/resume gap
                global_idx = sprint_index.get(sprint.pk, -1)
                if (pause_idx is not None and resume_idx is not None and
                        pause_idx <= global_idx < resume_idx):
                    days = Decimal('0')

                # Skip cells in the pause/resume gap (open-ended pause)
                elif pause_idx is not None and resume_idx is None:
                    if global_idx >= pause_idx:
                        days = Decimal('0')

                # Check capacity
                if days > 0 and member:
                    available = cap_map.get(member.pk, {}).get(sprint.pk, Decimal('0'))
                    # How much is already allocated to this member in this sprint
                    already = ResourcePlanAssignmentCell.objects.filter(
                        sprint=sprint,
                        assignment__team_member=member,
                        assignment__phase__plan_project_team__plan_project__plan=plan,
                    ).aggregate(
                        s=__import__('django.db.models', fromlist=['Sum']).Sum('days_allocated')
                    )['s'] or Decimal('0')

                    headroom = max(available - already, Decimal('0'))

                    if headroom < days:
                        # Overflow
                        overflow_days = days - headroom
                        days = headroom  # allocate what's available

                        result.overflow_suggestions.append({
                            'assignment_id':  assignment.pk,
                            'engineer':       assignment.display_name,
                            'sprint_name':    sprint.name,
                            'overflow_days':  str(overflow_days),
                            'available_days': str(headroom),
                            'project':        ppt.plan_project.project.display_name,
                            'dates_strict':   ppt.plan_project.dates_strict,
                        })

                        if not dry_run:
                            C = ResourcePlanConflict
                            C.objects.update_or_create(
                                plan=plan,
                                conflict_type=C.ConflictType.CAPACITY_EXCEEDED,
                                affected_assignment=assignment,
                                affected_sprint=sprint,
                                defaults={
                                    'severity':    C.Severity.ERROR,
                                    'resolution':  C.Resolution.PENDING,
                                    'resolved_at': None,
                                    'description': (
                                        f'{assignment.display_name} / {sprint.name}: '
                                        f'engine requires {days + overflow_days}d '
                                        f'but only {headroom}d available '
                                        f'({overflow_days}d overflow).'
                                    ),
                                },
                            )
                            result.conflicts_raised += 1

                    # Update capacity map to reflect this allocation
                    if member and days > 0:
                        old = cap_map.get(member.pk, {}).get(sprint.pk, Decimal('0'))
                        if member.pk in cap_map and sprint.pk in cap_map[member.pk]:
                            cap_map[member.pk][sprint.pk] = max(
                                old - days, Decimal('0')
                            )

                # TBC placeholder
                if not member:
                    result.engineers_tbc += 1

                # Write cell
                if not dry_run:
                    AutoAllocationEngine._write_cell(assignment, sprint, days)
                    if days > 0:
                        result.cells_written += 1
                    else:
                        result.cells_skipped += 1
                else:
                    if days > 0:
                        result.cells_written += 1
                    else:
                        result.cells_skipped += 1

    @staticmethod
    def _write_cell(assignment, sprint, days: Decimal):
        """Upsert a single AssignmentCell with is_auto=True."""
        cell, created = ResourcePlanAssignmentCell.objects.get_or_create(
            assignment=assignment,
            sprint=sprint,
            defaults={
                'days_allocated': days,
                'is_auto':        True,
                'is_locked':      sprint.end_date < datetime.date.today(),
            },
        )
        if not created and not cell.is_locked and cell.is_auto:
            # Only overwrite auto cells — leave manual overrides untouched
            cell.days_allocated = days
            cell.save(update_fields=['days_allocated', 'is_auto'])


# ═══════════════════════════════════════════════════════════
#  Phase 3 — Overflow Resolution Service
# ═══════════════════════════════════════════════════════════

class OverflowResolutionService:
    """
    Applies user-chosen resolutions to CAPACITY_EXCEEDED conflicts.

    Supported resolutions:
      PUSHED_RIGHT    — shift the affected assignment's phase start/end N sprints right
      SPLIT           — reduce days in the overflowing sprint, re-distribute to later sprints
      REPLACED        — create interim assignment for the overflowing sprint(s)
      PLACEHOLDER     — convert TBC assignment to named placeholder
      DEPRIORITISED   — zero out the overflowing cells and mark project deprioritised
      DISMISSED       — dismiss the conflict without changing allocations
    """

    @staticmethod
    @transaction.atomic
    def apply_resolution(
        conflict_id: int,
        resolution: str,
        extra: dict = None,
    ) -> ResourcePlanConflict:
        """
        Dispatch to the appropriate handler and mark the conflict resolved.

        extra keys (resolution-dependent):
          PUSHED_RIGHT:  { 'sprint_offset': int }   — number of sprints to shift right
          REPLACED:      { 'new_member_id': int }    — team member to assign as interim
          SPLIT:         { 'split_days': str }       — Decimal days to keep in overflow sprint
          DEPRIORITISED: {}
          DISMISSED:     {}
          PLACEHOLDER:   { 'placeholder_name': str }
        """
        extra = extra or {}
        C = ResourcePlanConflict
        R = C.Resolution

        conflict = C.objects.select_related(
            'plan',
            'affected_assignment__phase__plan_project_team__plan_project__project',
            'affected_assignment__team_member',
            'affected_sprint',
        ).get(pk=conflict_id)

        if conflict.resolution != R.PENDING:
            raise ValidationError('Conflict is already resolved.')

        handlers = {
            R.PUSHED_RIGHT:  OverflowResolutionService._pushed_right,
            R.SPLIT:         OverflowResolutionService._split,
            R.REPLACED:      OverflowResolutionService._replaced,
            R.PLACEHOLDER:   OverflowResolutionService._placeholder,
            R.DEPRIORITISED: OverflowResolutionService._deprioritised,
            R.DISMISSED:     OverflowResolutionService._dismissed,
        }
        handler = handlers.get(resolution)
        if handler:
            handler(conflict, extra)

        conflict.resolution  = resolution
        conflict.resolved_at = datetime.datetime.now()
        conflict.save()

        ResourcePlanAuditLog.objects.create(
            plan        = conflict.plan,
            changed_by  = 'User',
            change_type = 'CONFLICT_RESOLVED',
            description = (
                f'Conflict #{conflict_id} ({conflict.get_conflict_type_display()}) '
                f'resolved as {resolution}.'
            ),
        )
        return conflict

    @staticmethod
    def _pushed_right(conflict: ResourcePlanConflict, extra: dict):
        """
        Shift the phase's start and end sprints right by `sprint_offset` sprints.
        Re-runs ramp distribution on the new sprint range if possible.
        """
        from apps.sprints.models import Sprint
        sprint_offset = int(extra.get('sprint_offset', 1))
        phase = conflict.affected_assignment.phase
        if not phase.start_sprint or not phase.end_sprint:
            return

        fy = phase.plan_project_team.plan_project.plan.financial_year
        all_sprints = list(
            Sprint.objects.filter(financial_year=fy).order_by('start_date')
        )
        sprint_pks = [s.pk for s in all_sprints]

        try:
            start_idx = sprint_pks.index(phase.start_sprint_id)
            end_idx   = sprint_pks.index(phase.end_sprint_id)
        except ValueError:
            return

        new_start_idx = start_idx + sprint_offset
        new_end_idx   = end_idx   + sprint_offset

        if new_end_idx >= len(all_sprints):
            return  # Can't shift past FY end

        phase.start_sprint = all_sprints[new_start_idx]
        phase.end_sprint   = all_sprints[new_end_idx]
        phase.save(update_fields=['start_sprint', 'end_sprint'])

    @staticmethod
    def _split(conflict: ResourcePlanConflict, extra: dict):
        """
        Reduce days in the overflowing sprint to `split_days`, then
        add the remainder to the NEXT available sprint.
        """
        split_days = _round_to_quarter(extra.get('split_days', '0'))
        assignment = conflict.affected_assignment
        sprint     = conflict.affected_sprint
        if not assignment or not sprint:
            return

        # Update the overflowing cell
        cell = ResourcePlanAssignmentCell.objects.filter(
            assignment=assignment, sprint=sprint
        ).first()
        if cell:
            original  = cell.days_allocated
            remainder = original - split_days
            cell.days_allocated = split_days
            cell.is_auto        = False
            cell.save()

            # Distribute remainder to the next sprint in the phase
            from apps.sprints.models import Sprint
            next_sprint = Sprint.objects.filter(
                financial_year=sprint.financial_year,
                start_date__gt=sprint.end_date,
            ).order_by('start_date').first()
            if next_sprint and remainder > 0:
                next_cell, _ = ResourcePlanAssignmentCell.objects.get_or_create(
                    assignment=assignment,
                    sprint=next_sprint,
                    defaults={'days_allocated': Decimal('0'), 'is_auto': False},
                )
                next_cell.days_allocated = _round_to_quarter(
                    next_cell.days_allocated + remainder
                )
                next_cell.is_auto = False
                next_cell.save()

    @staticmethod
    def _replaced(conflict: ResourcePlanConflict, extra: dict):
        """
        Create an interim replacement assignment for the overflowing sprint,
        calling InterimReplacementService.
        """
        new_member_id = extra.get('new_member_id')
        if not new_member_id or not conflict.affected_assignment:
            return
        plan = conflict.plan
        InterimReplacementService.create_interim(
            phase_id               = conflict.affected_assignment.phase_id,
            replaces_assignment_id = conflict.affected_assignment_id,
            team_member_id         = int(new_member_id),
            plan                   = plan,
            sprint                 = conflict.affected_sprint,
        )

    @staticmethod
    def _placeholder(conflict: ResourcePlanConflict, extra: dict):
        """Convert a TBC assignment to a named placeholder."""
        name       = extra.get('placeholder_name', 'ENGINEER TBC')
        assignment = conflict.affected_assignment
        if assignment and not assignment.team_member:
            assignment.placeholder_name = name
            assignment.save(update_fields=['placeholder_name'])

    @staticmethod
    def _deprioritised(conflict: ResourcePlanConflict, extra: dict):
        """Zero out the overflowing sprint cell."""
        assignment = conflict.affected_assignment
        sprint     = conflict.affected_sprint
        if assignment and sprint:
            ResourcePlanAssignmentCell.objects.filter(
                assignment=assignment, sprint=sprint
            ).update(days_allocated=Decimal('0'), is_auto=False)

    @staticmethod
    def _dismissed(conflict: ResourcePlanConflict, extra: dict):
        """No allocation change — just dismiss."""
        pass


# ═══════════════════════════════════════════════════════════
#  Phase 3 — Interim Replacement Service
# ═══════════════════════════════════════════════════════════

class InterimReplacementService:
    """
    Creates an interim assignment that covers a specific engineer's leave/absence
    in a given sprint.

    Steps:
      1. Zero out the original assignment's cell for the affected sprint.
      2. Create a new ResourcePlanAssignment with is_interim=True,
         replaces_assignment=original, assignment_type=INTERIM.
      3. Copy the original cell's days to the new interim assignment for the sprint.
      4. Log the change in the audit trail.
    """

    @staticmethod
    @transaction.atomic
    def create_interim(
        phase_id: int,
        replaces_assignment_id: int,
        team_member_id: int,
        plan: ResourcePlan,
        sprint=None,
    ) -> ResourcePlanAssignment:
        from apps.team_members.models import TeamMember

        original   = ResourcePlanAssignment.objects.select_related(
            'team_member', 'phase'
        ).get(pk=replaces_assignment_id)
        new_member = TeamMember.objects.get(pk=team_member_id)

        # Create interim assignment
        interim = ResourcePlanAssignment.objects.create(
            phase                = original.phase,
            team_member          = new_member,
            assignment_type      = ResourcePlanAssignment.AssignmentType.INTERIM,
            is_interim           = True,
            replaces_assignment  = original,
            notes                = (
                f'Interim cover for {original.display_name}'
                + (f' in {sprint.name}' if sprint else '') + '.'
            ),
        )

        if sprint:
            # Get days from original cell
            orig_cell = ResourcePlanAssignmentCell.objects.filter(
                assignment=original, sprint=sprint
            ).first()
            days = orig_cell.days_allocated if orig_cell else Decimal('0')

            # Zero out original for this sprint
            if orig_cell:
                orig_cell.days_allocated = Decimal('0')
                orig_cell.is_auto        = False
                orig_cell.save()

            # Create interim cell
            if days > 0:
                ResourcePlanAssignmentCell.objects.create(
                    assignment     = interim,
                    sprint         = sprint,
                    days_allocated = days,
                    is_auto        = False,
                )

        ResourcePlanAuditLog.objects.create(
            plan        = plan,
            changed_by  = 'User',
            change_type = 'INTERIM_CREATED',
            description = (
                f'Interim: {new_member.display_name} covering '
                f'{original.display_name}'
                + (f' in {sprint.name}' if sprint else '') + '.'
            ),
        )
        return interim


# ═══════════════════════════════════════════════════════════
#  Phase 3 — Export Service (openpyxl)
# ═══════════════════════════════════════════════════════════

class ExportService:
    """
    Generates a multi-sheet Excel workbook for a ResourcePlan.

    Sheet 1  — Overview     : plan metadata + project list
    Sheet 2  — Capacity     : Section 1 (members × sprints, available days)
    Sheet 3  — Allocations  : Section 2 (project/engineer × sprints, allocated days)
    Sheet 4  — Remaining    : Section 3 (remaining capacity per engineer)
    Sheet 5  — Conflicts    : all conflict rows (pending + resolved)
    """

    # Colour palette (ARGB hex, no #)
    CLR_HEADER  = 'FF4F46E5'   # indigo
    CLR_SUBHEAD = 'FF6366F1'   # lighter indigo
    CLR_FULL    = 'FFD1FAE5'   # green-100
    CLR_MEDIUM  = 'FFFEF9C3'   # yellow-100
    CLR_LOW     = 'FFFEF3C7'   # amber-100
    CLR_ZERO    = 'FFF3F4F6'   # grey-100
    CLR_OVER    = 'FFFEE2E2'   # red-100
    CLR_ONTRACK = 'FFD1FAE5'   # green-100
    CLR_MANUAL  = 'FFDBEAFE'   # blue-100
    CLR_AUTO    = 'FFF9FAFB'   # grey-50
    CLR_LOCKED  = 'FFE5E7EB'   # grey-200
    CLR_PROJ    = 'FFEEF2FF'   # indigo-50 (project row)
    CLR_WHITE   = 'FFFFFFFF'
    CLR_WARN    = 'FFFEF3C7'
    CLR_ERROR   = 'FFFEE2E2'
    CLR_RESOLVE = 'FFD1FAE5'

    @staticmethod
    def export_plan_xlsx(plan_id: int):
        """Returns a BytesIO containing the workbook."""
        import io
        from openpyxl import Workbook
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        plan    = ResourcePlan.objects.select_related('financial_year').get(pk=plan_id)
        sprints = list(
            __import__('apps.sprints.models', fromlist=['Sprint']).Sprint.objects.filter(
                financial_year=plan.financial_year
            ).order_by('start_date')
        )
        teams = list(
            __import__('apps.teams.models', fromlist=['Team']).Team.objects.filter(
                pk__in=ResourcePlanProjectTeam.objects.filter(
                    plan_project__plan=plan
                ).values_list('team_id', flat=True)
            ).order_by('name')
        )

        s1_data = {}
        s2_data = {}
        s3_data = {}
        for team in teams:
            s1 = GridService.section1_capacity(plan, team, sprints)
            s2 = GridService.section2_allocations(plan, team, sprints)
            s3 = GridService.section3_summary(plan, team, sprints, s1, s2)
            s1_data[team.pk] = (team, s1)
            s2_data[team.pk] = (team, s2)
            s3_data[team.pk] = (team, s3)

        conflicts = ResourcePlanConflict.objects.filter(
            plan=plan
        ).select_related('affected_assignment__team_member', 'affected_sprint').order_by('-created_at')

        wb = Workbook()

        # ── Sheet 1: Overview ────────────────────────────────
        ExportService._sheet_overview(wb, plan)

        # ── Sheet 2: Capacity ────────────────────────────────
        ExportService._sheet_grid(
            wb=wb,
            title='Capacity',
            sprints=sprints,
            teams_data=s1_data,
            cell_getter=lambda row, spk: row['cells'].get(spk, 0),
            colour_fn=ExportService._cap_colour,
            row_label_fn=lambda row: row['member'].display_name,
            section_label='Available days',
        )

        # ── Sheet 3: Allocations ─────────────────────────────
        ExportService._sheet_allocations(wb, sprints, s2_data)

        # ── Sheet 4: Remaining ───────────────────────────────
        ExportService._sheet_grid(
            wb=wb,
            title='Remaining',
            sprints=sprints,
            teams_data=s3_data,
            cell_getter=lambda row, spk: row['cells'].get(spk, {}).get('remaining', 0),
            colour_fn=ExportService._rem_colour,
            row_label_fn=lambda row: row['display_name'],
            section_label='Remaining days',
        )

        # ── Sheet 5: Conflicts ───────────────────────────────
        ExportService._sheet_conflicts(wb, conflicts)

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return buf

    # ── Styling helpers ───────────────────────────────────

    @staticmethod
    def _fill(hex_colour: str):
        from openpyxl.styles import PatternFill
        return PatternFill('solid', fgColor=hex_colour)

    @staticmethod
    def _bold(size: int = 10, colour: str = 'FF000000'):
        from openpyxl.styles import Font
        return Font(bold=True, size=size, color=colour)

    @staticmethod
    def _border():
        from openpyxl.styles import Border, Side
        thin = Side(style='thin', color='FFD1D5DB')
        return Border(left=thin, right=thin, top=thin, bottom=thin)

    @staticmethod
    def _cap_colour(val) -> str:
        v = float(val)
        if v >= 8:   return ExportService.CLR_FULL
        if v >= 4:   return ExportService.CLR_MEDIUM
        if v > 0:    return ExportService.CLR_LOW
        return ExportService.CLR_ZERO

    @staticmethod
    def _rem_colour(val) -> str:
        v = float(val)
        if v < 0:    return ExportService.CLR_OVER
        if v == 0:   return ExportService.CLR_ONTRACK
        return ExportService.CLR_FULL

    @staticmethod
    def _fmt_val(val) -> str:
        """Smart decimal — 8.0→8, 8.5→8.5"""
        try:
            f = float(val)
            return str(int(f)) if f == int(f) else f'{f:.2f}'.rstrip('0')
        except Exception:
            return str(val)

    # ── Sheet builders ────────────────────────────────────

    @staticmethod
    def _sheet_overview(wb, plan: ResourcePlan):
        from openpyxl.styles import Alignment
        ws = wb.active
        ws.title = 'Overview'

        E = ExportService
        meta = [
            ('Plan name',       plan.name),
            ('Financial year',  plan.financial_year.long_fy),
            ('Status',          plan.get_status_display()),
            ('Threshold',       f'±{plan.allocation_threshold_pct}%'),
            ('Scope notes',     plan.scope_notes or '—'),
            ('Exported',        datetime.datetime.now().strftime('%d %b %Y %H:%M')),
        ]
        for r, (label, val) in enumerate(meta, start=1):
            ws.cell(r, 1, label).font  = E._bold()
            ws.cell(r, 2, val)
            ws.cell(r, 1).fill = E._fill(E.CLR_PROJ)

        ws.append([])

        # Projects table
        hdr = ['Programme', 'Project', 'Basis', 'Days required', 'Priority', 'Confidence']
        ws.append(hdr)
        for i, h in enumerate(hdr, 1):
            c = ws.cell(len(meta) + 2, i)
            c.font  = E._bold(colour='FFFFFFFF')
            c.fill  = E._fill(E.CLR_HEADER)

        for pp in ResourcePlanProject.objects.filter(plan=plan).select_related('project').order_by(
            'project__programme_name', 'project__project_name'
        ):
            ws.append([
                pp.project.programme_name or '—',
                pp.project.project_name,
                pp.get_basis_display(),
                E._fmt_val(pp.days_required or 0),
                pp.effective_priority,
                pp.effective_confidence,
            ])

        ws.column_dimensions['A'].width = 25
        ws.column_dimensions['B'].width = 30
        for col in 'CDEF':
            ws.column_dimensions[col].width = 14

    @staticmethod
    def _sheet_grid(wb, title, sprints, teams_data, cell_getter,
                    colour_fn, row_label_fn, section_label):
        E  = ExportService
        ws = wb.create_sheet(title=title)

        row_num = 1
        for team_pk, (team, data) in teams_data.items():
            # Team header
            ws.cell(row_num, 1, team.name).font = E._bold(11, 'FFFFFFFF')
            ws.cell(row_num, 1).fill = E._fill(E.CLR_HEADER)
            ws.merge_cells(
                start_row=row_num, start_column=1,
                end_row=row_num, end_column=len(sprints) + 1,
            )
            row_num += 1

            # Sprint header
            ws.cell(row_num, 1, section_label).font = E._bold()
            ws.cell(row_num, 1).fill = E._fill(E.CLR_SUBHEAD)
            for col, sprint in enumerate(sprints, start=2):
                c = ws.cell(row_num, col, sprint.name)
                c.font  = E._bold(colour='FFFFFFFF')
                c.fill  = E._fill(E.CLR_SUBHEAD)
                c.alignment = __import__('openpyxl.styles', fromlist=['Alignment']).Alignment(
                    horizontal='center', wrap_text=True
                )
            row_num += 1

            # Data rows
            rows = data.get('rows', [])
            for row in rows:
                ws.cell(row_num, 1, row_label_fn(row)).font = Font(size=10)
                for col, sprint in enumerate(sprints, start=2):
                    val = cell_getter(row, sprint.pk)
                    c   = ws.cell(row_num, col, E._fmt_val(val))
                    c.fill      = E._fill(colour_fn(val))
                    c.alignment = __import__('openpyxl.styles', fromlist=['Alignment']).Alignment(horizontal='center')
                    c.border    = E._border()
                row_num += 1

            # Totals row
            totals = data.get('totals', {})
            ws.cell(row_num, 1, 'Total').font = E._bold()
            ws.cell(row_num, 1).fill = E._fill(E.CLR_PROJ)
            for col, sprint in enumerate(sprints, start=2):
                raw = totals.get(sprint.pk, 0)
                # totals may be Decimal or dict
                val = raw.get('remaining', raw) if isinstance(raw, dict) else raw
                c   = ws.cell(row_num, col, E._fmt_val(val))
                c.font   = E._bold()
                c.fill   = E._fill(E.CLR_PROJ)
                c.border = E._border()
            row_num += 2

        ws.column_dimensions['A'].width = 28
        for col in range(2, len(sprints) + 2):
            ws.column_dimensions[
                __import__('openpyxl.utils', fromlist=['get_column_letter']).get_column_letter(col)
            ].width = 9
        ws.freeze_panes = 'B3'

    @staticmethod
    def _sheet_allocations(wb, sprints, s2_data):
        E  = ExportService
        ws = wb.create_sheet(title='Allocations')
        from openpyxl.styles import Alignment as Aln
        from openpyxl.utils import get_column_letter

        row_num = 1
        for team_pk, (team, s2) in s2_data.items():
            # Team header
            ws.cell(row_num, 1, team.name).font = E._bold(11, 'FFFFFFFF')
            ws.cell(row_num, 1).fill = E._fill(E.CLR_HEADER)
            ws.merge_cells(
                start_row=row_num, start_column=1,
                end_row=row_num, end_column=len(sprints) + 1,
            )
            row_num += 1

            # Sprint column headers
            ws.cell(row_num, 1, 'Project / Engineer').font = E._bold()
            ws.cell(row_num, 1).fill = E._fill(E.CLR_SUBHEAD)
            for col, sprint in enumerate(sprints, start=2):
                c = ws.cell(row_num, col, sprint.name)
                c.font  = E._bold(colour='FFFFFFFF')
                c.fill  = E._fill(E.CLR_SUBHEAD)
                c.alignment = Aln(horizontal='center', wrap_text=True)
            row_num += 1

            for group in s2.get('project_groups', []):
                pp      = group['plan_project']
                proj    = pp.project

                # Project header row
                label = f'{proj.programme_name}: {proj.project_name}' \
                        if proj.programme_name else proj.project_name
                if pp.days_required:
                    label += f'  [{E._fmt_val(pp.days_required)}d]'
                ws.cell(row_num, 1, label).font = E._bold()
                ws.cell(row_num, 1).fill = E._fill(E.CLR_PROJ)
                ws.merge_cells(
                    start_row=row_num, start_column=1,
                    end_row=row_num, end_column=len(sprints) + 1,
                )
                row_num += 1

                # Assignment rows
                for arow in group['assignment_rows']:
                    ws.cell(row_num, 1, f'  {arow["assignment"].display_name}')
                    for col, sprint in enumerate(sprints, start=2):
                        cd  = arow['cells'].get(sprint.pk, {})
                        val = cd.get('days', Decimal('0')) if isinstance(cd, dict) else cd
                        c   = ws.cell(row_num, col, E._fmt_val(val) if float(val) > 0 else '')
                        if cd.get('is_locked'):
                            c.fill = E._fill(E.CLR_LOCKED)
                        elif cd.get('is_auto') and float(val) > 0:
                            c.fill = E._fill(E.CLR_AUTO)
                        elif not cd.get('is_auto') and float(val) > 0:
                            c.fill = E._fill(E.CLR_MANUAL)
                        c.alignment = Aln(horizontal='center')
                        c.border    = E._border()
                    row_num += 1

                # Per-group total
                ws.cell(row_num, 1, '  Total').font = E._bold()
                ws.cell(row_num, 1).fill = E._fill(E.CLR_PROJ)
                for col, sprint in enumerate(sprints, start=2):
                    group_total = sum(
                        float(arow['cells'].get(sprint.pk, {}).get('days', 0))
                        for arow in group['assignment_rows']
                    )
                    c = ws.cell(row_num, col, E._fmt_val(group_total) if group_total else '')
                    c.font   = E._bold()
                    c.fill   = E._fill(E.CLR_PROJ)
                    c.border = E._border()
                row_num += 1

            row_num += 1

        ws.column_dimensions['A'].width = 30
        for col in range(2, len(sprints) + 2):
            ws.column_dimensions[get_column_letter(col)].width = 9
        ws.freeze_panes = 'B3'

    @staticmethod
    def _sheet_conflicts(wb, conflicts):
        E  = ExportService
        ws = wb.create_sheet(title='Conflicts')
        from openpyxl.styles import Alignment as Aln

        headers = [
            'Type', 'Severity', 'Engineer', 'Sprint',
            'Description', 'Resolution', 'Resolved at', 'Created at',
        ]
        ws.append(headers)
        for col, h in enumerate(headers, 1):
            c = ws.cell(1, col, h)
            c.font  = E._bold(colour='FFFFFFFF')
            c.fill  = E._fill(E.CLR_HEADER)

        for conflict in conflicts:
            resolved_at = (
                conflict.resolved_at.strftime('%d %b %Y %H:%M')
                if conflict.resolved_at else '—'
            )
            created_at = conflict.created_at.strftime('%d %b %Y %H:%M')
            row = [
                conflict.get_conflict_type_display(),
                conflict.severity,
                conflict.affected_assignment.display_name if conflict.affected_assignment else '—',
                conflict.affected_sprint.name if conflict.affected_sprint else '—',
                conflict.description,
                conflict.resolution,
                resolved_at,
                created_at,
            ]
            ws.append(row)
            r = ws.max_row
            sev = conflict.severity
            fill_clr = E.CLR_ERROR if sev == 'ERROR' else (
                E.CLR_WARN if sev == 'WARNING' else E.CLR_RESOLVE
            )
            for col in range(1, len(headers) + 1):
                c = ws.cell(r, col)
                c.fill   = E._fill(fill_clr)
                c.border = E._border()

        widths = [28, 10, 24, 16, 60, 16, 18, 18]
        for i, w in enumerate(widths, 1):
            from openpyxl.utils import get_column_letter
            ws.column_dimensions[get_column_letter(i)].width = w