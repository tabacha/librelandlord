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


urlpatterns = [
    path('', lambda request: redirect('/bill/')),  # Root redirect
    path('bill/', include('bill.urls')),
    path('admin/', admin.site.urls),
    path('oidc/', include('mozilla_django_oidc.urls')),  # OIDC URLs
]

# Redirect /accounts/login/ to OIDC in production
if getattr(settings, 'USE_OIDC_ONLY', False):
    urlpatterns.extend([
        path('accounts/login/', lambda request: redirect('/oidc/authenticate/')),
        # Admin login auch über OIDC
        path('admin/login/', lambda request: redirect('/oidc/authenticate/?next=/admin/'))
    ])

# Add static files serving
urlpatterns += staticfiles_urlpatterns()

# Serve static files in production (normally done by web server)
urlpatterns += static(settings.STATIC_URL,
                      document_root=settings.STATIC_ROOT)
