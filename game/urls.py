from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import path

from .views import (
    RegisterView,
    grid_view,
    level_list,
    mark_game_started,
    reset_level,
    reset_level_for_all_users,
    update_vehicle_position,
)

urlpatterns = [
    # --- Auth ---
    path("register/", RegisterView.as_view(), name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="game/login.html"),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(next_page="login"), name="logout"),
    # --- Levels ---
    path("", level_list, name="level-list"),
    # --- Grid / Game Logic ---
    path("level/<int:level_id>/", grid_view, name="grid"),
    path(
        "update_vehicle_position/<int:vehicle_id>/",
        update_vehicle_position,
        name="update_vehicle_position",
    ),
    path("mark_game_started/<int:level_id>/", mark_game_started, name="mark_game_started"),
    path("reset_level/<int:level_id>/", reset_level, name="reset_level"),
    path(
        "reset_level_all/<int:level_id>/",
        reset_level_for_all_users,
        name="reset_level_all",
    ),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
