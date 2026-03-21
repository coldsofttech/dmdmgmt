from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import ValidationError
from .services import SkillService
from .forms import SkillForm


class SkillListView(ListView):
    template_name       = 'skills/skill_list.html'
    context_object_name = 'skills'

    def get_queryset(self):
        return SkillService.list_skills()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs  = self.get_queryset()
        ctx['active_count']   = qs.filter(is_active=True).count()
        ctx['inactive_count'] = qs.filter(is_active=False).count()
        ctx['total_count']    = qs.count()
        return ctx


class SkillDetailView(DetailView):
    template_name       = 'skills/skill_detail.html'
    context_object_name = 'skill'

    def get_object(self, queryset=None):
        return SkillService.get_skill(self.kwargs['pk'])


class SkillCreateView(CreateView):
    template_name = 'skills/skill_form.html'
    form_class    = SkillForm

    def form_valid(self, form):
        try:
            skill = SkillService.create_skill(form.cleaned_data)
            messages.success(self.request, f'Skill "{skill.skill}" created successfully.')
            return HttpResponseRedirect(reverse_lazy('skills:list'))
        except ValidationError as exc:
            form.add_error('skill', exc.message)
            return self.form_invalid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx


class SkillUpdateView(UpdateView):
    template_name = 'skills/skill_form.html'
    form_class    = SkillForm

    def get_object(self, queryset=None):
        return SkillService.get_skill(self.kwargs['pk'])
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        return ctx

    def form_valid(self, form):
        try:
            skill = SkillService.update_skill(self.kwargs['pk'], form.cleaned_data)
            messages.success(self.request, f'Skill "{skill.skill}" updated successfully.')
            return HttpResponseRedirect(reverse_lazy('skills:list'))
        except ValidationError as exc:
            form.add_error('skill', exc.message)
            return self.form_invalid(form)

    def form_invalid(self, form):
        return self.render_to_response(self.get_context_data(form=form))
