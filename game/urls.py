# game/urls.py
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('', views.level_list, name='level-list'),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path('level/<int:level_id>/', views.grid_view, name='grid'),
    path("update_vehicle_position/<int:vehicle_id>/", views.update_vehicle_position, name="update_vehicle_position"),
    path("mark_game_started/<int:level_id>/", views.mark_game_started, name="mark_game_started"),
    path('reset_level/<int:level_id>/', views.reset_level, name='reset_level'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)