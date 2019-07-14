from django.contrib import admin
from .models import Game, Player, Action, Character

admin.site.register(Game)
admin.site.register(Action)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ['name', 'game', 'character', 'died_in_round']

@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']



