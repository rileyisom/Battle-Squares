from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from ..models import Level


@login_required(login_url="/login/")
def level_list(request):
    levels = Level.objects.all()
    return render(request, "game/levels.html", {"levels": levels})
