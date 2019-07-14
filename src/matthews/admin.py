from django.contrib import admin
from .models import Game, Player, Action, Character

admin.site.register(Game)
admin.site.register(Player)
admin.site.register(Action)



@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ['id', 'name']



