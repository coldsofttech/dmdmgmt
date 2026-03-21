from django.shortcuts import render
from django.views.generic import ListView, CreateView, UpdateView, DetailView, View
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import ValidationError

from .models import Team
from .services import TeamService
from .forms import TeamForm

class TeamListView(ListView):
    template_name = 'teams/team_list.html'
    context_object_name = 'teams'

    def get_queryset(self):
        return TeamService.list_teams()
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs  = self.get_queryset()
        ctx['active_count']   = qs.filter(is_active=True).count()

        try:
            from apps.team_members.models import TeamMember
            from django.db.models import Count
            counts_qs = (
                TeamMember.objects
                .values('team_id')
                .annotate(cnt=Count('id'))
            )
            member_counts = {row['team_id']: row['cnt'] for row in counts_qs}
            ctx['member_counts']      = member_counts
            ctx['total_members']      = TeamMember.objects.count()
            ctx['unassigned_members'] = TeamMember.objects.filter(team__isnull=True).count()
        except Exception:
            ctx['member_counts']      = {}
            ctx['total_members']      = 0
            ctx['unassigned_members'] = 0

        return ctx

# class TeamCreateView(CreateView):
#     template_name = 'teams/team_form.html'
#     form_class    = TeamForm
#     # success_url   = reverse_lazy('teams:list')

#     def form_valid(self, form):
#         try:
#             team = TeamService.create_team(form.cleaned_data)
#             messages.success(self.request, f'Team "{team.name}" created successfully.')
#             return HttpResponseRedirect(reverse_lazy('teams:list'))
#         except ValidationError as exc:
#             form.add_error('team', exc.message)
#             return self.form_invalid(form)
#         # TeamService.create_team(form.cleaned_data)
#         # messages.success(self.request, f'Team "{form.cleaned_data["name"]}" created.')
#         # return super().form_valid(form)

#     def form_invalid(self, form):
#         return self.render_to_response(self.get_context_data(form=form))
    
#     def get_context_data(self, **kwargs):
#         ctx = super().get_context_data(**kwargs)
#         return ctx

class TeamCreateView(View):
    template_name = 'teams/team_form.html'
 
    def get(self, request):
        from django.shortcuts import render
        return render(request, self.template_name, {
            'form': TeamForm(),
        })
 
    def post(self, request):
        from django.shortcuts import render
        form = TeamForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
            })
        try:
            team = TeamService.create_team(form.cleaned_data)
            messages.success(request, f'Team "{team.name}" created successfully.')
            return HttpResponseRedirect(reverse_lazy('teams:list'))
        except ValidationError as exc:
            form.add_error('name', exc.message)
            return render(request, self.template_name, {
                'form': form,
            })

# class TeamUpdateView(UpdateView):
#     template_name = 'teams/team_form.html'
#     form_class    = TeamForm
#     # success_url   = reverse_lazy('teams:list')

#     def get_object(self):
#         return TeamService.get_team(self.kwargs['pk'])
    
#     def get_context_data(self, **kwargs):
#         ctx = super().get_context_data(**kwargs)
#         return ctx

#     def form_valid(self, form):
#         try:
#             team = TeamService.update_team(self.kwargs['pk'], form.cleaned_data)
#             messages.success(self.request, f'Team "{team.name}" updated successfully.')
#             return HttpResponseRedirect(reverse_lazy('teams:list'))
#         except ValidationError as exc:
#             form.add_error('team', exc.message)
#             return self.form_invalid(form)
#         # TeamService.update_team(self.kwargs['pk'], form.cleaned_data)
#         # messages.success(self.request, f'Team "{form.cleaned_data["name"]}" updated.')
#         # return super().form_valid(form)

#     def form_invalid(self, form):
#         return self.render_to_response(self.get_context_data(form=form))

class TeamUpdateView(View):
    template_name = 'teams/team_form.html'
 
    def _get_team(self, pk):
        return TeamService.get_team(pk)
 
    def get(self, request, pk):
        from django.shortcuts import render
        team = self._get_team(pk)
        return render(request, self.template_name, {
            'form': TeamForm(instance=team),
        })
 
    def post(self, request, pk):
        from django.shortcuts import render
        team = self._get_team(pk)
        form = TeamForm(request.POST, instance=team)
        if not form.is_valid():
            return render(request, self.template_name, {
                'form': form,
            })
        try:
            updated = TeamService.update_team(pk, form.cleaned_data)
            messages.success(request, f'Team "{updated.name}" updated successfully.')
            return HttpResponseRedirect(reverse_lazy('teams:list'))
        except ValidationError as exc:
            form.add_error(None, exc.message)
            return render(request, self.template_name, {
                'form': form,
            })
    
# class TeamDetailView(DetailView):
#     template_name       = 'teams/team_detail.html'
#     context_object_name = 'team'

#     def get_object(self, queryset=None):
#         return TeamService.get_team(self.kwargs['pk'])

class TeamDetailView(DetailView):
    template_name       = 'teams/team_detail.html'
    context_object_name = 'team'
 
    def get_object(self, queryset=None):
        return TeamService.get_team(self.kwargs['pk'])
 
    def get_context_data(self, **kwargs):
        ctx  = super().get_context_data(**kwargs)
        team = self.get_object()
 
        try:
            from apps.team_members.models import TeamMember
            members_qs = (
                TeamMember.objects
                .filter(team=team)
                .prefetch_related('skills')
                .order_by('last_name', 'first_name')
            )
            ctx['team_members']        = members_qs
            ctx['member_count']        = members_qs.count()
            ctx['active_member_count'] = members_qs.filter(is_active=True).count()
        except Exception:
            ctx['team_members']        = []
            ctx['member_count']        = 0
            ctx['active_member_count'] = 0
 
        return ctx