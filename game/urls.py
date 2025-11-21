# game/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views
from .views import RegisterView

urlpatterns = [
    path("", views.level_list, name="level-list"),
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", auth_views.LoginView.as_view(template_name="game/login.html/"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    path("level/<int:level_id>/", views.grid_view, name="grid"),
    path(
        "update_vehicle_position/<int:vehicle_id>/",
        views.update_vehicle_position,
        name="update_vehicle_position",
    ),
    path("mark_game_started/<int:level_id>/", views.mark_game_started, name="mark_game_started"),
    path("reset_level/<int:level_id>/", views.reset_level, name="reset_level"),
    path(
        "reset_level_all/<int:level_id>/", views.reset_level_for_all_users, name="reset_level_all"
    ),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
