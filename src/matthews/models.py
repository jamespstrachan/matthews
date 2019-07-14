from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):

    def __str__(self):
        return self.first_name + " " + self.last_name


class Game(models.Model):
    date_started = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return 'Game {}'.format(self.id)



class Player(models.Model):
    name      = models.CharField(max_length=12, blank=False, null=False)
    game      = models.ForeignKey('Game', related_name='players', on_delete=models.CASCADE, blank=False, null=False)
    character = models.ForeignKey('Character', related_name='players', on_delete=models.PROTECT, blank=True, null=True)
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