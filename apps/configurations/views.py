from django.views.generic import ListView, DetailView, CreateView, UpdateView, View
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import ValidationError
from .services import ConfigurationService
from .forms import ConfigurationValueForm


class ConfigurationListView(ListView):
    template_name       = 'configurations/config_list.html'
    context_object_name = 'configs'

    def get_queryset(self):
        return ConfigurationService.list_configs()

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs  = self.get_queryset()
        ctx['total_count'] = qs.count()
        return ctx


class ConfigurationDetailView(DetailView):
    template_name       = 'configurations/config_detail.html'
    context_object_name = 'config'

    def get_object(self, queryset=None):
        return ConfigurationService.get_config(self.kwargs['pk'])

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        config = self.get_object()
        ctx['default_value'] = ConfigurationService.get_default_value(config.code)
        ctx['is_overridden'] = (
            ctx['default_value'] is not None
            and config.value != ctx['default_value']
        )
        return ctx


# class ConfigurationCreateView(CreateView):
#     template_name = 'configurations/config_form.html'
#     form_class    = ConfigurationForm

#     def form_valid(self, form):
#         try:
#             config = ConfigurationService.create_config(form.cleaned_data)
#             messages.success(
#                 self.request,
#                 f'Configuration "{config.code}" created successfully.',
#             )
#             return HttpResponseRedirect(reverse_lazy('configurations:list'))
#         except ValidationError as exc:
#             form.add_error('code', exc.message)
#             return self.form_invalid(form)

#     def form_invalid(self, form):
#         return self.render_to_response(self.get_context_data(form=form))
    
#     def get_context_data(self, **kwargs):
#         ctx = super().get_context_data(**kwargs)
#         return ctx


# class ConfigurationUpdateView(UpdateView):
#     template_name = 'configurations/config_form.html'
#     form_class    = ConfigurationForm

#     def get_object(self, queryset=None):
#         return ConfigurationService.get_config(self.kwargs['pk'])
    
#     def get_context_data(self, **kwargs):
#         ctx = super().get_context_data(**kwargs)
#         return ctx

#     def form_valid(self, form):
#         try:
#             data = {
#                 'value':       form.cleaned_data.get('value', ''),
#             }
#             config = ConfigurationService.update_config(self.kwargs['pk'], data)
#             messages.success(
#                 self.request,
#                 f'Configuration "{config.code}" updated successfully.',
#             )
#             return HttpResponseRedirect(reverse_lazy('configurations:list'))
#         except ValidationError as exc:
#             form.add_error(None, exc.message)
#             return self.form_invalid(form)

#     def form_invalid(self, form):
#         return self.render_to_response(self.get_context_data(form=form))

class ConfigurationUpdateView(View):
    template_name = 'configurations/config_form.html'
 
    def _get_config(self):
        return ConfigurationService.get_config(self.kwargs['pk'])
 
    def get(self, request, pk):
        config = self._get_config()
        form   = ConfigurationValueForm(initial={'value': config.value})
        return self._render(request, config, form)
 
    def post(self, request, pk):
        config = self._get_config()
        form   = ConfigurationValueForm(request.POST)
 
        if not form.is_valid():
            return self._render(request, config, form)
 
        try:
            ConfigurationService.update_config(pk, form.cleaned_data['value'])
            messages.success(
                request,
                f'Configuration "{config.code}" updated successfully.',
            )
            return HttpResponseRedirect(reverse_lazy('configurations:list'))
        except ValidationError as exc:
            form.add_error('value', exc.message)
            return self._render(request, config, form)
 
    def _render(self, request, config, form):
        from django.shortcuts import render
        default_value = ConfigurationService.get_default_value(config.code)
        return render(request, self.template_name, {
            'config':        config,
            'form':          form,
            'default_value': default_value,
            'is_overridden': (
                default_value is not None and config.value != default_value
            ),
        })
 
 
class ConfigurationResetView(View):
    def post(self, request, pk):
        try:
            config = ConfigurationService.reset_to_default(pk)
            messages.success(
                request,
                f'"{config.code}" has been reset to its default value ({config.value}).',
            )
            return JsonResponse({
                'ok':           True,
                'code':         config.code,
                'value':        config.value,
                'updated_at':   config.updated_at.strftime('%d %b %Y, %H:%M'),
            })
        except ValidationError as exc:
            return JsonResponse({'ok': False, 'detail': exc.message}, status=400)
        except Exception as exc:
            return JsonResponse({'ok': False, 'detail': str(exc)}, status=500)