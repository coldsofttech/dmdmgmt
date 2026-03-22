from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum, Q

from .models import Budget


class BudgetService:
    @staticmethod
    def list_budgets(financial_year_id: int = None, programme: str = None,
                     project_id: int = None, search: str = None):
        qs = (
            Budget.objects
            .select_related(
                'project', 'project__assigned_team', 'financial_year'
            )
            .all()
        )
        if financial_year_id:
            qs = qs.filter(financial_year_id=financial_year_id)
        if project_id:
            qs = qs.filter(project_id=project_id)
        if programme:
            qs = qs.filter(project__programme_name__iexact=programme)
        if search:
            qs = qs.filter(
                Q(project__project_name__icontains=search) |
                Q(project__programme_name__icontains=search) |
                Q(project__project_code__icontains=search)
            )
        return qs

    @staticmethod
    def get_budget(budget_id: int) -> Budget:
        return Budget.objects.select_related(
            'project', 'project__assigned_team', 'financial_year'
        ).get(pk=budget_id)

    @staticmethod
    def get_for_project_fy(project_id: int, financial_year_id: int):
        try:
            return Budget.objects.select_related(
                'project', 'financial_year'
            ).get(project_id=project_id, financial_year_id=financial_year_id)
        except Budget.DoesNotExist:
            return None

    @staticmethod
    def get_active_fy():
        try:
            from apps.financial_years.models import FinancialYear
            return FinancialYear.objects.filter(is_active=True).first()
        except Exception:
            return None

    @staticmethod
    def programme_summary(financial_year_id: int = None):
        qs = BudgetService.list_budgets(financial_year_id=financial_year_id)

        # Group rows by programme in Python so we can use the active_budget property.
        from collections import defaultdict
        groups = defaultdict(list)
        for b in qs:
            key = b.project.programme_name or '(No Programme)'
            groups[key].append(b)

        result = []
        for programme in sorted(groups.keys()):
            rows = groups[programme]
            # Sum active_budget (refined_budget if set, else budget_allocated)
            allocated_vals   = [b.active_budget   for b in rows if b.active_budget   is not None]
            estimates_vals   = [b.estimates        for b in rows if b.estimates        is not None]
            remaining_vals   = [b.remaining_budget for b in rows if b.remaining_budget is not None]

            from decimal import Decimal
            result.append({
                'programme':       programme,
                'project_count':   len(rows),
                'total_allocated': sum(allocated_vals,  Decimal('0')) if allocated_vals  else None,
                'total_estimates': sum(estimates_vals,  Decimal('0')) if estimates_vals  else None,
                'total_remaining': sum(remaining_vals,  Decimal('0')) if remaining_vals  else None,
                'budgets':         rows,
            })

        return result

    @staticmethod
    def fy_total_allocated(financial_year_id: int):
        from django.db.models import Sum
        result = Budget.objects.filter(
            financial_year_id=financial_year_id,
            budget_allocated__isnull=False,
        ).aggregate(total=Sum('budget_allocated'))
        return result['total']

    @staticmethod
    @transaction.atomic
    def ensure_budget_for_project(project_id: int, financial_year_id: int) -> Budget:
        from decimal import Decimal
        budget, _ = Budget.objects.get_or_create(
            project_id=project_id,
            financial_year_id=financial_year_id,
            defaults={
                'budget_allocated': Decimal('0'),  # seeded as £0.00 — edit to set real value
                'refined_budget':   None,
                'notes':            '',
            },
        )
        # Always refresh the estimate snapshot
        budget._refresh_estimates()
        budget._calc_remaining()
        budget.save(update_fields=['estimates', 'remaining_budget', 'updated_at'])
        return budget

    @staticmethod
    def seed_for_all_projects(financial_year_id: int) -> int:
        from apps.projects.models import Project
        projects = Project.objects.all()
        created = 0
        for project in projects:
            _, was_created = Budget.objects.get_or_create(
                project_id=project.pk,
                financial_year_id=financial_year_id,
                defaults={'budget_allocated': None, 'refined_budget': None},
            )
            if was_created:
                created += 1
        return created

    @staticmethod
    @transaction.atomic
    def create_budget(data: dict) -> Budget:
        budget = Budget(
            project_id        = data['project_id'],
            financial_year_id = data['financial_year_id'],
            budget_allocated  = data.get('budget_allocated'),
            refined_budget    = data.get('refined_budget'),
            notes             = data.get('notes', '').strip(),
        )
        budget.full_clean()
        budget.save()
        return budget

    @staticmethod
    @transaction.atomic
    def update_budget(budget_id: int, data: dict) -> Budget:
        budget = Budget.objects.get(pk=budget_id)
        if 'budget_allocated' in data: budget.budget_allocated = data['budget_allocated']
        if 'refined_budget'   in data: budget.refined_budget   = data['refined_budget']
        if 'notes'            in data: budget.notes            = data['notes'].strip()
        budget.full_clean()
        budget.save()
        return budget

    @staticmethod
    def delete_budget(budget_id: int) -> None:
        Budget.objects.get(pk=budget_id).delete()

    @staticmethod
    @transaction.atomic
    def refresh_estimates_for_project(project_id: int):
        for budget in Budget.objects.filter(project_id=project_id):
            budget.save()  # triggers _refresh_estimates() + _calc_remaining()