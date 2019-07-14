from datetime import datetime
from math import floor

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from django.contrib import messages
from django.conf import settings

from django_tables2 import RequestConfig

from .models import Game, Player, Action

@login_required
def home(request):
    context = {}
    return render(request, 'matthews/home.html', context)


def new_game(request):
    game = Game()
    game.save()
    messages.add_message(request, messages.INFO, 'New game created')
    return HttpResponseRedirect(reverse('matthews:lobby', kwargs={'id': game.id}))


def lobby(request, id):
    game = Game.objects.get(id=id)
    context = {
        'game':    game,
        'players': game.players.all(),
        'my_player': Player.objects.filter(id=request.session.get('player_id')).first(),
    }
    return render(request, 'matthews/lobby.html', context)


def game(request):
    game = Game.objects.get(id=request.session['game_id'])
    context = {
        'game':      game,
        'players':   game.players.all(),
        'base_url':  settings.BASE_URL,
        'my_player': Player.objects.filter(id=request.session.get('player_id')).first(),
        'round':     calculate_round(game),
    }
    return render(request, 'matthews/game.html', context)


def calculate_round(game):
    return floor(Action.objects.filter(done_by__game=game).count() / game.players.count())

def join(request, id):
    game = Game.objects.get(id=id)
    name = request.POST['name']

    if Player.objects.filter(game=game, name=name).count():
        raise Exception("There's already a player called '{}'".format(name))

    player = Player(name=name, game=game)
    player.save()

    request.session['game_id']   = game.id
    request.session['player_id'] = player.id

    messages.add_message(request, messages.INFO, 'Player {} added'.format(name))
    return HttpResponseRedirect(reverse('matthews:game'))

def start(request):
    game = Game.objects.get(id=request.session['game_id'])
    if game.players.all().order_by('id').first().id != request.session['player_id']:
        raise Exception('Only the first player in the game can start it')

    game.date_start = datetime.now()
    game.save()

    messages.add_message(request, messages.INFO, 'Game started, tell other players to refresh their screens')
    return HttpResponseRedirect(reverse('matthews:game'))


def target(request):
    game = Game.objects.get(id=request.session['game_id'])
    player = Player.objects.get(id=request.session['player_id'])
    target = Player.objects.filter(id=request.POST['target']).first()

    if target and target.game.id != game.id:
        raise Exception("That player's not in this game")

    action = Action(round=calculate_round(game), done_by=player, done_to=target)
    action.save()

    messages.add_message(request, messages.INFO, 'Saved action')
    return HttpResponseRedirect(reverse('matthews:game'))


def test404(request):
    raise Http404("Test: Not found")


def test500(request):
    raise Exception("Test: An error occurred")