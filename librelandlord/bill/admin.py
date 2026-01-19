from django.contrib import admin
# Register your models here.

from . import models
from .admin_csv_import import CSVImportAdminMixin


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


class BillTransactionLinkInline(admin.TabularInline):
    """Inline für Transaction-Links bei Bill (zeigt verknüpfte Banktransaktionen)"""
    model = models.TransactionBillLink
    extra = 0
    fields = ['transaction_info', 'amount', 'notes']
    readonly_fields = ['transaction_info']
    autocomplete_fields = []

    def transaction_info(self, obj):
        """Zeigt Transaktionsinformationen"""
        if obj.transaction:
            from django.utils.html import format_html
            from django.urls import reverse
            url = reverse('admin:bill_banktransaction_change',
                          args=[obj.transaction.pk])
            formatted_amount = f"{obj.transaction.amount:+.2f}"
            return format_html(
                '<a href="{}">{} | {} € | {}</a>',
                url,
                obj.transaction.booking_date.strftime('%d.%m.%Y'),
                formatted_amount,
                obj.transaction.counterpart_name or 'N/A'
            )
        return '-'
    transaction_info.short_description = 'Transaction'


class BillAdmin(admin.ModelAdmin):
    list_display = ('formatted_bill_date', 'text', 'bill_number', 'value',
                    'cost_center', 'account_period', 'formatted_from_date', 'formatted_to_date')
    list_filter = ['bill_date', 'cost_center', 'account_period']
    search_fields = ['text', 'bill_number', 'cost_center__text']
    autocomplete_fields = ['cost_center', 'account_period']
    date_hierarchy = 'bill_date'
    ordering = ['-bill_date']
    inlines = [BillTransactionLinkInline]

    def get_fieldsets(self, request, obj=None):
        import os
        fieldsets = [
            (None, {
                'fields': ('text', 'bill_number', 'bill_date', 'value')
            }),
            ('Assignment', {
                'fields': ('cost_center', 'account_period')
            }),
            ('Period', {
                'fields': ('from_date', 'to_date')
            }),
        ]
        # Paperless-Feld nur anzeigen wenn PAPERLESS_BASE_URL gesetzt ist
        if os.environ.get('PAPERLESS_BASE_URL'):
            fieldsets.append(('Paperless', {
                'fields': ('paperless_id', 'paperless_link', 'paperless_preview'),
                'classes': ('collapse',)
            }))
        return fieldsets

    def get_readonly_fields(self, request, obj=None):
        import os
        readonly = list(super().get_readonly_fields(request, obj))
        if os.environ.get('PAPERLESS_BASE_URL'):
            readonly.extend(['paperless_link', 'paperless_preview'])
        return readonly

    def paperless_link(self, obj):
        """Zeigt Link zu Paperless-NGX Dokument"""
        import os
        from django.utils.html import format_html
        base_url = os.environ.get('PAPERLESS_BASE_URL', '').rstrip('/')
        if obj.paperless_id and base_url:
            url = f"{base_url}/documents/{obj.paperless_id}/details"
            return format_html('<a href="{}" target="_blank">📄 In Paperless öffnen</a>', url)
        return '-'
    paperless_link.short_description = 'Paperless Link'

    def paperless_preview(self, obj):
        """Zeigt Link zur Paperless-NGX PDF Vorschau"""
        import os
        from django.utils.html import format_html
        base_url = os.environ.get('PAPERLESS_BASE_URL', '').rstrip('/')
        if obj.paperless_id and base_url:
            url = f"{base_url}/api/documents/{obj.paperless_id}/preview/"
            return format_html('<a href="{}" target="_blank">👁️ PDF Vorschau</a>', url)
        return '-'
    paperless_preview.short_description = 'Vorschau'

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


# ============================================================================
# Bank Transactions & Matching Rules
# ============================================================================

class BankAccountAdmin(admin.ModelAdmin):
    list_display = ('name', 'account_type', 'iban_display',
                    'bank_name', 'is_active')
    list_filter = ['account_type', 'is_active']
    search_fields = ['name', 'iban', 'bank_name']
    ordering = ['account_type', 'name']
    fieldsets = (
        (None, {
            'fields': ('name', 'account_type', 'is_active')
        }),
        ('Bank Details', {
            'fields': ('iban', 'bic', 'bank_name'),
            'classes': ('collapse',),
            'description': 'Nur für Bankkonten, nicht für Barkasse.'
        }),
        ('Notes', {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
    )

    def iban_display(self, obj):
        """Zeigt IBAN gekürzt oder Barkasse-Icon"""
        if obj.is_cash:
            return "💵 Barkasse"
        return f"...{obj.iban[-4:]}" if obj.iban else "-"
    iban_display.short_description = "IBAN"


admin.site.register(models.BankAccount, BankAccountAdmin)


class MatchingRuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'priority', 'conditions_preview',
                    'target_display', 'is_active')
    list_filter = ['is_active', 'target_transaction_type', 'target_renter']
    search_fields = ['name', 'match_iban', 'match_counterpart_name',
                     'match_booking_text', 'notes']
    autocomplete_fields = ['target_renter']
    ordering = ['-priority', 'name']
    actions = ['apply_rule_to_unmatched']
    fieldsets = (
        (None, {
            'fields': ('name', 'priority', 'is_active')
        }),
        ('Matching Conditions (AND-verknüpft)', {
            'fields': ('match_iban', 'match_counterpart_name',
                       'match_booking_text', 'match_amount_positive'),
            'description': 'Alle angegebenen Bedingungen müssen zutreffen (AND).'
        }),
        ('Target Assignment', {
            'fields': ('target_renter', 'target_transaction_type'),
            'description': 'Wenn Renter gesetzt, wird automatisch RENTER als Typ verwendet.'
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )

    def conditions_preview(self, obj):
        """Zeigt eine Vorschau der Bedingungen"""
        conditions = []
        if obj.match_iban:
            conditions.append(f"IBAN: ...{obj.match_iban[-4:]}")
        if obj.match_counterpart_name:
            conditions.append(f"Name: {obj.match_counterpart_name[:20]}")
        if obj.match_booking_text:
            conditions.append(f"Text: {obj.match_booking_text[:20]}")
        if obj.match_amount_positive is not None:
            conditions.append("+" if obj.match_amount_positive else "-")
        return " & ".join(conditions) if conditions else "-"
    conditions_preview.short_description = "Conditions"

    def target_display(self, obj):
        """Zeigt das Ziel der Regel"""
        if obj.target_renter:
            return f"🏠 {obj.target_renter.last_name}"
        return obj.get_target_transaction_type_display() if obj.target_transaction_type else "-"
    target_display.short_description = "Target"

    def apply_rule_to_unmatched(self, request, queryset):
        """
        Wendet die ausgewählten Regeln auf alle Transaktionen an,
        die noch den Typ 'Sonstige' (OTHER) haben.
        """
        # Hole alle nicht zugeordneten Transaktionen
        unmatched_transactions = models.BankTransaction.objects.filter(
            transaction_type=models.BankTransaction.TransactionType.OTHER
        )

        total_matched = 0
        for rule in queryset.filter(is_active=True):
            matched_count = 0
            for transaction in unmatched_transactions:
                # Prüfe ob die Regel matcht mit den korrekten Parametern
                if rule.matches(
                    iban=transaction.counterpart_iban or '',
                    counterpart_name=transaction.counterpart_name or '',
                    booking_text=transaction.booking_text or '',
                    amount=float(transaction.amount)
                ):
                    # Wende die Regel an
                    if rule.target_renter:
                        transaction.renter = rule.target_renter
                        transaction.transaction_type = models.BankTransaction.TransactionType.RENTER
                    elif rule.target_transaction_type:
                        transaction.transaction_type = rule.target_transaction_type

                    transaction.is_matched = True
                    transaction.matched_by_rule = rule
                    transaction.save()
                    matched_count += 1

            if matched_count > 0:
                self.message_user(
                    request,
                    f"✅ Regel '{rule.name}': {matched_count} Transaktionen zugeordnet",
                    level='SUCCESS'
                )
                total_matched += matched_count

        if total_matched == 0:
            self.message_user(
                request,
                "ℹ️ Keine passenden Transaktionen gefunden (nur 'Sonstige' werden geprüft).",
                level='WARNING'
            )
        else:
            self.message_user(
                request,
                f"🎯 Insgesamt {total_matched} Transaktionen zugeordnet.",
                level='SUCCESS'
            )

    apply_rule_to_unmatched.short_description = "Regel auf 'Sonstige' Transaktionen anwenden"


admin.site.register(models.MatchingRule, MatchingRuleAdmin)


class TransactionBillLinkInline(admin.TabularInline):
    """Inline für Bill-Links bei BankTransaction"""
    model = models.TransactionBillLink
    extra = 0
    fields = ['bill', 'amount', 'notes']
    autocomplete_fields = ['bill']


class BankTransactionAdmin(CSVImportAdminMixin, admin.ModelAdmin):
    list_display = ('formatted_date', 'amount_colored', 'counterpart_name_short',
                    'transaction_type', 'renter', 'accounting_year', 'is_matched', 'bank_account')
    list_filter = ['transaction_type', 'is_matched', 'accounting_year', 'bank_account',
                   'booking_date', 'renter']
    search_fields = ['counterpart_name',
                     'counterpart_iban', 'booking_text', 'notes']
    autocomplete_fields = ['bank_account', 'renter', 'matched_by_rule']
    date_hierarchy = 'booking_date'
    ordering = ['-booking_date', '-created_at']
    readonly_fields = ['import_hash', 'created_at', 'updated_at']
    inlines = [TransactionBillLinkInline]
    list_per_page = 50
    actions = ['auto_match_action',
               'mark_as_renter_transaction', 'mark_as_ignore']
    change_list_template = 'admin/bill/banktransaction/change_list.html'

    fieldsets = (
        ('Transaction Data', {
            'fields': ('bank_account', 'booking_date', 'value_date', 'amount', 'accounting_year')
        }),
        ('Counterpart', {
            'fields': ('counterpart_name', 'counterpart_iban', 'booking_text')
        }),
        ('Assignment', {
            'fields': ('transaction_type', 'renter', 'is_matched', 'matched_by_rule')
        }),
        ('Notes', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('import_hash', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def formatted_date(self, obj):
        """Zeigt Buchungsdatum im Format DD.MM.YYYY"""
        return obj.booking_date.strftime('%d.%m.%Y')
    formatted_date.short_description = 'Date'
    formatted_date.admin_order_field = 'booking_date'

    def amount_colored(self, obj):
        """Zeigt Betrag farbig (grün für Eingang, rot für Ausgang)"""
        from django.utils.html import format_html
        color = 'green' if obj.amount > 0 else 'red'
        formatted_amount = f"{obj.amount:+.2f}"
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} €</span>',
            color, formatted_amount
        )
    amount_colored.short_description = 'Amount'
    amount_colored.admin_order_field = 'amount'

    def counterpart_name_short(self, obj):
        """Zeigt gekürzten Counterpart-Namen"""
        if obj.counterpart_name:
            return obj.counterpart_name[:40] + ('...' if len(obj.counterpart_name) > 40 else '')
        return '-'
    counterpart_name_short.short_description = 'Counterpart'

    def auto_match_action(self, request, queryset):
        """Admin Action: Automatisches Matching durchführen"""
        matched = 0
        for obj in queryset.filter(is_matched=False):
            if obj.auto_match():
                obj.save()
                matched += 1
        self.message_user(
            request, f"{matched} Transaktionen erfolgreich zugeordnet.")
    auto_match_action.short_description = "Auto-Match durchführen"

    def mark_as_renter_transaction(self, request, queryset):
        """Admin Action: Als Mietertransaktion markieren"""
        count = queryset.update(
            transaction_type=models.BankTransaction.TransactionType.RENTER,
            is_matched=True
        )
        self.message_user(
            request, f"{count} Transaktionen als Mietertransaktion markiert.")
    mark_as_renter_transaction.short_description = "Als Mietertransaktion markieren"

    def mark_as_ignore(self, request, queryset):
        """Admin Action: Als ignoriert markieren"""
        count = queryset.update(
            transaction_type=models.BankTransaction.TransactionType.IGNORE,
            is_matched=True
        )
        self.message_user(
            request, f"{count} Transaktionen als ignoriert markiert.")
    mark_as_ignore.short_description = "Ignorieren"


admin.site.register(models.BankTransaction, BankTransactionAdmin)


class TransactionBillLinkAdmin(admin.ModelAdmin):
    list_display = ('transaction_date', 'transaction_amount', 'bill',
                    'amount', 'notes')
    list_filter = ['transaction__booking_date', 'bill__cost_center']
    search_fields = ['bill__text', 'bill__bill_number',
                     'transaction__counterpart_name', 'notes']
    autocomplete_fields = ['transaction', 'bill']
    ordering = ['-transaction__booking_date']

    def transaction_date(self, obj):
        """Zeigt Transaktionsdatum"""
        return obj.transaction.booking_date.strftime('%d.%m.%Y')
    transaction_date.short_description = 'Transaction Date'
    transaction_date.admin_order_field = 'transaction__booking_date'

    def transaction_amount(self, obj):
        """Zeigt Transaktionsbetrag"""
        from django.utils.html import format_html
        formatted_amount = f"{obj.transaction.amount:.2f}"
        return format_html(
            '<span style="color: red;">{} €</span>',
            formatted_amount
        )
    transaction_amount.short_description = 'Transaction Total'


admin.site.register(models.TransactionBillLink, TransactionBillLinkAdmin)


class YearlyAdjustmentAdmin(admin.ModelAdmin):
    list_display = ('billing_year', 'renter', 'description', 'amount_colored')
    list_filter = ['billing_year', 'renter']
    search_fields = ['description', 'renter__first_name', 'renter__last_name']
    autocomplete_fields = ['renter']
    ordering = ['-billing_year', 'renter__last_name']

    def amount_colored(self, obj):
        """Zeigt Betrag farbig an (grün=Gutschrift, rot=Abzug)"""
        from django.utils.html import format_html
        color = 'green' if obj.amount >= 0 else 'red'
        sign = '+' if obj.amount >= 0 else ''
        return format_html(
            '<span style="color: {};">{}{:.2f} €</span>',
            color, sign, obj.amount
        )
    amount_colored.short_description = 'Betrag'
    amount_colored.admin_order_field = 'amount'


admin.site.register(models.YearlyAdjustment, YearlyAdjustmentAdmin)
