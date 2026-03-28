from decimal import Decimal
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from .services import (
    ResourcePlanService, PlanProjectService, PlanProjectTeamService,
    PlanPhaseService, PlanAssignmentService, CellService,
    ConflictService, PlaceholderLeaveService, GridService,
)
from .serializers import (
    ResourcePlanSerializer, ResourcePlanProjectSerializer,
    ResourcePlanProjectTeamSerializer, ResourcePlanPhaseSerializer,
    ResourcePlanAssignmentSerializer, ResourcePlanAssignmentCellSerializer,
    ResourcePlanConflictSerializer,
)
from .models import ResourcePlan


def _err(exc):
    if hasattr(exc, 'message_dict'):
        return exc.message_dict
    if hasattr(exc, 'message'):
        return {'detail': exc.message}
    return {'detail': str(exc)}


class ResourcePlanViewSet(viewsets.ViewSet):
    """
    list        GET    /api/v1/resource-plans/
    retrieve    GET    /api/v1/resource-plans/{id}/
    create      POST   /api/v1/resource-plans/
    update      PUT    /api/v1/resource-plans/{id}/
    destroy     DELETE /api/v1/resource-plans/{id}/

    Extra actions:
    grid        GET    /api/v1/resource-plans/{id}/grid/?team=<pk>&view=sprint|month
    unmapped    GET    /api/v1/resource-plans/{id}/unmapped/
    generate_placeholders POST /api/v1/resource-plans/{id}/generate-placeholders/
    conflicts   GET    /api/v1/resource-plans/{id}/conflicts/
    """

    def list(self, request):
        fy_pk = request.query_params.get('fy')
        plans = ResourcePlanService.list_plans(
            financial_year_id=int(fy_pk) if fy_pk else None
        )
        return Response(ResourcePlanSerializer(plans, many=True).data)

    def retrieve(self, request, pk=None):
        try:
            plan = ResourcePlanService.get_plan(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ResourcePlanSerializer(plan).data)

    def create(self, request):
        serializer = ResourcePlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vd = serializer.validated_data
        try:
            plan = ResourcePlanService.create_plan({
                'name':                     vd['name'],
                'financial_year_id':        vd['financial_year'].pk,
                'status':                   vd.get('status', ResourcePlan.Status.DRAFT),
                'allocation_threshold_pct': vd.get('allocation_threshold_pct', Decimal('10')),
                'scope_notes':              vd.get('scope_notes', ''),
            })
        except ValidationError as exc:
            return Response(_err(exc), status=status.HTTP_400_BAD_REQUEST)
        return Response(ResourcePlanSerializer(plan).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        try:
            plan = ResourcePlanService.update_plan(pk, request.data)
        except (ObjectDoesNotExist, ValidationError) as exc:
            return Response(_err(exc), status=status.HTTP_400_BAD_REQUEST)
        return Response(ResourcePlanSerializer(plan).data)

    def destroy(self, request, pk=None):
        try:
            ResourcePlanService.delete_plan(pk)
        except ObjectDoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['get'])
    def unmapped(self, request, pk=None):
        from apps.projects.serializers import ProjectSerializer
        projects = ResourcePlanService.get_unmapped_projects(pk)
        # Minimal serialisation
        data = [
            {
                'id':           p.pk,
                'display_name': p.display_name,
                'programme':    p.programme_name,
                'status':       p.status,
                'priority':     p.priority,
            }
            for p in projects
        ]
        return Response(data)

    @action(detail=True, methods=['post'], url_path='generate-placeholders')
    def generate_placeholders(self, request, pk=None):
        try:
            plan    = ResourcePlanService.get_plan(pk)
            created = PlaceholderLeaveService.generate_for_plan(plan)
        except ObjectDoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'created': created})

    @action(detail=True, methods=['get'])
    def conflicts(self, request, pk=None):
        conflicts = ConflictService.get_pending_conflicts(pk)
        return Response(ResourcePlanConflictSerializer(conflicts, many=True).data)

    @action(detail=True, methods=['get'])
    def grid(self, request, pk=None):
        """
        Returns Section 1, 2, 3 data for one team.
        ?team=<team_pk>&view=sprint|month
        """
        team_pk = request.query_params.get('team')
        if not team_pk:
            return Response({'detail': '"team" param required.'}, status=400)
        try:
            from apps.teams.models import Team
            plan    = ResourcePlanService.get_plan(pk)
            team    = Team.objects.get(pk=team_pk)
            sprints = GridService.get_sprints_for_plan(plan)
            s1      = GridService.section1_capacity(plan, team, sprints)
            s2      = GridService.section2_allocations(plan, team, sprints)
            s3      = GridService.section3_summary(plan, team, sprints, s1, s2)
        except ObjectDoesNotExist:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Serialise sprint list
        from apps.sprints.serializers import SprintSerializer
        sprints_data = SprintSerializer(sprints, many=True).data

        return Response({
            'plan_id':  pk,
            'team_id':  team_pk,
            'sprints':  sprints_data,
            'section1': _serialise_s1(s1),
            'section2': _serialise_s2(s2),
            'section3': _serialise_s3(s3),
        })


# ── Cell update ViewSet ───────────────────────────────────

class ResourcePlanCellViewSet(viewsets.ViewSet):
    """
    PATCH /api/v1/resource-plan-cells/{assignment_pk}/{sprint_pk}/
    Body: { "days": 5.0 }
    """

    def partial_update(self, request, assignment_pk=None, sprint_pk=None):
        days = request.data.get('days')
        if days is None:
            return Response({'detail': '"days" is required.'}, status=400)
        try:
            cell = CellService.upsert_cell(
                assignment_id=int(assignment_pk),
                sprint_id=int(sprint_pk),
                days=Decimal(str(days)),
                changed_by=request.data.get('changed_by', 'User'),
            )
        except ValidationError as exc:
            return Response(_err(exc), status=status.HTTP_400_BAD_REQUEST)
        return Response(ResourcePlanAssignmentCellSerializer(cell).data)


# ── Conflict resolution ViewSet ───────────────────────────

class ResourcePlanConflictViewSet(viewsets.ViewSet):
    """
    POST /api/v1/resource-plan-conflicts/{id}/resolve/
    Body: { "resolution": "PUSHED_RIGHT" | "SPLIT" | ... }
    """

    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        resolution = request.data.get('resolution')
        if not resolution:
            return Response({'detail': '"resolution" is required.'}, status=400)
        try:
            conflict = ConflictService.resolve(pk, resolution)
        except ValidationError as exc:
            return Response(_err(exc), status=status.HTTP_400_BAD_REQUEST)
        return Response(ResourcePlanConflictSerializer(conflict).data)


# ── Serialisation helpers for grid data ──────────────────

def _serialise_s1(s1: dict) -> dict:
    return {
        'rows': [
            {
                'member_id':   row['member'].pk,
                'member_name': row['member'].display_name,
                'is_architect': row['is_architect'],
                'has_leave_warning': row['has_leave_warning'],
                'cells': {str(k): str(v) for k, v in row['cells'].items()},
                'placeholder_leave_sprints': {
                    str(k): str(v)
                    for k, v in row['placeholder_leave_sprints'].items()
                },
            }
            for row in s1['rows']
        ],
        'totals': {str(k): str(v) for k, v in s1['totals'].items()},
    }


def _serialise_s2(s2: dict) -> dict:
    return {
        'project_groups': [
            {
                'plan_project_id': g['plan_project'].pk,
                'project_name':    g['plan_project'].project.display_name,
                'programme_name':  g['plan_project'].project.programme_name,
                'days_required':   str(g['plan_project'].days_required or ''),
                'assignment_rows': [
                    {
                        'assignment_id': row['assignment'].pk,
                        'display_name':  row['assignment'].display_name,
                        'assignment_type': row['assignment'].assignment_type,
                        'is_interim':    row['assignment'].is_interim,
                        'cells': {
                            str(sprint_pk): {
                                'days':      str(cd['days']),
                                'is_auto':   cd['is_auto'],
                                'is_locked': cd['is_locked'],
                            }
                            for sprint_pk, cd in row['cells'].items()
                        },
                    }
                    for row in g['assignment_rows']
                ],
            }
            for g in s2['project_groups']
        ],
        'totals': {str(k): str(v) for k, v in s2['totals'].items()},
    }


def _serialise_s3(s3: dict) -> dict:
    return {
        'rows': [
            {
                'member_id':   row['member'].pk if row['member'] else None,
                'display_name': row['display_name'],
                'cells': {
                    str(sprint_pk): {
                        'allocated': str(cd['allocated']),
                        'available': str(cd['available']),
                        'remaining': str(cd['remaining']),
                    }
                    for sprint_pk, cd in row['cells'].items()
                },
            }
            for row in s3['rows']
        ],
        'totals': {
            str(sprint_pk): {
                'allocated': str(cd['allocated']),
                'available': str(cd['available']),
                'remaining': str(cd['remaining']),
            }
            for sprint_pk, cd in s3['totals'].items()
        },
    }