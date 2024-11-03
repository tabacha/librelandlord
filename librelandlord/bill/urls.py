from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("heating_info", views.heating_info, name="heating_info"),
    path("heating_info.pdf", views.heating_info_pdf, name="heating_info.pdf"),
    path("meter_place_consumption/<int:meter_place>", views.meter_place_consumption,
         name="meta_place_consumption"),
    path("heating_info_task", views.heating_info_task, name="heating_info_task")
]
