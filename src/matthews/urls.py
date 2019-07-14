from django.urls import path
from . import views

app_name = 'matthews'
urlpatterns = [
    path('', views.home, name='home'),
    path('new-game', views.new_game, name='new-game'),
    path('game/<int:id>', views.lobby, name='lobby'),
    path('game/<int:id>/join', views.join, name='join'),
    path('game', views.game, name='game'),
    path('game/start', views.start, name='start'),
    path('game/target', views.target, name='target'),
    path('404', views.test404, name='test_404'),
    path('500', views.test500, name='test_500'),
]
