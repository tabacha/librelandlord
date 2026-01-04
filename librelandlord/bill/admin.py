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

    # Admin Actions für Listenansicht
    actions = ['duplicate_consumption_calc_action']

    # Button auf Change-Seite aktivieren
    change_form_template = 'admin/bill/consumptioncalc/change_form.html'

    def _duplicate_single(self, obj):
        """Dupliziert ein einzelnes ConsumptionCalc Objekt inkl. Arguments"""
        original_arguments = list(obj.arguments.all())
        original_name = obj.name

        obj.pk = None
        obj.name = f"{original_name} (Kopie)"
        obj.save()

        for arg in original_arguments:
            arg.pk = None
            arg.consumption_calc = obj
            arg.save()

        return obj

    def duplicate_consumption_calc_action(self, request, queryset):
        """Admin Action: Dupliziert ausgewählte ConsumptionCalc Objekte"""
        for obj in queryset:
            self._duplicate_single(obj)
        self.message_user(
            request,
            f"{queryset.count()} ConsumptionCalc(s) erfolgreich dupliziert."
        )
    duplicate_consumption_calc_action.short_description = "Ausgewählte ConsumptionCalcs duplizieren"

    def response_change(self, request, obj):
        """Handle den Duplizieren-Button auf der Change-Seite"""
        if "_duplicate" in request.POST:
            original_name = obj.name
            new_obj = self._duplicate_single(obj)
            self.message_user(
                request, f"'{original_name}' wurde als '{new_obj.name}' dupliziert.")
            from django.urls import reverse
            from django.http import HttpResponseRedirect
            return HttpResponseRedirect(
                reverse('admin:bill_consumptioncalc_change', args=[new_obj.pk])
            )
        return super().response_change(request, obj)

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


class RentPaymentInline(admin.TabularInline):
    """Inline für Mietpreise beim Renter"""
    model = models.RentPayment
    extra = 1
    fields = ['start_date', 'end_date', 'cold_rent', 'advance_payment']
    ordering = ['-start_date']


class RenterAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'apartment',
                    'move_in_date', 'move_out_date', 'is_active')
    list_filter = ['apartment', 'move_in_date', 'move_out_date']
    search_fields = ['first_name', 'last_name',
                     'apartment__number', 'apartment__name']
    autocomplete_fields = ['apartment']
    date_hierarchy = 'move_in_date'
    ordering = ['-move_in_date']
    inlines = [RentPaymentInline]

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


class CostCenterContributionInline(admin.TabularInline):
    """Inline für CostCenterContribution im CostCenter Admin"""
    model = models.CostCenterContribution
    extra = 1
    autocomplete_fields = ['apartment', 'consumption_calc']
    fields = ['apartment', 'special_designation', 'consumption_calc']

    def get_formset(self, request, obj=None, **kwargs):
        """
        Passt das Formset an den distribution_type an.
        """
        formset = super().get_formset(request, obj, **kwargs)

        # Wenn ein CostCenter existiert und der Typ nicht CONSUMPTION ist,
        # mache consumption_calc nicht erforderlich
        if obj and obj.distribution_type != models.CostCenter.DistributionType.CONSUMPTION:
            if 'consumption_calc' in formset.form.base_fields:
                formset.form.base_fields['consumption_calc'].required = False
        else:
            # Bei neuen Objekten oder CONSUMPTION: auch nicht required
            # (wird per clean() validiert)
            if 'consumption_calc' in formset.form.base_fields:
                formset.form.base_fields['consumption_calc'].required = False

        return formset


class CostCenterAdmin(admin.ModelAdmin):
    list_display = ('text', 'distribution_type', 'is_oiltank')
    list_filter = ['is_oiltank', 'distribution_type']
    search_fields = ['text']
    ordering = ['text']
    inlines = [CostCenterContributionInline]

    class Media:
        js = ('bill/js/admin/costcentercontribution.js',)


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

    class Media:
        js = ('bill/js/admin/costcentercontribution.js',)

    def get_display_name(self, obj):
        """Zeigt den Anzeigenamen"""
        return obj.get_display_name()
    get_display_name.short_description = "Name"

    def get_fields(self, request, obj=None):
        """
        Ordnet die Felder und blendet consumption_calc aus wenn nicht benötigt.
        """
        fields = ['cost_center', 'apartment',
                  'special_designation', 'consumption_calc']
        return fields

    def get_readonly_fields(self, request, obj=None):
        """
        Macht consumption_calc readonly wenn der CostCenter-Typ nicht CONSUMPTION ist.
        """
        readonly = list(super().get_readonly_fields(request, obj))
        if obj and obj.cost_center:
            if obj.cost_center.distribution_type != models.CostCenter.DistributionType.CONSUMPTION:
                # Feld nicht in readonly - wird per JS ausgeblendet
                pass
        return readonly

    def get_form(self, request, obj=None, **kwargs):
        """
        Passt das Formular an den distribution_type an.
        """
        form = super().get_form(request, obj, **kwargs)

        # Wenn ein Objekt existiert und der Typ nicht CONSUMPTION ist,
        # mache consumption_calc nicht erforderlich
        if obj and obj.cost_center:
            if obj.cost_center.distribution_type != models.CostCenter.DistributionType.CONSUMPTION:
                if 'consumption_calc' in form.base_fields:
                    form.base_fields['consumption_calc'].required = False
        else:
            # Bei neuen Objekten: nicht erforderlich machen
            # (wird per JS und clean() validiert)
            if 'consumption_calc' in form.base_fields:
                form.base_fields['consumption_calc'].required = False

        return form


# CostCenterContribution wird nur als Inline unter CostCenter angezeigt,
# nicht im Hauptmenü (daher keine admin.site.register)


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


class LandlordAdmin(admin.ModelAdmin):
    list_display = ('name', 'street', 'postal_code', 'city', 'phone', 'email')

    def has_add_permission(self, request):
        # Nur erlauben, wenn noch kein Eintrag existiert
        if models.Landlord.objects.exists():
            return False
        return super().has_add_permission(request)

    def has_delete_permission(self, request, obj=None):
        # Löschen verhindern
        return False


admin.site.register(models.Landlord, LandlordAdmin)
