import datetime
from django.views.generic import ListView, View
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.contrib import messages
from django.core.exceptions import ValidationError

from .services import SprintService
from .forms import SprintGenerateForm, SprintForm
from .models import Sprint


def _apply_errors(form, exc):
    if hasattr(exc, 'message_dict'):
        for field, errs in exc.message_dict.items():
            for err in errs:
                form.add_error(field if field != '__all__' else None, err)
    elif hasattr(exc, 'message'):
        form.add_error(None, exc.message)
    else:
        form.add_error(None, str(exc))


class SprintListView(ListView):
    template_name       = 'sprints/sprint_list.html'
    context_object_name = 'sprints'

    def _selected_fy(self):
        fy_pk = self.request.GET.get('fy', '').strip()
        if fy_pk:
            try:
                from apps.financial_years.models import FinancialYear
                return FinancialYear.objects.get(pk=fy_pk)
            except Exception:
                pass
        return SprintService.get_active_fy()

    def get_queryset(self):
        fy = self._selected_fy()
        if not fy:
            return Sprint.objects.none()
        return SprintService.list_sprints(financial_year_id=fy.pk)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.financial_years.models import FinancialYear

        selected_fy = self._selected_fy()
        ctx['selected_fy']     = selected_fy
        ctx['financial_years'] = FinancialYear.objects.all().order_by('-start_date')
        ctx['active_fy']       = SprintService.get_active_fy()
        ctx['generate_form']   = SprintGenerateForm(
            initial={'financial_year': selected_fy} if selected_fy else {}
        )

        try:
            from apps.configurations.services import ConfigurationService
            ctx['sprint_duration']     = ConfigurationService.get_int('SPRINT_DURATION_DAYS', fallback=10)
            ctx['sprint_start_number'] = ConfigurationService.get_int('SPRINT_START_NUMBER', fallback=1)
        except Exception:
            ctx['sprint_duration']     = 10
            ctx['sprint_start_number'] = 1

        # Capacity per sprint (dict keyed by sprint.pk)
        sprints    = ctx['sprints']
        capacities = {s.pk: SprintService.sprint_capacity(s) for s in sprints}
        ctx['capacities'] = capacities

        # Consistency warnings
        if selected_fy:
            ctx['warnings']          = SprintService.check_consistency(selected_fy.pk)
            ctx['warned_sprint_ids'] = {w['sprint_id'] for w in ctx['warnings']}
        else:
            ctx['warnings']          = []
            ctx['warned_sprint_ids'] = set()

        ctx['total_count'] = len(sprints) if hasattr(sprints, '__len__') else sprints.count()

        return ctx

    def post(self, request):
        form = SprintGenerateForm(request.POST)
        if not form.is_valid():
            from apps.financial_years.models import FinancialYear
            return render(request, self.template_name, {
                'sprints':            Sprint.objects.none(),
                'generate_form':      form,
                'financial_years':    FinancialYear.objects.all().order_by('-start_date'),
                'active_fy':          SprintService.get_active_fy(),
                'capacities':         {},
                'warnings':           [],
                'warned_sprint_ids':  set(),
                'total_count':        0,
                'sprint_duration':    10,
                'sprint_start_number': 1,
            })
        try:
            cd      = form.cleaned_data
            sprints = SprintService.generate_sprints(
                financial_year_id=cd['financial_year'].pk,
            )
            messages.success(
                request,
                f'{len(sprints)} sprints generated for {cd["financial_year"].long_fy}.'
            )
            return HttpResponseRedirect(
                reverse('sprints:list') + f'?fy={cd["financial_year"].pk}'
            )
        except ValidationError as exc:
            msg = exc.message if hasattr(exc, 'message') else str(exc)
            messages.error(request, msg)
            return HttpResponseRedirect(reverse('sprints:list'))


class SprintDetailView(View):
    template_name = 'sprints/sprint_detail.html'

    def get(self, request, pk):
        sprint   = SprintService.get_sprint(pk)
        capacity = SprintService.sprint_capacity(sprint)
        return render(request, self.template_name, {
            'sprint':   sprint,
            'capacity': capacity,
        })


class SprintCreateView(View):
    template_name = 'sprints/sprint_form.html'

    def get(self, request):
        fy_pk   = request.GET.get('fy', '').strip()
        initial = {}
        if fy_pk:
            try:
                from apps.financial_years.models import FinancialYear
                initial['financial_year'] = FinancialYear.objects.get(pk=fy_pk)
            except Exception:
                pass
        return render(request, self.template_name, {
            'form': SprintForm(initial=initial), 'is_create': True,
        })

    def post(self, request):
        form = SprintForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'is_create': True})
        try:
            cd     = form.cleaned_data
            sprint = SprintService.create_sprint({
                'financial_year_id': cd['financial_year'].pk,
                'sprint_number':     cd['sprint_number'],
                'name':              cd['name'],
                'start_date':        cd['start_date'],
                'end_date':          cd['end_date'],
                'notes':             cd.get('notes', ''),
            })
            messages.success(request, f'"{sprint.name}" created.')
            return HttpResponseRedirect(
                reverse('sprints:list') + f'?fy={sprint.financial_year_id}'
            )
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, {'form': form, 'is_create': True})


class SprintUpdateView(View):
    template_name = 'sprints/sprint_form.html'

    def get(self, request, pk):
        sprint = SprintService.get_sprint(pk)
        return render(request, self.template_name, {
            'form': SprintForm(instance=sprint), 'sprint': sprint, 'is_create': False,
        })

    def post(self, request, pk):
        sprint = SprintService.get_sprint(pk)
        form   = SprintForm(request.POST, instance=sprint)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form, 'sprint': sprint, 'is_create': False,
            })
        try:
            cd      = form.cleaned_data
            updated = SprintService.update_sprint(pk, {
                'sprint_number': cd['sprint_number'],
                'name':          cd['name'],
                'start_date':    cd['start_date'],
                'end_date':      cd['end_date'],
                'notes':         cd.get('notes', ''),
            })
            messages.success(request, f'"{updated.name}" updated.')
            return HttpResponseRedirect(
                reverse('sprints:list') + f'?fy={updated.financial_year_id}'
            )
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, {
                'form': form, 'sprint': sprint, 'is_create': False,
            })


class SprintDeleteView(View):
    def post(self, request, pk):
        try:
            sprint = SprintService.get_sprint(pk)
            fy_pk  = sprint.financial_year_id
            SprintService.delete_sprint(pk)
            return JsonResponse({'ok': True, 'fy_pk': fy_pk})
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


class SprintDeleteFYView(View):
    def post(self, request):
        fy_pk = request.POST.get('fy', '').strip()
        if not fy_pk:
            return JsonResponse({'ok': False, 'detail': '"fy" is required.'}, status=400)
        try:
            deleted = SprintService.delete_all_for_fy(int(fy_pk))
            return JsonResponse({'ok': True, 'deleted': deleted})
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)