from django.views.generic import ListView, View
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.core.exceptions import ValidationError

from .services import HolidayService
from .forms import HolidayForm
from .models import Holiday


def _apply_errors(form, exc: ValidationError):
    if hasattr(exc, 'message_dict'):
        for field, errs in exc.message_dict.items():
            for err in errs:
                form.add_error(field if field != '__all__' else None, err)
    else:
        form.add_error(None, exc.message)

def _get_fy(pk):
    try:
        from apps.financial_years.models import FinancialYear
        return FinancialYear.objects.get(pk=pk)
    except Exception:
        return None


class HolidayListView(ListView):
    template_name       = 'holidays/holiday_list.html'
    context_object_name = 'holidays'
 
    def get_queryset(self):
        fy_pk = self.request.GET.get('fy')
        return HolidayService.list_holidays(
            financial_year_id=int(fy_pk) if fy_pk else None
        )
 
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from apps.financial_years.models import FinancialYear
        ctx['financial_years'] = FinancialYear.objects.all().order_by('-start_date')
        ctx['selected_fy_pk']  = self.request.GET.get('fy', '')
        ctx['total_count']     = self.get_queryset().count()
        return ctx


class HolidayCreateView(View):
    template_name = 'holidays/holiday_form.html'
 
    def get(self, request):
        fy_pk     = request.GET.get('fy')
        locked_fy = _get_fy(fy_pk) if fy_pk else None
        form      = HolidayForm(financial_year=locked_fy)
        return render(request, self.template_name, {
            'form':      form,
            'is_create': True,
            'locked_fy': locked_fy,
        })
 
    def post(self, request):
        # ── Read the locked FY pk from the hidden field _fy_pk ──────────────
        # We use a dedicated hidden field name (_fy_pk) rather than _locked_fy
        # to avoid any ambiguity.  The template sets this field's value from
        # locked_fy.pk when the FY is pre-locked.
        fy_pk     = request.POST.get('_fy_pk', '').strip()
        locked_fy = _get_fy(fy_pk) if fy_pk else None
 
        form = HolidayForm(request.POST, financial_year=locked_fy)
 
        if not form.is_valid():
            return render(request, self.template_name, {
                'form':      form,
                'is_create': True,
                'locked_fy': locked_fy,
            })
 
        try:
            cd      = form.cleaned_data
            holiday = HolidayService.create_holiday({
                'financial_year_id': cd['financial_year'].pk,
                'holiday_date':      cd['holiday_date'],
                'note':              cd.get('note', ''),
            })
            messages.success(request, f'Holiday "{holiday}" added.')
            if locked_fy:
                return HttpResponseRedirect(
                    reverse('financial_years:detail', args=[locked_fy.pk])
                )
            return HttpResponseRedirect(reverse('holidays:list'))
 
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, {
                'form':      form,
                'is_create': True,
                'locked_fy': locked_fy,
            })


class HolidayUpdateView(View):
    template_name = 'holidays/holiday_form.html'
 
    def get(self, request, pk):
        holiday = HolidayService.get_holiday(pk)
        form    = HolidayForm(instance=holiday)
        return render(request, self.template_name, {
            'form':      form,
            'holiday':   holiday,
            'is_create': False,
        })
 
    def post(self, request, pk):
        holiday = HolidayService.get_holiday(pk)
        form    = HolidayForm(request.POST, instance=holiday)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form':      form,
                'holiday':   holiday,
                'is_create': False,
            })
        try:
            cd      = form.cleaned_data
            updated = HolidayService.update_holiday(pk, {
                'financial_year_id': cd['financial_year'].pk,
                'holiday_date':      cd['holiday_date'],
                'note':              cd.get('note', ''),
            })
            messages.success(request, f'Holiday "{updated}" updated.')
            return HttpResponseRedirect(
                reverse('financial_years:detail', args=[updated.financial_year_id])
            )
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, {
                'form':      form,
                'holiday':   holiday,
                'is_create': False,
            })


class HolidayDeleteView(View):
    def post(self, request, pk):
        try:
            holiday = HolidayService.get_holiday(pk)
            fy_pk   = holiday.financial_year_id
            HolidayService.delete_holiday(pk)
            return JsonResponse({'ok': True, 'fy_pk': fy_pk})
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)
        
        
class HolidayDetailView(View):
    template_name = 'holidays/holiday_detail.html'
 
    def get(self, request, pk):
        holiday        = HolidayService.get_holiday(pk)
        other_holidays = HolidayService.list_holidays(
            financial_year_id=holiday.financial_year_id
        )
        return render(request, self.template_name, {
            'holiday':        holiday,
            'other_holidays': other_holidays,
        })