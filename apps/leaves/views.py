from django.views.generic import ListView, View
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.contrib import messages
from django.core.exceptions import ValidationError

from .services import LeaveService
from .forms import LeaveForm
from .models import Leave


def _apply_errors(form, exc: ValidationError):
    if hasattr(exc, 'message_dict'):
        for field, errs in exc.message_dict.items():
            for err in errs:
                form.add_error(field if field != '__all__' else None, err)
    else:
        form.add_error(None, exc.message)


def _get_team_member(pk):
    try:
        from apps.team_members.models import TeamMember
        return TeamMember.objects.get(pk=pk)
    except Exception:
        return None


def _get_fy(pk):
    try:
        from apps.financial_years.models import FinancialYear
        return FinancialYear.objects.get(pk=pk)
    except Exception:
        return None


class LeaveListView(ListView):
    template_name       = 'leaves/leave_list.html'
    context_object_name = 'leaves'
 
    def _params(self):
        g = self.request.GET
        return {
            'search':    g.get('search', '').strip(),
            'fy_pk':     g.get('fy', '').strip(),
            'team_pk':   g.get('team', '').strip(),
            'member_pk': g.get('member', '').strip(),
        }
 
    def get_queryset(self):
        p = self._params()
        return LeaveService.list_leaves(
            financial_year_id = int(p['fy_pk'])     if p['fy_pk']     else None,
            team_member_id    = int(p['member_pk']) if p['member_pk'] else None,
            team_id           = int(p['team_pk'])   if p['team_pk']   else None,
            search            = p['search']         or None,
        )
 
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        p   = self._params()
 
        from apps.financial_years.models import FinancialYear
        from apps.team_members.models    import TeamMember
        from apps.teams.models           import Team
 
        ctx['financial_years']    = FinancialYear.objects.all().order_by('-start_date')
        ctx['teams']              = Team.objects.filter(is_active=True).order_by('name')
        ctx['team_members']       = (
            TeamMember.objects
            .filter(is_active=True)
            .select_related('team')
            .order_by('last_name', 'first_name')
        )
        ctx['search_query']       = p['search']
        ctx['selected_fy_pk']     = p['fy_pk']
        ctx['selected_team_pk']   = p['team_pk']
        ctx['selected_member_pk'] = p['member_pk']
        ctx['total_count']        = self.get_queryset().count()
        ctx['active_fy']          = LeaveService.get_active_fy()
        return ctx


class LeaveDetailView(View):
    template_name = 'leaves/leave_detail.html'
 
    def get(self, request, pk):
        leave = LeaveService.get_leave(pk)
        other_leaves = LeaveService.list_leaves(
            team_member_id    = leave.team_member_id,
            financial_year_id = leave.financial_year_id,
        )
        return render(request, self.template_name, {
            'leave':        leave,
            'other_leaves': other_leaves,
        })


class LeaveCreateView(View):
    template_name = 'leaves/leave_form.html'
 
    def _get_locks(self, request):
        member_pk = request.GET.get('member') or request.POST.get('_member_pk', '').strip()
        fy_pk     = request.GET.get('fy')     or request.POST.get('_fy_pk', '').strip()
        locked_member = _get_team_member(member_pk) if member_pk else None
        locked_fy     = _get_fy(fy_pk)               if fy_pk     else None
        return locked_member, locked_fy
 
    def _ctx(self, form, locked_member=None, locked_fy=None):
        return {
            'form':          form,
            'is_create':     True,
            'locked_member': locked_member,
            'locked_fy':     locked_fy,
        }
 
    def get(self, request):
        locked_member, locked_fy = self._get_locks(request)
        form = LeaveForm(team_member=locked_member, financial_year=locked_fy)
        return render(request, self.template_name,
                      self._ctx(form, locked_member, locked_fy))
 
    def post(self, request):
        locked_member, locked_fy = self._get_locks(request)
        form = LeaveForm(request.POST,
                         team_member=locked_member,
                         financial_year=locked_fy)
        if not form.is_valid():
            return render(request, self.template_name,
                          self._ctx(form, locked_member, locked_fy))
        try:
            cd    = form.cleaned_data
            leave = LeaveService.create_leave({
                'team_member_id':    cd['team_member'].pk,
                'financial_year_id': cd['financial_year'].pk,
                'start_date':        cd['start_date'],
                'end_date':          cd['end_date'],
                'note':              '',
            })
            messages.success(request, f'Leave "{leave}" added.')
            if locked_member:
                return HttpResponseRedirect(
                    reverse('team_members:detail', args=[locked_member.pk])
                )
            return HttpResponseRedirect(reverse('leaves:list'))
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name,
                          self._ctx(form, locked_member, locked_fy))


class LeaveUpdateView(View):
    template_name = 'leaves/leave_form.html'
 
    def get(self, request, pk):
        leave = LeaveService.get_leave(pk)
        form  = LeaveForm(instance=leave)
        return render(request, self.template_name, {
            'form': form, 'leave': leave, 'is_create': False,
        })
 
    def post(self, request, pk):
        leave = LeaveService.get_leave(pk)
        form  = LeaveForm(request.POST, instance=leave)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form, 'leave': leave, 'is_create': False,
            })
        try:
            cd      = form.cleaned_data
            updated = LeaveService.update_leave(pk, {
                'team_member_id':    cd['team_member'].pk,
                'financial_year_id': cd['financial_year'].pk,
                'start_date':        cd['start_date'],
                'end_date':          cd['end_date'],
            })
            messages.success(request, f'Leave "{updated}" updated.')
            return HttpResponseRedirect(
                reverse('team_members:detail', args=[updated.team_member_id])
            )
        except ValidationError as exc:
            _apply_errors(form, exc)
            return render(request, self.template_name, {
                'form': form, 'leave': leave, 'is_create': False,
            })


class LeaveDeleteView(View):
    def post(self, request, pk):
        try:
            leave     = LeaveService.get_leave(pk)
            member_pk = leave.team_member_id
            LeaveService.delete_leave(pk)
            return JsonResponse({'ok': True, 'member_pk': member_pk})
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=400)

        
class HolidayDatesApiView(View):
    def get(self, request):
        fy_pk = request.GET.get('fy', '').strip()
        if not fy_pk:
            return JsonResponse({'holiday_dates': []})
        try:
            dates = LeaveService.get_holiday_dates_for_fy(int(fy_pk))
            return JsonResponse({
                'holiday_dates': [d.isoformat() for d in dates]
            })
        except (ValueError, TypeError):
            return JsonResponse({'holiday_dates': []})