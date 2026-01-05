"""
Django Management Command zum Importieren von DKB CSV-Dateien.

Verwendung:
    python manage.py import_dkb_csv /pfad/zur/datei.csv
    python manage.py import_dkb_csv /pfad/zur/datei.csv --no-auto-match
    python manage.py import_dkb_csv /pfad/zur/datei.csv --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from bill.services import import_dkb_csv, DKBCSVImporter
from bill.models import BankAccount


class Command(BaseCommand):
    help = 'Importiert eine DKB CSV-Datei mit Banktransaktionen'

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_file',
            type=str,
            help='Pfad zur DKB CSV-Datei'
        )
        parser.add_argument(
            '--no-auto-match',
            action='store_true',
            help='Kein automatisches Matching via MatchingRules durchführen'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Nur validieren, nicht importieren'
        )
        parser.add_argument(
            '--account-id',
            type=int,
            help='BankAccount ID statt automatischer Erkennung via IBAN'
        )

    def handle(self, *args, **options):
        csv_file = options['csv_file']
        auto_match = not options['no_auto_match']
        dry_run = options['dry_run']
        account_id = options.get('account_id')

        self.stdout.write(f"Lese Datei: {csv_file}")

        # Zeige CSV-Infos
        importer = DKBCSVImporter(auto_match=auto_match)
        account_name, iban = importer.extract_account_info(csv_file)

        if not iban:
            raise CommandError("Konnte IBAN nicht aus CSV extrahieren!")

        self.stdout.write(f"  Kontoname: {account_name}")
        self.stdout.write(f"  IBAN:      {iban}")

        # BankAccount finden
        bank_account = None
        if account_id:
            try:
                bank_account = BankAccount.objects.get(id=account_id)
                self.stdout.write(f"  Verwende: {bank_account}")
            except BankAccount.DoesNotExist:
                raise CommandError(
                    f"BankAccount mit ID {account_id} nicht gefunden!")
        else:
            bank_account = BankAccount.get_by_iban(iban)
            if bank_account:
                self.stdout.write(
                    self.style.SUCCESS(f"  Gefunden: {bank_account}")
                )
            else:
                # Zeige verfügbare Konten
                self.stdout.write(
                    self.style.WARNING(
                        f"\n  Kein BankAccount mit IBAN {iban} gefunden!")
                )
                self.stdout.write("\n  Verfügbare Bankkonten:")
                for acc in BankAccount.objects.filter(account_type='BANK'):
                    self.stdout.write(f"    [{acc.id}] {acc.name}: {acc.iban}")

                self.stdout.write(
                    "\n  Bitte zuerst ein BankAccount mit dieser IBAN anlegen,"
                    " oder --account-id verwenden."
                )
                return

        if dry_run:
            self.stdout.write(self.style.NOTICE(
                "\n=== DRY RUN - Keine Änderungen ===\n"))

            # Zeige was importiert werden würde
            result = self._dry_run_analysis(csv_file, bank_account, importer)
            self.stdout.write(f"Zeilen im CSV:        {result['total']}")
            self.stdout.write(
                f"Würden importiert:    {result['would_import']}")
            self.stdout.write(f"Duplikate:            {result['duplicates']}")
            self.stdout.write(f"Null-Beträge:         {result['zeros']}")
            return

        # Import durchführen
        self.stdout.write("\nStarte Import...")
        result = import_dkb_csv(csv_file, bank_account, auto_match)

        # Ergebnis anzeigen
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("IMPORT ABGESCHLOSSEN")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Zeilen gesamt:        {result.total_rows}")
        self.stdout.write(
            self.style.SUCCESS(f"Importiert:           {result.imported}")
        )
        self.stdout.write(
            f"Übersprungen (Duplikat): {result.skipped_duplicates}")
        self.stdout.write(f"Übersprungen (0€):       {result.skipped_zero}")

        if auto_match:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Auto-Matched:         {result.auto_matched}")
            )
        else:
            self.stdout.write("Auto-Match:           deaktiviert")

        if result.errors:
            self.stdout.write(
                self.style.ERROR(f"\nFehler ({len(result.errors)}):")
            )
            for error in result.errors[:10]:  # Zeige max 10 Fehler
                self.stdout.write(f"  - {error}")
            if len(result.errors) > 10:
                self.stdout.write(
                    f"  ... und {len(result.errors) - 10} weitere Fehler"
                )

    def _dry_run_analysis(self, csv_file, bank_account, importer):
        """Analysiert CSV ohne zu importieren."""
        import csv
        import hashlib
        from bill.models import BankTransaction

        result = {
            'total': 0,
            'would_import': 0,
            'duplicates': 0,
            'zeros': 0,
        }

        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';', quotechar='"')

            # Überspringe Metadaten + Header (5 Zeilen: 1-4 Meta, 5 Header)
            for _ in range(5):
                next(reader, None)

            for row in reader:
                if len(row) < 9:
                    continue

                result['total'] += 1

                amount = importer.parse_german_amount(row[8])
                if amount == 0:
                    result['zeros'] += 1
                    continue

                booking_date = importer.parse_german_date(row[0])
                value_date = importer.parse_german_date(row[1])
                counterpart_iban = row[7].strip().replace(
                    ' ', '').upper() if len(row) > 7 and row[7] else ''
                booking_text = row[5] if len(row) > 5 else ''

                hash_data = (
                    f"{bank_account.id}|{booking_date}|{value_date}|"
                    f"{amount}|{counterpart_iban}|{booking_text[:100]}"
                )
                import_hash = hashlib.sha256(
                    hash_data.encode()).hexdigest()[:64]

                if BankTransaction.objects.filter(import_hash=import_hash).exists():
                    result['duplicates'] += 1
                else:
                    result['would_import'] += 1

        return result
