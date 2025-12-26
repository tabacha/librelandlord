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
from django.http import HttpResponseRedirect
from django.urls import include, path, reverse
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.shortcuts import redirect
from django.views.generic import View


class CustomLogin(View):
    def get(self, request, **kwargs):
        return HttpResponseRedirect(
            reverse('oidc_authentication_init') + (
                '?next={}'.format(
                    request.GET['next']) if 'next' in request.GET else ''
            )
        )


urlpatterns = [
    path('', lambda request: redirect('/bill/')),  # Root redirect
    path('bill/', include('bill.urls')),
    path('oidc/', include('mozilla_django_oidc.urls')),  # OIDC URLs
]

# Configure authentication based on USE_OIDC_ONLY setting
if getattr(settings, 'USE_OIDC_ONLY', False):
    # OIDC-only mode: redirect all logins to OIDC
    urlpatterns.extend([
        path('accounts/login/', lambda request: redirect('/oidc/authenticate/')),
        path('admin/login/', CustomLogin.as_view()),
        path('admin/', admin.site.urls),
    ])
else:
    # Mixed mode: support both local and OIDC authentication
    from django.contrib.auth import views as auth_views
    urlpatterns.extend([
        path('accounts/login/', auth_views.LoginView.as_view(), name='login'),
        path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),
        # Custom admin login that uses our template BEFORE admin.site.urls
        path('admin/login/', auth_views.LoginView.as_view(
            template_name='registration/login.html',
            extra_context={'title': 'Administration - Anmeldung'}
        )),
        path('admin/', admin.site.urls),
    ])

# Add static files serving
urlpatterns += staticfiles_urlpatterns()

# Serve static files even in production for small systems
# This overrides Django's default behavior of not serving static files when DEBUG=False
if settings.DEBUG or getattr(settings, 'FORCE_SERVE_STATIC', False):
    urlpatterns += static(settings.STATIC_URL,
                          document_root=settings.STATIC_ROOT)
