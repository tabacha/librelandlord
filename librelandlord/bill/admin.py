from django.contrib import admin
# Register your models here.

from . import models


class MeterPlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'remark', 'location')
    search_fields = ['name', 'location', 'type']


admin.site.register(models.MeterPlace, MeterPlaceAdmin)


class MeterAdmin(admin.ModelAdmin):
    list_display = ('place', 'remark', 'meter_number',
                    'build_in_date', 'out_of_order_date')


admin.site.register(models.Meter, MeterAdmin)


class MeterReadingAdmin(admin.ModelAdmin):
    list_display = ('meter', 'date', 'meter_reading')


admin.site.register(models.MeterReading, MeterReadingAdmin)


class ConsumptionCalcArgumentInline(admin.TabularInline):
    model = models.ConsumptionCalcArgument
    fk_name = 'consumption_calc'  # Spezifiziere welcher FK verwendet werden soll
    extra = 1
    fields = ['position', 'meter_place', 'value',
              'unit', 'nested_calc', 'explanation']
    ordering = ['position']
    autocomplete_fields = ['meter_place', 'nested_calc']

    class Media:
        css = {
            'all': ('admin/css/changelists.css',)
        }


class ConsumptionCalcAdmin(admin.ModelAdmin):
    list_display = ['name', 'operator', 'start_date',
                    'end_date', 'get_formula_preview']
    list_filter = ['operator', 'start_date']
    search_fields = ['name']
    inlines = [ConsumptionCalcArgumentInline]

    # Blende die alten deprecated Felder aus
    exclude = [
        'argument1', 'argument1_value', 'argument1_unit', 'argument1_explanation', 'operator1',
        'argument2', 'argument2_value', 'argument2_unit', 'argument2_explanation', 'operator2',
        'argument3', 'argument3_value', 'argument3_unit', 'argument3_explanation'
    ]

    def get_formula_preview(self, obj):
        """Zeigt Formel-Vorschau in der Liste"""
        args = obj.arguments.all()[:5]  # Max 5 Arguments anzeigen
        if not args:
            return "-"
        parts = []
        for arg in args:
            if arg.meter_place:
                parts.append(str(arg.meter_place.name)[:20])
            elif arg.nested_calc:
                parts.append(f"({arg.nested_calc.name[:15]})")
            elif arg.value is not None:
                parts.append(f"{arg.value}{arg.unit}")

        formula = f" {obj.operator} ".join(parts)
        if obj.arguments.count() > 5:
            formula += " ..."
        return formula

    get_formula_preview.short_description = "Formel"


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
    list_display = ('text', 'bill_date', 'value', 'from_date', 'to_date')


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


class AccountPeriod(admin.ModelAdmin):
    list_display = ('text', 'start_date', 'end_date')


admin.site.register(models.AccountPeriod, AccountPeriod)


class HeatingInfo(admin.ModelAdmin):
    list_display = ('apartment', 'year', 'month')


admin.site.register(models.HeatingInfo, HeatingInfo)


class HeatingInfoTemplate(admin.ModelAdmin):
    lists_display = ('apartment')


admin.site.register(models.HeatingInfoTemplate, HeatingInfoTemplate)
