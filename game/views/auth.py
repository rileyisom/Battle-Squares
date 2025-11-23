from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views.generic import FormView

from ..forms import SimpleUserCreationForm


# AUTHENTICATION
class RegisterView(FormView):
    template_name = "game/register.html"
    form_class = SimpleUserCreationForm
    success_url = reverse_lazy("level-list")

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)  # Log user in automatically
        return super().form_valid(form)
