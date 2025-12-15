"""
URL configuration for librelandlord project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.shortcuts import redirect

from django.http import HttpResponse


def oidc_test_view(request):
    return HttpResponse("OIDC URLs loaded correctly")

def debug_headers_view(request):
    headers_info = []
    headers_info.append(f"request.is_secure(): {request.is_secure()}")
    headers_info.append(f"request.scheme: {request.scheme}")
    headers_info.append(f"HTTP_X_FORWARDED_PROTO: {request.META.get('HTTP_X_FORWARDED_PROTO', 'NOT SET')}")
    headers_info.append(f"HTTP_HOST: {request.META.get('HTTP_HOST', 'NOT SET')}")
    headers_info.append(f"SERVER_NAME: {request.META.get('SERVER_NAME', 'NOT SET')}")
    headers_info.append(f"SECURE_PROXY_SSL_HEADER: {getattr(settings, 'SECURE_PROXY_SSL_HEADER', 'NOT SET')}")
    headers_info.append(f"USE_TLS: {getattr(settings, 'USE_TLS', 'NOT SET')}")
    return HttpResponse("<br>".join(headers_info))


urlpatterns = [
    path('', lambda request: redirect('/bill/')),  # Root redirect
    path('bill/', include('bill.urls')),
    path('admin/', admin.site.urls),
    path('oidc/test/', oidc_test_view),  # Test-View
    path('debug/headers/', debug_headers_view),  # Debug Headers
    path('oidc/', include('mozilla_django_oidc.urls')),  # OIDC URLs
]

# Redirect /accounts/login/ to OIDC in production
if getattr(settings, 'USE_OIDC_ONLY', False):
    urlpatterns.extend([
        path('accounts/login/', lambda request: redirect('/oidc/authenticate/')),
        # Admin login auch über OIDC
        path('admin/login/', lambda request: redirect('/oidc/authenticate/?next=/admin/'))
    ])

# Add static files serving during development
urlpatterns += staticfiles_urlpatterns()
