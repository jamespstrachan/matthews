import json
from django.contrib.auth.models import AbstractUser
from django.db import models

MAFIA_ID     = 1
CIVILIAN_ID  = 2
DOCTOR_ID    = 3
DETECTIVE_ID = 4

ROLE_NAMES = {
    MAFIA_ID:     'Mafia',
    CIVILIAN_ID:  'Civilian',
    DOCTOR_ID:    'Doctor',
    DETECTIVE_ID: 'Detective',
}

class DictField(models.TextField):
    """ serialises dicts for saving """
    def from_db_value(self, value, *args):
        return json.loads(value) if value else None

    def get_db_prep_save(self, value, *args, **kwargs):
        return json.dumps(value) if value else None


class User(AbstractUser):

    def __str__(self):
        return self.first_name + " " + self.last_name


class Game(models.Model):
    date_started = models.DateTimeField(null=True, blank=True)
    options      = DictField(blank=True, null=True)
    next_game    = models.OneToOneField('Game', related_name='previous_game',
                                        on_delete=models.SET_NULL, blank=True, null=True)

    def list_good_guys(self):
        return self.players.filter(died_in_round__isnull=True) \
                           .exclude(character__id=MAFIA_ID)

    def list_bad_guys(self):
        return self.players.filter(died_in_round__isnull=True) \
                           .filter(character__id=MAFIA_ID)

    def __str__(self):
        return 'Game {}'.format(self.id)


class Player(models.Model):
    name          = models.CharField(max_length=12, blank=False, null=False)
    game          = models.ForeignKey('Game', related_name='players', on_delete=models.CASCADE, blank=False, null=False)
    character     = models.ForeignKey('Character', related_name='players', on_delete=models.PROTECT, blank=True, null=True)
    died_in_round = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.name


class Character(models.Model):
    name = models.CharField(max_length=12, blank=False, null=False)

    def __str__(self):
        return self.name


class Action(models.Model):
    round   = models.IntegerField(blank=False, null=False)
    done_by = models.ForeignKey('Player', related_name='actions_by', on_delete=models.CASCADE, blank=False, null=False)
    done_to = models.ForeignKey('Player', related_name='actions_to', on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        #todo: remove this after debugging
        return 'round {}: {} targeted {}'.format(self.round, self.done_by, self.done_to)