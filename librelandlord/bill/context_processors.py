from django.conf import settings


def paperless_settings(request):
    """Make Paperless settings available in templates."""
    return {
        'PAPERLESS_BASE_URL': settings.PAPERLESS_BASE_URL,
    }
