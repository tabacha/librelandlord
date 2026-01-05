"""
Admin-View für DKB CSV Import.
"""
from django import forms
from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.urls import path

from .models import BankAccount, BankTransaction
from .services import import_dkb_csv, DKBCSVImporter


class CSVImportForm(forms.Form):
    """Form für CSV-Upload"""
    csv_file = forms.FileField(
        label='DKB CSV Datei',
        help_text='Wählen Sie eine DKB Umsatzliste CSV-Datei aus.'
    )
    bank_account = forms.ModelChoiceField(
        queryset=BankAccount.objects.filter(account_type='BANK'),
        required=False,
        label='Bankkonto',
        help_text='Optional: Falls leer, wird das Konto anhand der IBAN in der CSV erkannt.'
    )
    auto_match = forms.BooleanField(
        initial=True,
        required=False,
        label='Auto-Match',
        help_text='Automatisches Zuordnen via Matching-Regeln durchführen.'
    )


class CSVImportAdminMixin:
    """
    Mixin für Admin-Klassen, um CSV-Import zu ermöglichen.

    Fügt eine 'Import CSV' URL und View hinzu.
    """

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                'import-csv/',
                self.admin_site.admin_view(self.import_csv_view),
                name='bill_banktransaction_import_csv'
            ),
        ]
        return custom_urls + urls

    def import_csv_view(self, request):
        """View für CSV-Import"""
        if request.method == 'POST':
            form = CSVImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv_file']
                bank_account = form.cleaned_data['bank_account']
                auto_match = form.cleaned_data['auto_match']

                # Speichere temporär die Datei
                import tempfile
                import os

                with tempfile.NamedTemporaryFile(mode='wb', delete=False, suffix='.csv') as tmp:
                    for chunk in csv_file.chunks():
                        tmp.write(chunk)
                    tmp_path = tmp.name

                try:
                    # Zeige CSV-Info
                    importer = DKBCSVImporter(auto_match=auto_match)
                    csv_account_name, csv_iban = importer.extract_account_info(
                        tmp_path)

                    # Import durchführen
                    result = import_dkb_csv(tmp_path, bank_account, auto_match)

                    # Ergebnis anzeigen
                    if result.imported > 0:
                        messages.success(
                            request,
                            f"✅ {result.imported} Transaktionen importiert "
                            f"(von {csv_account_name}, IBAN: {csv_iban})"
                        )

                    if result.auto_matched > 0:
                        messages.success(
                            request,
                            f"🎯 {result.auto_matched} Transaktionen automatisch zugeordnet"
                        )

                    if result.skipped_duplicates > 0:
                        messages.info(
                            request,
                            f"⏭️ {result.skipped_duplicates} Duplikate übersprungen"
                        )

                    if result.skipped_zero > 0:
                        messages.info(
                            request,
                            f"⏭️ {result.skipped_zero} Null-Beträge übersprungen"
                        )

                    if result.errors:
                        for error in result.errors[:5]:
                            messages.error(request, f"❌ {error}")
                        if len(result.errors) > 5:
                            messages.warning(
                                request,
                                f"... und {len(result.errors) - 5} weitere Fehler"
                            )

                finally:
                    # Temporäre Datei löschen
                    os.unlink(tmp_path)

                return redirect('admin:bill_banktransaction_changelist')
        else:
            form = CSVImportForm()

        context = {
            'form': form,
            'title': 'DKB CSV Import',
            'opts': self.model._meta,
            'available_accounts': BankAccount.objects.filter(account_type='BANK'),
        }
        return render(request, 'admin/bill/banktransaction/import_csv.html', context)

    def changelist_view(self, request, extra_context=None):
        """Fügt Import-Button zur Changelist hinzu"""
        extra_context = extra_context or {}
        extra_context['show_import_csv_button'] = True
        return super().changelist_view(request, extra_context)
