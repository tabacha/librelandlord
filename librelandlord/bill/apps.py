from django.apps import AppConfig


class BillConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bill'

    def ready(self):
        from django.contrib import admin
        admin.site.site_header = 'LibreLandlord Admin'
        admin.site.site_title = 'LibreLandlord'
        admin.site.index_title = 'Verwaltung'
