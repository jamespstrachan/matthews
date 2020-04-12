from datetime import datetime
from math import floor
import random
import hashlib
import re

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, Http404, HttpResponse
from django.urls import reverse
from django.contrib import messages
from django.conf import settings
from django.db.models import Count, Q, F, FloatField
from django.db.models.functions import Cast, Coalesce

from django_tables2 import RequestConfig

from project.emails import send_email
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
    name = request.GET['leader']
    return join(request, game.id, name, True)


def make_invite_hash(game_id, name):
    cleartext = str(game_id) + 'invite_hash' + name + settings.SECRET_KEY
    return hashlib.md5(cleartext.encode('utf-8')).hexdigest()


def make_invite_url(game_id, name):
    kwargs = {'id': game_id, 'name': name, 'hash': make_invite_hash(game_id, name)}
    return settings.BASE_URL + reverse('matthews:join', kwargs=kwargs)


def invite(request, id):
    game = Game.objects.get(id=id)

    if game.date_started:
        messages.add_message(request, messages.WARNING, "Can't invite new players the game has started")
        return HttpResponseRedirect(reverse('matthews:game'))

    if request.method == "POST":
        player_list = request.POST['name_and_email']

        if game.date_started:
            raise Exception("This game has already started, blame {}".format(game.players.first().name))

        for name, email in (x.split(',') for x in player_list.split('\n')):
            name  = name.strip()
            email = email.strip()
            url   = make_invite_url(id, name)
            msg = "Join game {}".format(url)
            if '@' in email:
                send_email([email], 'Join Matthews Game', html_content=msg, text_content=msg)
            elif not Player.objects.filter(game=game, name=name).first():
                player = Player(name=name, game=game)
                player.save()
            messages.add_message(request, messages.INFO, 'Player {} invited by email with {}'.format(name, url))

        return HttpResponseRedirect(reverse('matthews:invite', kwargs={'id': game.id}))

    context = {
        'game':    game,
        'players': game.players.all(),
        'my_player': Player.objects.filter(id=request.session.get('player_id')).first(),
    }
    return HttpResponseRedirect(reverse('matthews:game'))


def join(request, id, name, hash):
    game = Game.objects.get(id=id)

    if hash != True and hash != make_invite_hash(game.id, name):
        messages.add_message(request, messages.INFO, "The link you follwed is invalid, please check and retry")
        return HttpResponseRedirect(reverse('matthews:home'))

    player = Player.objects.filter(game=game, name=name).first()
    if not player:
        player = Player(name=name, game=game)
        player.save()

    request.session['game_id']   = game.id
    request.session['player_id'] = player.id

    return HttpResponseRedirect(reverse('matthews:game'))


def restart(request):
    game = Game.objects.get(id=request.session['game_id'])
    for player in game.players.all():
        player.actions_by.all().delete()
        player.died_in_round = None
        player.character = None
        player.save()
    game.date_started = None
    game.save()
    return HttpResponseRedirect(reverse('matthews:game'))


def start(request):
    game = Game.objects.get(id=request.session['game_id'])
    if game.players.all().order_by('id').first().id != request.session['player_id']:
        raise Exception('Only the first player in the game can start it')

    num_players = 1 + game.players.count()
    num_bad = 1 + floor(0.19 * num_players) #todo: add random dither

    special_character_ids = [DOCTOR_ID, DETECTIVE_ID] + ([MAFIA_ID] * num_bad)
    all_character_ids = special_character_ids + ([CIVILIAN_ID] * (num_players - len(special_character_ids)))

    random.shuffle(all_character_ids)

    for player in game.players.all():
        player.character_id = all_character_ids.pop()
        player.save()

    game.date_started = datetime.now()
    game.save()

    return HttpResponseRedirect(reverse('matthews:game'))


def game(request):
    play_as_id = request.GET.get('play_as_id')
    if play_as_id:
        request.session['player_id'] = int(play_as_id)
        return HttpResponseRedirect(reverse('matthews:game'))

    debug = request.GET.get('debug')
    if debug is not None:
        request.session['debug'] = int(debug)
        messages.add_message(request, messages.INFO, 'debug set to {}'.format(debug))
        return HttpResponseRedirect(reverse('matthews:game'))

    game_id = request.session.get('game_id')
    if not game_id:
        messages.add_message(request, messages.INFO, "You're not currently in any game, follow the link in the invite email to join one")
        return HttpResponseRedirect(reverse('matthews:home'))
    game = Game.objects.get(id=game_id)

    newest_action = Action.objects.filter(done_by__game=game).order_by('-id').first()
    newest_action_id = newest_action.id if newest_action else 0
    if request.GET.get('any_actions_since'):
        new_actions = newest_action_id > int(request.GET.get('any_actions_since'))
        return HttpResponse(newest_action_id if new_actions else 0);

    round = calculate_round(game)
    my_player = Player.objects.filter(id=request.session.get('player_id')).first()

    suspect = None
    if round % 2 == 0 and my_player.character_id == DETECTIVE_ID:
        investigation = Action.objects.filter(round=round-1, done_by=my_player).first()
        suspect = investigation.done_to if investigation else None

    players = game.players.all()

    mafia_win = did_mafia_win(game)
    if mafia_win is not None:
        bad_guy_ids = [MAFIA_ID]
        good_guy_ids = [CIVILIAN_ID, DOCTOR_ID, DETECTIVE_ID]
        day_regex   = '^\d*[02468]$'
        night_regex = '^\d*[13579]$'
        was_alive_to_act         = Q(actions_by__round__lte=F('died_in_round')) | Q(died_in_round__isnull=True)
        was_alive_to_be_acted_on = Q(actions_to__round__lte=F('died_in_round')) | Q(died_in_round__isnull=True)
        players = players.annotate(lynched_bad=Count('actions_by', distinct=True,
                                                     filter=Q(was_alive_to_act,
                                                              actions_by__round__iregex=day_regex,
                                                              actions_by__done_to__character_id__in=bad_guy_ids,
                                                              actions_by__done_to__died_in_round=F('actions_by__round')))
                        ).annotate(lynched_good=Count('actions_by', distinct=True,
                                                      filter=Q(was_alive_to_act,
                                                               actions_by__round__iregex=day_regex,
                                                               actions_by__done_to__character_id__in=good_guy_ids,
                                                               actions_by__done_to__died_in_round=F('actions_by__round')))
                        ).annotate(killed_bad=Count('actions_by', distinct=True,
                                                    filter=Q(was_alive_to_act,
                                                             character_id=MAFIA_ID,
                                                             actions_by__round__iregex=night_regex,
                                                             actions_by__done_to__character_id__in=bad_guy_ids,
                                                             actions_by__done_to__died_in_round=F('actions_by__round')))
                        ).annotate(killed_good=Count('actions_by', distinct=True,
                                                     filter=Q(was_alive_to_act,
                                                              character_id=MAFIA_ID,
                                                              actions_by__round__iregex=night_regex,
                                                              actions_by__done_to__character_id__in=good_guy_ids,
                                                              actions_by__done_to__died_in_round=F('actions_by__round')))
                        ).annotate(killed_doctor=Count('actions_by', distinct=True,
                                                     filter=Q(was_alive_to_act,
                                                              character_id=MAFIA_ID,
                                                              actions_by__round__iregex=night_regex,
                                                              actions_by__done_to__character_id=DOCTOR_ID,
                                                              actions_by__done_to__died_in_round=F('actions_by__round')))
                        ).annotate(killed_detective=Count('actions_by', distinct=True,
                                                     filter=Q(was_alive_to_act,
                                                              character_id=MAFIA_ID,
                                                              actions_by__round__iregex=night_regex,
                                                              actions_by__done_to__character_id=DETECTIVE_ID,
                                                              actions_by__done_to__died_in_round=F('actions_by__round')))
                        ).annotate(lives_saved=Count('actions_by__round', distinct=True,
                                                     filter=Q(was_alive_to_act,
                                                              character_id=DOCTOR_ID,
                                                              actions_by__round__iregex=night_regex,
                                                              actions_by__done_to__actions_to__done_by__character_id__in=bad_guy_ids,
                                                              actions_by__done_to__actions_to__round=F('actions_by__round')))
                        ).annotate(suspected_bad_pc=Cast(Count('actions_by', distinct=True,
                                                               filter=Q(was_alive_to_act,
                                                                        character_id=CIVILIAN_ID,
                                                                        actions_by__round__iregex=night_regex,
                                                                        actions_by__done_to__character_id__in=bad_guy_ids)), FloatField())
                                                    / Cast(Coalesce(F('died_in_round'), round) + 1 , FloatField())
                                                    * 2 * 100
                        ).annotate(successful_kill_pc=Cast(F('killed_good'), FloatField())
                                                    / Cast(Coalesce(F('died_in_round') + 1, round) , FloatField())
                                                    * 2 * 100
                        ).annotate(mafia_target=Count('actions_to', distinct=True,
                                                     filter=Q(was_alive_to_be_acted_on,
                                                              actions_to__round__iregex=night_regex,
                                                              actions_to__done_by__character_id__in=bad_guy_ids))
                        ).annotate(mafia_found=Count('actions_by', distinct=True,
                                                    filter=Q(was_alive_to_act,
                                                             character_id=DETECTIVE_ID,
                                                             actions_by__round__iregex=night_regex,
                                                             actions_by__done_to__character_id__in=bad_guy_ids))
        )

        players = list(players)
        # todo - add extra params for awards, like so:
        # eg. players[2].favourite_person = "James"
    else:
        players = players.annotate(has_acted=Count('actions_by', filter=Q(actions_by__round=round)))

    deaths = game.players.filter(died_in_round=round-1)
    random.seed(game.id+round)

    context = {
        'debug':        request.session.get('debug', 0),
        'invite_url':   make_invite_url(game.id, my_player.name),
        'game':         game,
        'round':        round,
        'players':      players,
        'my_player':    my_player,
        'my_action':    Action.objects.filter(round=round, done_by=my_player).first(),
        'newest_action_id': newest_action_id,
        'votes':        Action.objects.filter(round=round-1, done_by__game=game) \
                                      .filter(Q(done_by__died_in_round__gte=round) | Q(done_by__died_in_round__isnull=True)) \
                                      .order_by('done_to'),
        'deaths':       deaths,
        'death_report': make_death_report(deaths[0].name) if deaths else '',
        'suspect':      suspect,
        'MAFIA_ID':     MAFIA_ID,
        'mafia_win':    mafia_win,
    }
    return render(request, 'matthews/game.html', context)


def make_death_report(name):
    templates = [
        [
        "A horrible incident at the [Bakery,School,Garden Center,Polio Ward] left {{name}} dead as [a dingbat,a doornail,Jimmy Saville].",
        "Locals came across a [frankly baffling] mystery this morning when they discovered the body of {{name}} locked inside a [suitcase,mini-bar,chest freezer].",
        "There was [chaos,pandemonium,a grim silence] at the [farmers' market] this morning when {{name}}'s [head,arm,spine] was discovered floating in the communal [milk,ale,water] barrel.",
        ],[
        "[Police,First-responders,A young child] found the body with a [spatula,baked potato,half-complete Airfix kit] stuck into its [collarbone,clavicle,right temple] and having lost a lot of blood.",
        "The cause of death was unknown \"Apart from [being dead,their pale colour,male-pattern baldness] they appeared to be in peak physical condition\", said [the coroner,the chief of police,Mrs Ronson from number 34].",
        "Authorities could only identify the body by its [winning smile,nubile physique,luscious sideburns] and [Norway,penis,Mickey Mouse]-shaped birth mark.",
        ],[
        "Our thoughts, prayers and [best wishes,cash prizes,sexy times] are with [the family,the whole world,no one in particular] at this difficult time.",
        "The deceased leaves behind their pet [dog,iguana,zebra] {{name}} Jr. and an unmoved [spouse,set of triplets,mother-in-law].",
        "\"They were always into [hang-gliding,pot-holing,archery]\", [a close friend,a passing cyclist,a disembodied voice] remarked \"so I guess it's what they would have wanted\"",
        ],
    ]

    report_lines = (re.sub(r'\[(.*?)\]',
                           lambda m: random.choice(m.group(1).split(',')),
                           random.choice(x).replace('{{name}}', name)
                           )
                    for x in templates)
    return "\n\n".join(report_lines)



def target(request):
    game = Game.objects.get(id=request.session['game_id'])
    player = Player.objects.get(id=request.session['player_id'])
    target = Player.objects.filter(id=request.POST['target']).first()

    if target and target.game.id != game.id:
        raise Exception("That player's not in this game")

    save_action(game, player, target)

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

    if round % 2 == 0: # process day vote
        nominees = game.players.filter(actions_to__round=round,
                                       actions_to__done_by__died_in_round__isnull=True) \
                               .annotate(votes=Count('actions_to')) \
                               .order_by('-votes')
        nominee = nominees.first()
        num_alive_players = game.players.exclude(died_in_round__isnull=False).count()
        if nominee and nominee.votes > num_alive_players / 2: # Simple majority
            return [nominee]

    else: # process night actions
        targets = game.players.filter(actions_to__round=round,
                                      actions_to__done_by__died_in_round__isnull=True,
                                      actions_to__done_by__character_id=MAFIA_ID) \
                           .annotate(votes=Count('actions_to')) \
                           .order_by('-votes')
        target = targets.first()

        doctor_save_action = Action.objects.filter(done_by__game=game,
                                                   round=round, done_to=target,
                                                   done_by__character_id=DOCTOR_ID,
                                                   done_by__died_in_round__isnull=True).first()

        # todo - decide if mafia need majority
        if target and not doctor_save_action:
            return [target]
    return []


def did_mafia_win(game):
    """ returns True if so; False if Civilians win; None if game is undecided
    """
    if not game.date_started:
        return None

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

    return HttpResponseRedirect(reverse('matthews:game'))
