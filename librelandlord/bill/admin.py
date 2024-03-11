from django.contrib import admin
# Register your models here.

from . import models

class MeterAdmin(admin.ModelAdmin):
    list_display = ('place', 'remark', 'meter_number','type','build_in_date','out_of_order_date')
admin.site.register(models.MeterPlace)
admin.site.register(models.Meter,MeterAdmin)
admin.site.register(models.MeterReading)
admin.site.register(models.ConsumptionCalc)
admin.site.register(models.AccountEntry)
admin.site.register(models.Apartment)
