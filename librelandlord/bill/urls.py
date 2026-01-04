from django.urls import path, register_converter

from . import views
from librelandlord.convertes import DateConverter

register_converter(DateConverter, "date")

app_name = 'bill'

urlpatterns = [
    path("", views.index, name="index"),
    path("login/", views.custom_login, name="login"),
    path("heating_info/<int:id>.html", views.heating_info, name="heating_info"),
    path("heating_info/<int:id>.pdf",
         views.heating_info_pdf, name="heating_info.pdf"),
    path("meter_place_consumption/<int:meter_place>/<date:start_date>/<date:end_date>", views.meter_place_consumption,
         name="meta_place_consumption"),
    # path("calc_consumption_calc/<int:meter_place>/<date:start_date>/<date:end_date>", views.calc_consumption_calc,
    #     name="calc_consumption_calc"),

    path("heating_info_task", views.heating_info_task, name="heating_info_task"),
    path("account-period/<int:account_period_id>/calculation/",
         views.account_period_calculation, name="account_period_calculation"),
    path("account-period/<int:account_period_id>/calculation/renter/<int:renter_id>/",
         views.account_period_calculation, name="account_period_calculation_renter"),
    path("yearly-calculation/<int:billing_year>/",
         views.yearly_calculation, name="yearly_calculation"),
    path("yearly-calculation/<int:billing_year>/renter/<int:renter_id>/",
         views.yearly_calculation, name="yearly_calculation_renter"),
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
]
