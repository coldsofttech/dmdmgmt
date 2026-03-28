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
    def list_plans(financial_year_id: int = None):
        qs = ResourcePlan.objects.select_related('financial_year').all()
        if financial_year_id:
            qs = qs.filter(financial_year_id=financial_year_id)
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
    def upsert_cell(assignment_id: int, sprint_id: int,
                    days: Decimal, changed_by: str = 'User') -> ResourcePlanAssignmentCell:
        """
        Create or update a cell.
        Marks is_auto=False (manual override) and logs the change.
        Raises ValidationError if the sprint is locked (past sprint).
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
            old_val = cell.days_allocated
            cell.days_allocated = rounded
            cell.is_auto        = False
            cell.save()
        else:
            old_val = Decimal('0')

        # Audit
        assignment = ResourcePlanAssignment.objects.select_related(
            'phase__plan_project_team__plan_project__plan'
        ).get(pk=assignment_id)
        plan = assignment.phase.plan_project_team.plan_project.plan
        ResourcePlanAuditLog.objects.create(
            plan        = plan,
            changed_by  = changed_by,
            change_type = 'CELL_UPDATE',
            description = (
                f'{assignment.display_name} / {sprint.name}: '
                f'{old_val}d → {rounded}d'
            ),
        )

        # Check threshold and log conflict if needed
        CellService._check_threshold(assignment, plan)

        return cell

    @staticmethod
    def _check_threshold(assignment: ResourcePlanAssignment, plan: ResourcePlan):
        """
        After a cell edit, check if total allocated days for the plan-project
        breaches the plan's allocation_threshold_pct. Log a conflict if so.
        """
        try:
            pp = assignment.phase.plan_project_team.plan_project
            total_allocated = Decimal('0')
            for cell in ResourcePlanAssignmentCell.objects.filter(
                assignment__phase__plan_project_team__plan_project=pp
            ):
                total_allocated += cell.days_allocated

            days_required = pp.days_required
            if not days_required or days_required <= 0:
                return

            threshold    = plan.allocation_threshold_pct / Decimal('100')
            upper_limit  = days_required * (1 + threshold)
            lower_limit  = days_required * (1 - threshold)

            conflict_type = None
            if total_allocated > upper_limit:
                conflict_type = ResourcePlanConflict.ConflictType.OVER_BUDGET
                severity      = ResourcePlanConflict.Severity.ERROR
                desc = (
                    f'{pp.project.display_name}: allocated {total_allocated}d '
                    f'exceeds {days_required}d + {plan.allocation_threshold_pct}% threshold '
                    f'(limit: {upper_limit:.2f}d).'
                )
            elif total_allocated < lower_limit:
                conflict_type = ResourcePlanConflict.ConflictType.UNDER_BUDGET
                severity      = ResourcePlanConflict.Severity.WARNING
                desc = (
                    f'{pp.project.display_name}: allocated {total_allocated}d '
                    f'is below {days_required}d − {plan.allocation_threshold_pct}% threshold '
                    f'(min: {lower_limit:.2f}d).'
                )

            if conflict_type:
                # Upsert — don't create duplicate conflicts for the same assignment
                ResourcePlanConflict.objects.update_or_create(
                    plan=plan,
                    conflict_type=conflict_type,
                    affected_assignment=assignment,
                    resolution=ResourcePlanConflict.Resolution.PENDING,
                    defaults={'severity': severity, 'description': desc},
                )
        except Exception:
            pass  # Never let threshold checking break the cell save


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
    def generate_for_plan(plan: ResourcePlan) -> int:
        """
        For each active team member in the plan's teams, check if their
        confirmed leaves total < DEFAULT_HOLIDAYS. If so, auto-insert
        ResourcePlanLeafPlaceholder rows in the SECOND HALF of remaining sprints.

        Days per placeholder: 1.0 for whole-day blocks, 0.5 for remainder.
        Returns the number of placeholder rows created.
        """
        from apps.sprints.models import Sprint
        from apps.leaves.models import Leave
        from apps.team_members.models import TeamMember

        fy         = plan.financial_year
        today      = datetime.date.today()
        default_h  = _get_default_holidays()

        # Future sprints only (3.36)
        future_sprints = list(
            Sprint.objects.filter(
                financial_year=fy,
                end_date__gte=today,
            ).order_by('start_date')
        )
        if not future_sprints:
            return 0

        # Second half only
        half          = len(future_sprints) // 2
        target_sprints = future_sprints[half:]
        if not target_sprints:
            return 0

        # Gather members across all teams in this plan
        member_ids = set(
            ResourcePlanProjectTeam.objects.filter(
                plan_project__plan=plan
            ).values_list('team__members__id', flat=True)
        )
        members = TeamMember.objects.filter(pk__in=member_ids, is_active=True)

        created = 0
        for member in members:
            # Count confirmed leaves in this FY
            confirmed_days = sum(
                l.days for l in Leave.objects.filter(
                    team_member=member,
                    financial_year=fy,
                )
            )
            remaining_leave = default_h - float(confirmed_days)
            if remaining_leave <= 0:
                continue

            # Remove already-existing placeholders for this plan+member
            ResourcePlanLeafPlaceholder.objects.filter(
                plan=plan, team_member=member
            ).delete()

            # Spread remaining_leave across target_sprints as 1.0 or 0.5 blocks
            days_left = remaining_leave
            for sprint in target_sprints:
                if days_left <= 0:
                    break
                block = 1.0 if days_left >= 1.0 else 0.5
                ResourcePlanLeafPlaceholder.objects.create(
                    plan=plan,
                    team_member=member,
                    sprint=sprint,
                    days=Decimal(str(block)),
                    is_auto_generated=True,
                )
                days_left -= block
                created   += 1

        return created


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