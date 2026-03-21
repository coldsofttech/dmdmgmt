from django.shortcuts import render
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import ValidationError
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
        return ctx

class TeamCreateView(CreateView):
    template_name = 'teams/team_form.html'
    form_class    = TeamForm
    # success_url   = reverse_lazy('teams:list')

    def form_valid(self, form):
        try:
            team = TeamService.create_team(form.cleaned_data)
            messages.success(self.request, f'Team "{team.name}" created successfully.')
            return HttpResponseRedirect(reverse_lazy('teams:list'))
        except ValidationError as exc:
            form.add_error('team', exc.message)
            return self.form_invalid(form)
        # TeamService.create_team(form.cleaned_data)
        # messages.success(self.request, f'Team "{form.cleaned_data["name"]}" created.')
        # return super().form_valid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx

class TeamUpdateView(UpdateView):
    template_name = 'teams/team_form.html'
    form_class    = TeamForm
    # success_url   = reverse_lazy('teams:list')

    def get_object(self):
        return TeamService.get_team(self.kwargs['pk'])
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx

    def form_valid(self, form):
        try:
            team = TeamService.update_team(self.kwargs['pk'], form.cleaned_data)
            messages.success(self.request, f'Team "{team.name}" updated successfully.')
            return HttpResponseRedirect(reverse_lazy('teams:list'))
        except ValidationError as exc:
            form.add_error('team', exc.message)
            return self.form_invalid(form)
        # TeamService.update_team(self.kwargs['pk'], form.cleaned_data)
        # messages.success(self.request, f'Team "{form.cleaned_data["name"]}" updated.')
        # return super().form_valid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))
    
class TeamDetailView(DetailView):
    template_name       = 'teams/team_detail.html'
    context_object_name = 'team'

    def get_object(self, queryset=None):
        return TeamService.get_team(self.kwargs['pk'])
