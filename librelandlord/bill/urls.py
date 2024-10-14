from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("heating_info", views.heating_info, name="heating_info"),
    path("heating_info.pdf", views.heating_info_pdf, name="heating_info.pdf"),
]
