import hmac
import hashlib
import subprocess

from django.http import HttpResponse, HttpResponseForbidden, Http404
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
def deploy(request):
    """ triggers git pull of updated application code on receipt of valid webhook """
    github_signature = request.META['HTTP_X_HUB_SIGNATURE']
    signature = hmac.new(settings.SECRET_DEPLOY_KEY.encode('utf-8'), request.body, hashlib.sha1)
    expected_signature = 'sha1=' + signature.hexdigest()
    if not hmac.compare_digest(github_signature, expected_signature):
        return HttpResponseForbidden('Invalid signature header')

    # Example of how to pipe stdout, stderr in case useful in future
    #raise Exception(subprocess.run("git pull open master".split(' '), timeout=15, stdout = subprocess.PIPE, stderr = subprocess.PIPE).stdout)

    if subprocess.run('git pull'.split(' '), timeout=15).returncode == 0 and \
       subprocess.run('python manage.py migrate'.split(' '), timeout=15).returncode == 0 and \
       subprocess.run('python manage.py collectstatic --noinput'.split(' '), timeout=15).returncode == 0:
        return HttpResponse('Webhook received', status=http.client.ACCEPTED)
    raise Http404("Update failed")
