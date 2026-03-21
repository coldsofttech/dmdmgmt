from django.views.generic import ListView, DetailView, View
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.core.exceptions import ValidationError
from .services import TeamMemberService
from .forms import TeamMemberForm, MoveTeamForm
from .models import TeamMember


class TeamMemberListView(ListView):
    template_name       = 'team_members/team_member_list.html'
    context_object_name = 'members'

    def get_queryset(self):
        return TeamMemberService.list_members()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs  = self.get_queryset()
        ctx['total_count']    = qs.count()
        ctx['active_count']   = qs.filter(is_active=True).count()
        ctx['employee_count']      = qs.filter(employee_type=TeamMember.EmployeeType.EMPLOYEE).count()
        ctx['contractor_count'] = qs.filter(employee_type=TeamMember.EmployeeType.CONTRACTOR).count()
        from apps.teams.models import Team
        ctx['teams'] = Team.objects.filter(is_active=True).order_by('name')
        ctx['roles'] = TeamMember.Role.choices
        return ctx


class TeamMemberDetailView(DetailView):
    template_name       = 'team_members/team_member_detail.html'
    context_object_name = 'member'

    def get_object(self, queryset=None):
        return TeamMemberService.get_member(self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['history']    = TeamMemberService.get_team_history(self.kwargs['pk'])
        ctx['move_form']  = MoveTeamForm(member=self.get_object())
        return ctx


class TeamMemberCreateView(View):
    template_name = 'team_members/team_member_form.html'

    def _default_holidays(self):
        try:
            from apps.configurations.services import ConfigurationService
            return ConfigurationService.get_int('DEFAULT_HOLIDAYS', fallback=20)
        except Exception:
            return 20

    def get(self, request):
        form = TeamMemberForm(initial={'default_holidays': self._default_holidays()})
        return render(request, self.template_name, {'form': form, 'is_create': True})

    def post(self, request):
        form = TeamMemberForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {'form': form, 'is_create': True})

        cd = form.cleaned_data
        data = {
            'first_name':       cd['first_name'],
            'last_name':        cd['last_name'],
            'display_name':     cd.get('display_name', ''),
            'role':             cd['role'],
            'location':         cd['location'],
            'employee_type':    cd['employee_type'],
            'team_id':          cd['team'].pk if cd.get('team') else None,
            'skill_ids':        [s.pk for s in cd.get('skills', [])],
            'start_date':       cd['start_date'],
            'end_date':         cd.get('end_date'),
            'default_holidays': cd['default_holidays'],
            'is_active':        cd['is_active'],
        }
        try:
            member = TeamMemberService.create_member(data)
            messages.success(request, f'"{member.display_name}" added successfully.')
            return HttpResponseRedirect(reverse('team_members:list'))
        except ValidationError as exc:
            for field, errs in (exc.message_dict if hasattr(exc, 'message_dict') else {}).items():
                for err in errs:
                    form.add_error(field, err)
            return render(request, self.template_name, {'form': form, 'is_create': True})


class TeamMemberUpdateView(View):
    template_name = 'team_members/team_member_form.html'

    def _get_member(self, pk):
        return TeamMemberService.get_member(pk)

    def get(self, request, pk):
        member = self._get_member(pk)
        form   = TeamMemberForm(instance=member)
        return render(request, self.template_name, {
            'form': form, 'member': member, 'is_create': False,
        })

    def post(self, request, pk):
        member = self._get_member(pk)
        form   = TeamMemberForm(request.POST, instance=member)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form, 'member': member, 'is_create': False,
            })

        cd = form.cleaned_data
        data = {
            'first_name':       cd['first_name'],
            'last_name':        cd['last_name'],
            'display_name':     cd.get('display_name', ''),
            'role':             cd['role'],
            'location':         cd['location'],
            'employee_type':    cd['employee_type'],
            'team_id':          cd['team'].pk if cd.get('team') else None,
            'skill_ids':        [s.pk for s in cd.get('skills', [])],
            'start_date':       cd['start_date'],
            'end_date':         cd.get('end_date'),
            'default_holidays': cd['default_holidays'],
            'is_active':        cd['is_active'],
        }
        try:
            updated = TeamMemberService.update_member(pk, data)
            messages.success(request, f'"{updated.display_name}" updated successfully.')
            return HttpResponseRedirect(reverse('team_members:detail', args=[pk]))
        except ValidationError as exc:
            errs = exc.message_dict if hasattr(exc, 'message_dict') else {}
            for field, field_errs in errs.items():
                for err in field_errs:
                    form.add_error(field if field != '__all__' else None, err)
            return render(request, self.template_name, {
                'form': form, 'member': member, 'is_create': False,
            })


class TeamMemberMoveView(View):
    def post(self, request, pk):
        member = TeamMemberService.get_member(pk)
        form   = MoveTeamForm(request.POST, member=member)

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if not form.is_valid():
            if is_ajax:
                return JsonResponse({'ok': False, 'errors': form.errors}, status=400)
            messages.error(request, 'Please correct the errors below.')
            return HttpResponseRedirect(reverse('team_members:detail', args=[pk]))

        cd      = form.cleaned_data
        to_team = cd.get('to_team')
        try:
            updated = TeamMemberService.move_to_team(
                member_id  = pk,
                to_team_id = to_team.pk if to_team else None,
                moved_on   = cd['moved_on'],
                note       = cd.get('note', ''),
            )
        except ValidationError as exc:
            if is_ajax:
                return JsonResponse({'ok': False, 'detail': exc.message}, status=400)
            messages.error(request, exc.message)
            return HttpResponseRedirect(reverse('team_members:detail', args=[pk]))

        team_name = updated.team.name if updated.team else 'No team'
        msg = f'"{updated.display_name}" moved to {team_name}.'
        messages.success(request, msg)

        if is_ajax:
            return JsonResponse({'ok': True, 'team_name': team_name, 'detail': msg})
        return HttpResponseRedirect(reverse('team_members:detail', args=[pk]))