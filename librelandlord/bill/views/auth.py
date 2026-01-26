from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings


def custom_login(request):
    """Custom login view that supports both OIDC and local authentication"""
    context = {
        'USE_OIDC_ONLY': getattr(settings, 'USE_OIDC_ONLY', False),
        'INSTALLED_APPS': settings.INSTALLED_APPS,
    }
    return render(request, 'registration/login.html', context)


@login_required
def index(request):
    """Redirect zum Admin Dashboard"""
    return redirect('/admin/')
