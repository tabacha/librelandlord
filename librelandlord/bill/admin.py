from django.contrib import admin
# Register your models here.

from . import models


class MeterPlaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'remark', 'location')
    list_filter = ['type']
    search_fields = ['name', 'location', 'remark']
    ordering = ['name']


admin.site.register(models.MeterPlace, MeterPlaceAdmin)


class MeterAdmin(admin.ModelAdmin):
    list_display = ('meter_number', 'place', 'remark', 'remote_type',
                    'build_in_date', 'calibrated_until_date', 'out_of_order_date')
    list_filter = ['place__type', 'remote_type',
                   'build_in_date', 'out_of_order_date']
    search_fields = ['meter_number', 'remark', 'place__name', 'remote_address']
    autocomplete_fields = ['place']
    date_hierarchy = 'build_in_date'
    ordering = ['-build_in_date']
    fieldsets = (
        (None, {
            'fields': ('place', 'meter_number', 'remark')
        }),
        ('Dates', {
            'fields': ('build_in_date', 'calibrated_until_date', 'out_of_order_date')
        }),
        ('Remote Reading', {
            'fields': ('remote_type', 'remote_address'),
            'classes': ('collapse',)
        }),
    )


admin.site.register(models.Meter, MeterAdmin)


class MeterReadingAdmin(admin.ModelAdmin):
    list_display = ('date', 'meter', 'meter_reading', 'time')
    list_filter = ['date', 'meter__place']
    search_fields = ['meter__meter_number', 'meter__place__name']
    autocomplete_fields = ['meter']
    date_hierarchy = 'date'
    ordering = ['-date', '-time']


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

    ordering = ['name']

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
    list_display = ('date', 'text', 'value', 'bill', 'account_period')
    list_filter = ['date', 'account_period', 'bill__cost_center']
    search_fields = ['text', 'bill__text', 'bill__bill_number']
    autocomplete_fields = ['bill', 'account_period']
    date_hierarchy = 'date'
    ordering = ['-date']


admin.site.register(models.AccountEntry, AccountEntryAdmin)


class ApartmentAdmin(admin.ModelAdmin):
    list_display = ('number', 'name', 'street',
                    'postal_code', 'city', 'size_in_m2')
    list_filter = ['city']
    search_fields = ['number', 'name', 'street', 'city', 'postal_code']
    ordering = ['number']


admin.site.register(models.Apartment, ApartmentAdmin)


class RenterAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'apartment',
                    'move_in_date', 'move_out_date', 'is_active')
    list_filter = ['apartment', 'move_in_date', 'move_out_date']
    search_fields = ['first_name', 'last_name',
                     'apartment__number', 'apartment__name']
    autocomplete_fields = ['apartment']
    date_hierarchy = 'move_in_date'
    ordering = ['-move_in_date']

    def is_active(self, obj):
        """Zeigt an, ob der Mieter aktuell aktiv ist"""
        return obj.move_out_date is None
    is_active.boolean = True
    is_active.short_description = "Active"


admin.site.register(models.Renter, RenterAdmin)


class BillAdmin(admin.ModelAdmin):
    list_display = ('formatted_bill_date', 'text', 'bill_number', 'value',
                    'cost_center', 'account_period', 'formatted_from_date', 'formatted_to_date')
    list_filter = ['bill_date', 'cost_center', 'account_period']
    search_fields = ['text', 'bill_number', 'cost_center__text']
    autocomplete_fields = ['cost_center', 'account_period']
    date_hierarchy = 'bill_date'
    ordering = ['-bill_date']
    fieldsets = (
        (None, {
            'fields': ('text', 'bill_number', 'bill_date', 'value')
        }),
        ('Assignment', {
            'fields': ('cost_center', 'account_period')
        }),
        ('Period', {
            'fields': ('from_date', 'to_date')
        }),
    )

    def formatted_bill_date(self, obj):
        """Zeigt bill_date im Format DD.MM.YYYY"""
        return obj.bill_date.strftime('%d.%m.%Y')
    formatted_bill_date.short_description = 'Bill Date'
    formatted_bill_date.admin_order_field = 'bill_date'

    def formatted_from_date(self, obj):
        """Zeigt from_date im Format DD.MM.YYYY"""
        return obj.from_date.strftime('%d.%m.%Y')
    formatted_from_date.short_description = 'From Date'
    formatted_from_date.admin_order_field = 'from_date'

    def formatted_to_date(self, obj):
        """Zeigt to_date im Format DD.MM.YYYY"""
        return obj.to_date.strftime('%d.%m.%Y')
    formatted_to_date.short_description = 'To Date'
    formatted_to_date.admin_order_field = 'to_date'


admin.site.register(models.Bill, BillAdmin)


class CostCenterAdmin(admin.ModelAdmin):
    list_display = ('text', 'is_oiltank')
    list_filter = ['is_oiltank']
    search_fields = ['text']
    ordering = ['text']


admin.site.register(models.CostCenter, CostCenterAdmin)


class CostCenterContributionAdmin(admin.ModelAdmin):
    list_display = ('get_display_name', 'cost_center', 'apartment',
                    'special_designation', 'consumption_calc')
    list_filter = ['cost_center', 'apartment']
    search_fields = ['apartment__number', 'apartment__name',
                     'special_designation', 'cost_center__text',
                     'consumption_calc__name']
    autocomplete_fields = ['cost_center', 'apartment', 'consumption_calc']
    ordering = ['cost_center', 'apartment']

    def get_display_name(self, obj):
        """Zeigt den Anzeigenamen"""
        return obj.get_display_name()
    get_display_name.short_description = "Name"


admin.site.register(models.CostCenterContribution, CostCenterContributionAdmin)


class CostCenterBillEntryAdmin(admin.ModelAdmin):
    list_display = ('cost_center', 'account_entry',
                    'oil_in_liter', 'get_value')
    list_filter = ['cost_center']
    search_fields = ['cost_center__text', 'account_entry__text']
    autocomplete_fields = ['cost_center', 'account_entry']
    ordering = ['cost_center']

    def get_value(self, obj):
        """Zeigt den Wert aus dem AccountEntry"""
        return obj.account_entry.value
    get_value.short_description = "Value"


admin.site.register(models.CostCenterBillEntry, CostCenterBillEntryAdmin)


class AccountPeriod(admin.ModelAdmin):
    list_display = ('text', 'start_date', 'end_date', 'duration_days')
    list_filter = ['start_date', 'end_date']
    search_fields = ['text']
    date_hierarchy = 'start_date'
    ordering = ['-start_date']

    def duration_days(self, obj):
        """Berechnet die Dauer der Periode in Tagen"""
        delta = obj.end_date - obj.start_date
        return delta.days
    duration_days.short_description = "Duration (days)"


admin.site.register(models.AccountPeriod, AccountPeriod)


class HeatingInfo(admin.ModelAdmin):
    list_display = ('apartment', 'year', 'month', 'heating_energy_kwh',
                    'hot_water_energy_kwh', 'hot_water_m3')
    list_filter = ['year', 'month', 'apartment']
    search_fields = ['apartment__number', 'apartment__name']
    autocomplete_fields = ['apartment']
    ordering = ['-year', '-month', 'apartment']


admin.site.register(models.HeatingInfo, HeatingInfo)


class HeatingInfoTemplate(admin.ModelAdmin):
    list_display = ('apartment', 'next_year', 'next_month',
                    'calc_heating', 'calc_hot_water', 'kwh_per_m3_hot_water')
    list_filter = ['next_year', 'next_month']
    search_fields = ['apartment__number', 'apartment__name']
    autocomplete_fields = ['apartment', 'calc_heating', 'calc_hot_water']
    ordering = ['apartment']
    fieldsets = (
        (None, {
            'fields': ('apartment', 'next_year', 'next_month')
        }),
        ('Calculations', {
            'fields': ('calc_heating', 'calc_hot_water', 'kwh_per_m3_hot_water')
        }),
        ('Comparison Groups', {
            'fields': ('compare_heating_group', 'compare_hot_water_group')
        }),
    )


admin.site.register(models.HeatingInfoTemplate, HeatingInfoTemplate)
