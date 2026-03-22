from django.views.generic import ListView, View
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.contrib import messages
from django.core.exceptions import ValidationError

from .services import BudgetService
from .forms import BudgetForm
from .models import Budget


def _apply_errors(form, exc):
    if hasattr(exc, 'message_dict'):
        for field, errs in exc.message_dict.items():
            for err in errs:
                form.add_error(field if field != '__all__' else None, err)
    else:
        form.add_error(None, exc.message)


def _get_project(pk):
    try:
        from apps.projects.models import Project
        return Project.objects.get(pk=pk)
    except Exception:
        return None


def _get_fy(pk):
    try:
        from apps.financial_years.models import FinancialYear
        return FinancialYear.objects.get(pk=pk)
    except Exception:
        return None


class BudgetListView(ListView):
    template_name       = 'budgets/budget_list.html'
    context_object_name = 'budgets'

    def get_queryset(self):
        fy_pk  = self.request.GET.get('fy', '').strip()
        search = self.request.GET.get('search', '').strip()
        return BudgetService.list_budgets(
            financial_year_id = int(fy_pk) if fy_pk else None,
            search            = search     or None,
        )

    def get_context_data(self, **kwargs):
        ctx   = super().get_context_data(**kwargs)
        fy_pk = self.request.GET.get('fy', '').strip()

        from apps.financial_years.models import FinancialYear
        ctx['financial_years']  = FinancialYear.objects.all().order_by('-start_date')
        ctx['selected_fy_pk']   = fy_pk
        ctx['search_query']     = self.request.GET.get('search', '')
        ctx['active_fy']        = BudgetService.get_active_fy()
        ctx['total_count']      = self.get_queryset().count()
        ctx['view_mode']        = self.request.GET.get('view', 'list')

        # Programme summary (always computed — used by both view modes)
        ctx['programme_summary'] = BudgetService.programme_summary(
            financial_year_id=int(fy_pk) if fy_pk else None
        )

        # Total allocated for the active FY — shown in stat card
        active_fy = ctx['active_fy']
        if active_fy:
            ctx['fy_total_allocated'] = BudgetService.fy_total_allocated(active_fy.pk)
        else:
            ctx['fy_total_allocated'] = None

        return ctx


class BudgetDetailView(View):
    template_name = 'budgets/budget_detail.html'

    def get(self, request, pk):
        budget = BudgetService.get_budget(pk)
        return render(request, self.template_name, {'budget': budget})


class BudgetCreateView(View):
    template_name = 'budgets/budget_form.html'

    def _get_locks(self, request):
        project_pk = request.GET.get('project') or request.POST.get('_project_pk', '').strip()
        fy_pk      = request.GET.get('fy')      or request.POST.get('_fy_pk', '').strip()
        return (
            _get_project(project_pk) if project_pk else None,
            _get_fy(fy_pk)           if fy_pk      else None,
        )

    def _ctx(self, form, locked_project=None, locked_fy=None, is_create=True):
        return {
            'form':           form,
            'is_create':      is_create,
            'locked_project': locked_project,
            'locked_fy':      locked_fy,
        }

    def get(self, request):
        locked_project, locked_fy = self._get_locks(request)
        form = BudgetForm(project=locked_project, financial_year=locked_fy)
        return render(request, self.template_name,
                      self._ctx(form, locked_project, locked_fy))

    def post(self, request):
        locked_project, locked_fy = self._get_locks(request)
        form = BudgetForm(request.POST,
                          project=locked_project,
                          financial_year=locked_fy)
        if not form.is_valid():
            return render(request, self.template_name,
                          self._ctx(form, locked_project, locked_fy))
        try:
            cd     = form.cleaned_data
            budget = BudgetService.create_budget({
                'project_id':        cd['project'].pk,
                'financial_year_id': cd['financial_year'].pk,
                'budget_allocated':  cd.get('budget_allocated'),
                'refined_budget':    cd.get('refined_budget'),
                'notes':             cd.get('notes', ''),
            })
            messages.success(request, f'Budget entry created for "{budget.project}".')
            if locked_project:
                return HttpResponseRedirect(
                    reverse('projects:detail', args=[locked_project.pk])
                )
            return HttpResponseRedirect(reverse('budgets:list'))
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name,
                          self._ctx(form, locked_project, locked_fy))


class BudgetUpdateView(View):
    template_name = 'budgets/budget_form.html'

    def get(self, request, pk):
        budget = BudgetService.get_budget(pk)
        form   = BudgetForm(instance=budget,
                             project=budget.project,
                             financial_year=budget.financial_year)
        return render(request, self.template_name, {
            'form': form, 'budget': budget, 'is_create': False,
            'locked_project': budget.project,
            'locked_fy':      budget.financial_year,
        })

    def post(self, request, pk):
        budget = BudgetService.get_budget(pk)
        form   = BudgetForm(request.POST, instance=budget,
                             project=budget.project,
                             financial_year=budget.financial_year)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form, 'budget': budget, 'is_create': False,
                'locked_project': budget.project,
                'locked_fy':      budget.financial_year,
            })
        try:
            cd      = form.cleaned_data
            updated = BudgetService.update_budget(pk, {
                'budget_allocated': cd.get('budget_allocated'),
                'refined_budget':   cd.get('refined_budget'),
                'notes':            cd.get('notes', ''),
            })
            messages.success(request, f'Budget updated for "{updated.project}".')
            return HttpResponseRedirect(
                reverse('projects:detail', args=[updated.project_id])
            )
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, {
                'form': form, 'budget': budget, 'is_create': False,
                'locked_project': budget.project,
                'locked_fy':      budget.financial_year,
            })


class BudgetDeleteView(View):
    def post(self, request, pk):
        try:
            budget     = BudgetService.get_budget(pk)
            project_pk = budget.project_id
            BudgetService.delete_budget(pk)
            return JsonResponse({'ok': True, 'project_pk': project_pk})
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


class ProgrammeSummaryView(View):
    template_name = 'budgets/programme_summary.html'

    def get(self, request):
        fy_pk = request.GET.get('fy', '').strip()
        from apps.financial_years.models import FinancialYear
        ctx = {
            'financial_years':   FinancialYear.objects.all().order_by('-start_date'),
            'selected_fy_pk':    fy_pk,
            'active_fy':         BudgetService.get_active_fy(),
            'programme_summary': BudgetService.programme_summary(
                financial_year_id=int(fy_pk) if fy_pk else None
            ),
            # All budget rows for detail drill-down on the same page
            'budgets': BudgetService.list_budgets(
                financial_year_id=int(fy_pk) if fy_pk else None
            ),
        }
        return render(request, self.template_name, ctx)