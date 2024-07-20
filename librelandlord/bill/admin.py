from django.contrib import admin
# Register your models here.

from . import models


class MeterPlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'remark', 'location')


admin.site.register(models.MeterPlace, MeterPlaceAdmin)


class MeterAdmin(admin.ModelAdmin):
    list_display = ('place', 'remark', 'meter_number',
                    'build_in_date', 'out_of_order_date')


admin.site.register(models.Meter, MeterAdmin)


class MeterReadingAdmin(admin.ModelAdmin):
    list_display = ('meter', 'date', 'meter_reading')


admin.site.register(models.MeterReading, MeterReadingAdmin)


class ConsumptionCalcAdmin(admin.ModelAdmin):
    list_display = ['name']


admin.site.register(models.ConsumptionCalc, ConsumptionCalcAdmin)


class AccountEntryAdmin(admin.ModelAdmin):
    list_display = ('date', 'text', 'value', 'bill')


admin.site.register(models.AccountEntry, AccountEntryAdmin)


class ApartmentAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'street', 'size_in_m2')


admin.site.register(models.Apartment, ApartmentAdmin)


class RenterAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'apartment',
                    'move_in_date', 'move_out_date')


admin.site.register(models.Renter, RenterAdmin)


class BillAdmin(admin.ModelAdmin):
    list_display = ('text', 'date', 'value')


admin.site.register(models.Bill, BillAdmin)


class CostCenterAdmin(admin.ModelAdmin):
    list_display = ('text', 'is_oiltank')


admin.site.register(models.CostCenter, CostCenterAdmin)


class CostCenterContributionAdmin(admin.ModelAdmin):
    list_display = ('cost_center', 'apartment', 'consumption_calc')


admin.site.register(models.CostCenterContribution, CostCenterContributionAdmin)


class CostCenterBillEntryAdmin(admin.ModelAdmin):
    list_display = ('cost_center', 'account_entry', 'oil_in_liter')


admin.site.register(models.CostCenterBillEntry, CostCenterBillEntryAdmin)
