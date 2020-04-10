from datetime import datetime
from math import floor
import random

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, Http404
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from django.db.models import Count, Q

from django_tables2 import RequestConfig

from .models import Game, Player, Action


MAFIA_ID     = 1
CIVILIAN_ID  = 2
DOCTOR_ID    = 3
DETECTIVE_ID = 4

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


def join(request, id):
    game = Game.objects.get(id=id)
    name = request.POST['name']

    if game.date_started:
        raise Exception("This game has already started, blame {}".format(game.players.first().name))

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

    num_players = 1 + game.players.count()
    num_bad = 1 + floor(0.22 * num_players) #todo: add random dither

    special_character_ids = [DOCTOR_ID, DETECTIVE_ID] + ([MAFIA_ID] * num_bad)
    all_character_ids = special_character_ids + ([CIVILIAN_ID] * (num_players - len(special_character_ids)))

    random.shuffle(all_character_ids)

    for player in game.players.all():
        player.character_id = all_character_ids.pop()
        player.save()

    game.date_started = datetime.now()
    game.save()

    messages.add_message(request, messages.INFO, 'Game started, tell other players to refresh their screens')
    return HttpResponseRedirect(reverse('matthews:game'))


def game(request):
    play_as_id = request.GET.get('play_as_id')
    if play_as_id:
        request.session['player_id'] = int(play_as_id)
        messages.add_message(request, messages.INFO, 'You are now playing as player {}'.format(play_as_id))
        return HttpResponseRedirect(reverse('matthews:game'))

    debug = request.GET.get('debug')
    if debug is not None:
        request.session['debug'] = int(debug)
        messages.add_message(request, messages.INFO, 'debug set to {}'.format(debug))
        return HttpResponseRedirect(reverse('matthews:game'))

    game = Game.objects.get(id=request.session['game_id'])
    round = calculate_round(game)
    my_player = Player.objects.filter(id=request.session.get('player_id')).first()

    suspect = None
    if round % 2 == 0 and my_player.character_id == DETECTIVE_ID:
        investigation = Action.objects.filter(round=round-1, done_by=my_player).first()
        suspect = investigation.done_to if investigation else None

    context = {
        'debug':     request.session.get('debug', 0),
        'game':      game,
        'players':   game.players.all().annotate(has_acted=Count('actions_by', filter=Q(actions_by__round=round))),
        'base_url':  settings.BASE_URL,
        'my_player': my_player,
        'my_action': Action.objects.filter(round=round, done_by=my_player).first(),
        'round':     round,
        'votes':     Action.objects.filter(round=round-1, done_by__game=game).order_by('done_to'),
        'deaths':    game.players.filter(died_in_round=round-1),
        'suspect':   suspect,
        'MAFIA_ID':  MAFIA_ID,
        'mafia_win': did_mafia_win(game),
    }
    return render(request, 'matthews/game.html', context)


def target(request):
    game = Game.objects.get(id=request.session['game_id'])
    player = Player.objects.get(id=request.session['player_id'])
    target = Player.objects.filter(id=request.POST['target']).first()

    if target and target.game.id != game.id:
        raise Exception("That player's not in this game")

    save_action(game, player, target)

    messages.add_message(request, messages.INFO, 'Saved action')
    return HttpResponseRedirect(reverse('matthews:game'))


def test404(request):
    raise Http404("Test: Not found")


def test500(request):
    raise Exception("Test: An error occurred")


def calculate_round(game):
    return floor(Action.objects.filter(done_by__game=game).count() / game.players.count())


def save_action(game, done_by, done_to):
    round = calculate_round(game)
    action = Action.objects.filter(round=round, done_by=done_by).first() \
             or Action(round=round, done_by=done_by)
    action.done_to = done_to
    action.save()

    # Fill in blank actions for dead players who haven't acted so they don't hold up the game
    non_voters = yet_to_vote(game, round)
    if non_voters.count() == 0:
        for corpse in yet_to_vote(game, round, False):
            action = Action(round=round, done_by=corpse, done_to=None)
            action.save()

    if calculate_round(game) != round: # If this action completes a round of voting
        victims = who_died(game, round)
        for victim in victims:
            victim.died_in_round = round
            victim.save()


def yet_to_vote(game, round, is_alive=True):
    """ Return a query idenfying alive players who have not voted in this round
    """
    return game.players.filter(died_in_round__isnull=is_alive) \
                       .exclude(actions_by__round=round)


def who_died(game, round):
    """ returns a list of players who were killed by the actions of this round
    """
    nominees = game.players.filter(actions_to__round=round,
                                   actions_to__done_by__died_in_round__isnull=True) \
                           .annotate(votes=Count('actions_to')) \
                           .order_by('-votes')

    if round % 2 == 0: # process day vote
        nominee = nominees.first()
        num_alive_players = game.players.exclude(died_in_round__isnull=False).count()
        if nominee and nominee.votes > num_alive_players / 2: # Simple majority
            return [nominee]

    else: # process night actions
        targets = nominees.filter(actions_to__done_by__character_id=MAFIA_ID)
        target = targets.first()

        doctor_save_action = Action.objects.filter(round=round, done_to=target,
                                                   done_by__character_id=DOCTOR_ID,
                                                   done_by__died_in_round__isnull=True).first()

        # todo - decide if mafia need majority
        if target and not doctor_save_action:
            return [target]
    return []


def did_mafia_win(game):
    """ returns True if so; False if Civilians win; None if game is undecided
    """
    players = game.players.filter(died_in_round__isnull=True)
    num_players = players.count()
    num_bad = players.filter(character__id=MAFIA_ID).count()

    if num_bad == 0:
        return False
    if num_bad >= num_players / 2:
        return True
    return None


def cast_all(request):
    game = Game.objects.get(id=request.session['game_id'])
    round = calculate_round(game)
    non_voters = yet_to_vote(game, round)

    target = None #non_voters.first()
    for player in non_voters:
        save_action(game, player, target)

    messages.add_message(request, messages.INFO, '{} votes cast'.format(len(non_voters)))
    return HttpResponseRedirect(reverse('matthews:game'))
