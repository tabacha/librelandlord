from django.urls import path, register_converter
from django.shortcuts import redirect

from . import views
from librelandlord.convertes import DateConverter

register_converter(DateConverter, "date")

app_name = 'bill'

urlpatterns = [
    path("", lambda request: redirect('/admin/'), name="index"),
    path("login/", views.custom_login, name="login"),
    path("heating_info/<int:id>.html", views.heating_info, name="heating_info"),
    path("heating_info/<int:id>.pdf",
         views.heating_info_pdf, name="heating_info_pdf"),
    path("heating_info/<int:id>.json",
         views.heating_info_json, name="heating_info_json"),
    path("heating_info/token/<str:token>.pdf",
         views.heating_info_pdf_by_token, name="heating_info_pdf_by_token"),
    path("heating_info/token/<str:token>.json",
         views.heating_info_json_by_token, name="heating_info_json_by_token"),
    path("heating_info/unsubscribe/<str:token>",
         views.heating_info_unsubscribe, name="heating_info_unsubscribe"),
    path("meter_place_consumption/<int:meter_place>/<date:start_date>/<date:end_date>", views.meter_place_consumption,
         name="meta_place_consumption"),
    # path("calc_consumption_calc/<int:meter_place>/<date:start_date>/<date:end_date>", views.calc_consumption_calc,
    #     name="calc_consumption_calc"),

    path("heating_info_task", views.heating_info_task, name="heating_info_task"),
    path("yearly-calculation/<int:billing_year>/",
         views.yearly_calculation, name="yearly_calculation"),
    path("yearly-calculation/<int:billing_year>/renter/<int:renter_id>/",
         views.yearly_calculation, name="yearly_calculation_renter"),
    path("tax-overview/<int:billing_year>/",
         views.tax_overview, name="tax_overview"),
    path("meter-readings-input/", views.meter_readings_input,
         name="meter_readings_input"),
    path("meter-readings-save-single/", views.meter_readings_save_single,
         name="meter_readings_save_single"),
    # API für Admin
    path("api/costcenter/<int:cost_center_id>/distribution-type/",
         views.costcenter_distribution_type, name="costcenter_distribution_type"),
    # API für M-Bus Import
    path("api/mbus/import/", views.mbus_readings_import,
         name="mbus_readings_import"),
    # API für Dashboard-Statistiken
    path("api/dashboard-stats/", views.dashboard_stats_api,
         name="dashboard_stats_api"),
    # Notfallkontakte
    path("emergency-contacts/", views.emergency_contacts,
         name="emergency_contacts"),
    # API für Paperless-ID Update
    path("api/bill/<int:bill_id>/paperless-id/", views.bill_paperless_id_update,
         name="bill_paperless_id_update"),
]
