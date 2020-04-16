import os
from datetime import datetime

from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def date_updated():
    ''' return the date this container image was built, written into file by Dockerfile '''
    timestamp = os.path.getmtime(settings.DJANGO_BASE_DIR + '/manage.py')
    return datetime.fromtimestamp(timestamp).strftime("%H:%M on %a %d %b %Y")
