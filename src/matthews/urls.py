from django.urls import path
from . import views

app_name = 'matthews'
urlpatterns = [
    path('', views.home, name='home'),
    path('new-game', views.new_game, name='new-game'),
    path('game/<int:id>/invite', views.invite, name='invite'),
    path('game/<int:id>/join/<slug:name>/<slug:hash>', views.join, name='join'),
    path('game', views.game, name='game'),
    path('game/update-options', views.update_options, name='update_options'),
    path('game/state', views.state, name='state'),
    path('game/remove-player/<int:id>', views.remove_player, name='remove_player'),
    path('game/start', views.start, name='start'),
    path('game/restart', views.restart, name='restart'),
    path('game/restart-round/<int:round>', views.restart_round, name='restart_round'),
    path('game/target', views.target, name='target'),
    path('404', views.test404, name='test_404'),
    path('500', views.test500, name='test_500'),

    path('cast-all', views.cast_all, name='cast-all'),
]
