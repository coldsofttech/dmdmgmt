from django.views.generic import ListView, View
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.contrib import messages
from django.core.exceptions import ValidationError

from .services import FinancialYearService
from .forms import FinancialYearForm
from .models import FinancialYear


class FinancialYearListView(ListView):
    template_name       = 'financial_years/fy_list.html'
    context_object_name = 'financial_years'

    def get_queryset(self):
        return FinancialYearService.list_financial_years()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs  = self.get_queryset()
        ctx['total_count']  = qs.count()
        ctx['active_fy']    = FinancialYearService.get_active()
 
        # Days remaining in the active FY (clamped to 0 when past end date)
        from datetime import date
        active = ctx['active_fy']
        if active and active.end_date:
            remaining = (active.end_date - date.today()).days
            ctx['active_fy_days_remaining'] = max(remaining, 0)
        else:
            ctx['active_fy_days_remaining'] = None
 
        return ctx


class FinancialYearDetailView(View):
    template_name = 'financial_years/fy_detail.html'

    def get(self, request, pk):
        fy = FinancialYearService.get_financial_year(pk)
        return render(request, self.template_name, {'fy': fy})


class FinancialYearCreateView(View):
    template_name = 'financial_years/fy_form.html'

    def get(self, request):
        return render(request, self.template_name, {
            'form': FinancialYearForm(),
            'is_create': True,
        })

    def post(self, request):
        form = FinancialYearForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'is_create': True})
        try:
            fy = FinancialYearService.create_financial_year(form.cleaned_data)
            messages.success(request, f'Financial year {fy.long_fy} created successfully.')
            return HttpResponseRedirect(reverse('financial_years:detail', args=[fy.pk]))
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, {'form': form, 'is_create': True})


class FinancialYearUpdateView(View):
    template_name = 'financial_years/fy_form.html'

    def _get_fy(self, pk):
        return FinancialYearService.get_financial_year(pk)

    def get(self, request, pk):
        fy   = self._get_fy(pk)
        form = FinancialYearForm(instance=fy)
        return render(request, self.template_name, {'form': form, 'fy': fy, 'is_create': False})

    def post(self, request, pk):
        fy   = self._get_fy(pk)
        form = FinancialYearForm(request.POST, instance=fy)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'fy': fy, 'is_create': False})
        try:
            updated = FinancialYearService.update_financial_year(pk, form.cleaned_data)
            messages.success(request, f'{updated.long_fy} updated successfully.')
            return HttpResponseRedirect(reverse('financial_years:detail', args=[pk]))
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, {'form': form, 'fy': fy, 'is_create': False})


class FinancialYearSetActiveView(View):
    def post(self, request, pk):
        try:
            fy = FinancialYearService.set_active(pk)
            messages.success(request, f'{fy.long_fy} is now the active financial year.')
            return JsonResponse({
                'ok':       True,
                'long_fy':  fy.long_fy,
                'short_fy': fy.short_fy,
            })
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


class FinancialYearDeleteView(View):
    def post(self, request, pk):
        try:
            FinancialYearService.delete_financial_year(pk)
            return JsonResponse({'ok': True})
        except ValidationError as exc:
            return JsonResponse({'ok': False, 'detail': exc.message}, status=400)
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)


def _apply_errors(form, exc: ValidationError):
    if hasattr(exc, 'message_dict'):
        for field, errs in exc.message_dict.items():
            for err in errs:
                form.add_error(field if field != '__all__' else None, err)
    else:
        form.add_error(None, exc.message)