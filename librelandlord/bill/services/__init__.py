"""
DKB CSV Import Service für Banktransaktionen.

Das DKB CSV-Format hat folgende Struktur:
- Zeile 1: Kontoname; IBAN
- Zeile 2: "Zeitraum:"; "DD.MM.YYYY - DD.MM.YYYY"
- Zeile 3: "Kontostand vom DD.MM.YYYY:"; "X.XXX,XX €"
- Zeile 4: leer
- Zeile 5: Header-Zeile
- Ab Zeile 6: Daten

Spalten:
0: Buchungsdatum (DD.MM.YY)
1: Wertstellung (DD.MM.YY)
2: Status ("Gebucht")
3: Zahlungspflichtige*r
4: Zahlungsempfänger*in
5: Verwendungszweck
6: Umsatztyp ("Eingang"/"Ausgang")
7: IBAN
8: Betrag (deutsches Format: "1.500" oder "-137")
9: Gläubiger-ID
10: Mandatsreferenz
11: Kundenreferenz
"""

import csv
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Tuple, List, Optional
from dataclasses import dataclass

from django.db import transaction

from ..models import BankAccount, BankTransaction, MatchingRule


@dataclass
class ImportResult:
    """Ergebnis eines CSV-Imports."""
    total_rows: int = 0
    imported: int = 0
    skipped_duplicates: int = 0
    skipped_zero: int = 0
    auto_matched: int = 0
    errors: List[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class DKBCSVImporter:
    """Importiert DKB CSV-Kontoauszüge."""

    # Regex für deutsche Datumsformate
    DATE_PATTERN_SHORT = re.compile(r'^(\d{2})\.(\d{2})\.(\d{2})$')  # DD.MM.YY
    DATE_PATTERN_LONG = re.compile(
        r'^(\d{2})\.(\d{2})\.(\d{4})$')   # DD.MM.YYYY

    def __init__(self, auto_match: bool = True):
        """
        Args:
            auto_match: Soll automatisches Matching via MatchingRules durchgeführt werden?
        """
        self.auto_match = auto_match

    def parse_german_date(self, date_str: str) -> Optional[datetime]:
        """Parst ein deutsches Datum (DD.MM.YY oder DD.MM.YYYY)."""
        if not date_str:
            return None

        date_str = date_str.strip().strip('"')

        # Versuche DD.MM.YY
        match = self.DATE_PATTERN_SHORT.match(date_str)
        if match:
            day, month, year = match.groups()
            # Konvertiere 2-stelliges Jahr zu 4-stellig
            year_int = int(year)
            if year_int < 50:
                year_int += 2000
            else:
                year_int += 1900
            return datetime(year_int, int(month), int(day)).date()

        # Versuche DD.MM.YYYY
        match = self.DATE_PATTERN_LONG.match(date_str)
        if match:
            day, month, year = match.groups()
            return datetime(int(year), int(month), int(day)).date()

        return None

    def parse_german_amount(self, amount_str: str) -> Optional[Decimal]:
        """
        Parst einen deutschen Geldbetrag.
        Beispiele: "1.500" -> 1500.00, "-137" -> -137.00, "3.898,43" -> 3898.43
        """
        if not amount_str:
            return None

        amount_str = amount_str.strip().strip('"')

        # Entferne € Zeichen und Leerzeichen
        amount_str = amount_str.replace('€', '').replace(' ', '').strip()

        if not amount_str:
            return None

        try:
            # Deutsches Format: Punkt als Tausendertrennzeichen, Komma als Dezimaltrennzeichen
            # Entferne Tausendertrennzeichen (Punkte) und ersetze Komma durch Punkt
            amount_str = amount_str.replace('.', '').replace(',', '.')
            return Decimal(amount_str)
        except (InvalidOperation, ValueError):
            return None

    def extract_account_info(self, file_path: str) -> Tuple[str, str]:
        """
        Extrahiert Kontoname und IBAN aus den ersten Zeilen der CSV.

        Returns:
            Tuple (account_name, iban)
        """
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';', quotechar='"')
            first_row = next(reader)

            if len(first_row) >= 2:
                account_name = first_row[0].strip()
                iban = first_row[1].strip().replace(' ', '').upper()
                return account_name, iban

        return None, None

    def import_csv(self, file_path: str, bank_account: BankAccount = None) -> ImportResult:
        """
        Importiert eine DKB CSV-Datei.

        Args:
            file_path: Pfad zur CSV-Datei
            bank_account: Optional - BankAccount zu verwenden.
                          Wenn None, wird versucht das Konto anhand der IBAN zu finden.

        Returns:
            ImportResult mit Statistiken
        """
        result = ImportResult()

        # Extrahiere Kontoinformationen aus CSV
        csv_account_name, csv_iban = self.extract_account_info(file_path)

        if not csv_iban:
            result.errors.append("Konnte IBAN nicht aus CSV extrahieren.")
            return result

        # Finde oder validiere BankAccount
        if bank_account is None:
            bank_account = BankAccount.get_by_iban(csv_iban)
            if bank_account is None:
                result.errors.append(
                    f"Kein BankAccount mit IBAN {csv_iban} gefunden. "
                    f"Bitte zuerst anlegen."
                )
                return result
        else:
            # Validiere dass IBAN übereinstimmt
            if bank_account.iban and bank_account.iban != csv_iban:
                result.errors.append(
                    f"IBAN Mismatch: CSV hat {csv_iban}, "
                    f"BankAccount hat {bank_account.iban}"
                )
                return result

        # Lese und importiere Transaktionen
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';', quotechar='"')

            # Überspringe Metadaten-Zeilen (Zeile 1-4: Kontoinfo, Zeitraum, Kontostand, leer)
            for _ in range(4):
                next(reader, None)

            # Lese Header-Zeile (Zeile 5)
            header = next(reader, None)
            if not header:
                result.errors.append("Keine Header-Zeile gefunden.")
                return result

            # Importiere Datenzeilen (ab Zeile 6)
            with transaction.atomic():
                for row_num, row in enumerate(reader, start=6):
                    result.total_rows += 1

                    if len(row) < 9:
                        result.errors.append(
                            f"Zeile {row_num}: Zu wenige Spalten ({len(row)})")
                        continue

                    try:
                        trans = self._parse_row(
                            row, bank_account, row_num, result)
                        if trans:
                            # Auto-Match durchführen
                            if self.auto_match:
                                if trans.auto_match():
                                    result.auto_matched += 1

                            trans.save()
                            result.imported += 1

                    except Exception as e:
                        result.errors.append(f"Zeile {row_num}: {str(e)}")

        return result

    def _parse_row(
        self,
        row: list,
        bank_account: BankAccount,
        row_num: int,
        result: ImportResult
    ) -> Optional[BankTransaction]:
        """
        Parst eine CSV-Zeile und erstellt eine BankTransaction.

        Returns:
            BankTransaction oder None wenn übersprungen
        """
        # Spalten extrahieren
        booking_date_str = row[0]
        value_date_str = row[1]
        # status = row[2]  # "Gebucht" - wird nicht benötigt
        payer = row[3]
        payee = row[4]
        purpose = row[5]
        # transaction_type = row[6]  # "Eingang"/"Ausgang" - wird über Betrag ermittelt
        counterpart_iban = row[7] if len(row) > 7 else ''
        amount_str = row[8] if len(row) > 8 else ''

        # Parse Datum
        booking_date = self.parse_german_date(booking_date_str)
        value_date = self.parse_german_date(value_date_str)

        if not booking_date:
            result.errors.append(
                f"Zeile {row_num}: Ungültiges Buchungsdatum '{booking_date_str}'")
            return None

        if not value_date:
            value_date = booking_date  # Fallback

        # Parse Betrag
        amount = self.parse_german_amount(amount_str)
        if amount is None:
            result.errors.append(
                f"Zeile {row_num}: Ungültiger Betrag '{amount_str}'")
            return None

        # Überspringe 0-Beträge (z.B. DKB Entgeltinformationen)
        if amount == 0:
            result.skipped_zero += 1
            return None

        # Bestimme Counterpart basierend auf Ein-/Ausgang
        if amount > 0:
            # Eingang: Payer ist der Counterpart
            counterpart_name = payer
        else:
            # Ausgang: Payee ist der Counterpart
            counterpart_name = payee

        # Normalisiere IBAN
        if counterpart_iban:
            counterpart_iban = counterpart_iban.strip().replace(' ', '').upper()
            # Ignoriere ungültige IBANs wie "0000000000" oder "1202197727"
            if len(counterpart_iban) < 15 or counterpart_iban.startswith('0000'):
                counterpart_iban = None

        # Erstelle Transaction (noch nicht gespeichert)
        trans = BankTransaction(
            bank_account=bank_account,
            booking_date=booking_date,
            value_date=value_date,
            amount=amount,
            counterpart_name=counterpart_name.strip() if counterpart_name else None,
            counterpart_iban=counterpart_iban,
            booking_text=purpose.strip() if purpose else '',
        )

        # Generiere Import-Hash für Duplikat-Check
        # Wir müssen den Hash manuell generieren, da bank_account_id noch nicht gesetzt ist
        import hashlib
        hash_data = (
            f"{bank_account.id}|"
            f"{trans.booking_date}|"
            f"{trans.value_date}|"
            f"{trans.amount}|"
            f"{trans.counterpart_iban or ''}|"
            f"{trans.booking_text[:100] if trans.booking_text else ''}"
        )
        trans.import_hash = hashlib.sha256(hash_data.encode()).hexdigest()[:64]

        # Prüfe auf Duplikat
        if BankTransaction.objects.filter(import_hash=trans.import_hash).exists():
            result.skipped_duplicates += 1
            return None

        return trans


def import_dkb_csv(file_path: str, bank_account: BankAccount = None, auto_match: bool = True) -> ImportResult:
    """
    Convenience-Funktion zum Importieren einer DKB CSV-Datei.

    Args:
        file_path: Pfad zur CSV-Datei
        bank_account: Optional - BankAccount zu verwenden
        auto_match: Soll automatisches Matching durchgeführt werden?

    Returns:
        ImportResult mit Statistiken
    """
    importer = DKBCSVImporter(auto_match=auto_match)
    return importer.import_csv(file_path, bank_account)
