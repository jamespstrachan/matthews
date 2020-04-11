""" handles email sending """
from django.conf import settings
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives

def send_email(recipients, subject, template_base=None, context={}, html_content=None, text_content=None):
    """ sends an email as directed, but observes instance email settings
        either expects a template_base & context pair or a pre-rendered html_content & text_content pair
        @param `recipients` expects a list of recipients, even if it's only length 1
        @param `template_base` should be a file path with no extension, to which '.txt' and '.html'
        can be appended.
        @param `context` is a dict of data to be rendered into the template files
    """
    if settings.BLOCK_EMAIL_SENDING:
        return

    if not settings.IS_PRODUCTION and not settings.SEND_ALL_EMAILS_TO:
        raise Exception('Email sending blocked from an instance with IS_PRODUCTION=False and SEND_ALL_EMAILS_TO not set')

    if settings.SEND_ALL_EMAILS_TO:
        subject = '{} (( redirected from {} ))'.format(subject, recipients)
        context.update({
            'SEND_ALL_EMAILS_TO' : settings.SEND_ALL_EMAILS_TO,
            'original_recipients': recipients
        })
        recipients = [settings.SEND_ALL_EMAILS_TO]

    if 'BASE_URL' not in context:
        context.update({'BASE_URL': settings.BASE_URL})

    if not html_content:
        html_content = render_to_string(template_base + '.html', context)
    if not text_content:
        text_content = render_to_string(template_base + '.txt', context)
    from_email = settings.SYSTEM_FROM_EMAIL
    email = EmailMultiAlternatives(subject, text_content, from_email, recipients)
    email.attach_alternative(html_content, "text/html")
    email.send()
