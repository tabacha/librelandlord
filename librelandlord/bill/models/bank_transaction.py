from django.db import models
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import date
import hashlib

from .bank_account import BankAccount
from .renter import Renter


class BankTransaction(models.Model):
    """
    Banktransaktion oder Barkassen-Buchung - direkt aus CSV importierbar.

    Hauptszenarien:
    1. EINNAHMEN: Mieteinnahmen → renter wird zugeordnet
    2. AUSGABEN: Kosten → Verknüpfung mit Bill(s) über TransactionBillLink
    3. BARKASSE: Manuelle Buchungen ohne IBAN

    KEIN Kalt/Warm-Split hier - das wird in der Jahresabrechnung ermittelt!
    """

    class TransactionType(models.TextChoices):
        """Grobe Kategorisierung für Übersicht und Auswertung"""
        RENTER = 'RENTER', _('Mietertransaktion')
        EXPENSE = 'EXPENSE', _('Ausgabe')
        TRANSFER = 'TRANSFER', _('Umbuchung')
        IGNORE = 'IGNORE', _('Ignorieren')
        OTHER = 'OTHER', _('Sonstige')

    # === Konto ===
    bank_account = models.ForeignKey(
        BankAccount,
        on_delete=models.PROTECT,
        related_name='transactions',
        verbose_name=_("Bank Account / Cash Box"))

    # === Daten aus CSV oder manuelle Eingabe ===
    booking_date = models.DateField(
        verbose_name=_("Booking Date"),
        help_text=_("Buchungsdatum"))

    value_date = models.DateField(
        verbose_name=_("Value Date"),
        help_text=_("Wertstellungsdatum"))

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Amount"),
        help_text=_("Positiv = Eingang, Negativ = Ausgang"))

    counterpart_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Counterpart Name"),
        help_text=_("Zahlungspflichtiger/Empfänger"))

    counterpart_iban = models.CharField(
        max_length=34,
        blank=True,
        null=True,
        verbose_name=_("Counterpart IBAN"))

    booking_text = models.TextField(
        max_length=1000,
        verbose_name=_("Booking Text"),
        help_text=_("Verwendungszweck"))

    csv_transaction_type = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("CSV Transaction Type"),
        help_text=_("'Eingang'/'Ausgang' aus CSV"))

    # === Zuordnung ===
    transaction_type = models.CharField(
        max_length=10,
        choices=TransactionType.choices,
        default=TransactionType.OTHER,
        verbose_name=_("Transaction Type"))

    renter = models.ForeignKey(
        Renter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bank_transactions',
        verbose_name=_("Renter"),
        help_text=_("Bei Mieteinnahmen: zugeordneter Mieter"))

    # === Status ===
    is_matched = models.BooleanField(
        default=False,
        verbose_name=_("Matched"),
        help_text=_("Automatisch oder manuell zugeordnet"))

    matched_by_rule = models.ForeignKey(
        'MatchingRule',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Matched by Rule"),
        help_text=_("Die Regel die das Matching durchgeführt hat"))

    # === Duplikat-Check ===
    import_hash = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
        null=True,
        verbose_name=_("Import Hash"),
        help_text=_("Hash für Duplikat-Erkennung beim Import"))

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes"))

    accounting_year = models.PositiveSmallIntegerField(
        verbose_name=_("Accounting Year"),
        help_text=_("Für welches Abrechnungsjahr ist diese Transaktion relevant? Default: Jahr des Wertstellungsdatums"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Bank Transaction")
        verbose_name_plural = _("Bank Transactions")
        ordering = ['-booking_date', '-created_at']
        indexes = [
            models.Index(fields=['booking_date']),
            models.Index(fields=['counterpart_iban']),
            models.Index(fields=['renter']),
            models.Index(fields=['is_matched']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['accounting_year']),
        ]

    def __str__(self):
        type_icon = "💵" if self.bank_account.is_cash else "🏦"
        return f"{type_icon} {self.booking_date} | {self.amount:+.2f} € | {self.counterpart_name or 'N/A'}"

    def save(self, *args, **kwargs):
        if self.counterpart_iban:
            self.counterpart_iban = self.counterpart_iban.replace(
                ' ', '').upper()
        if not self.import_hash and not self.bank_account.is_cash:
            self.import_hash = self._generate_import_hash()
        # Default accounting_year from value_date if not set
        if self.accounting_year is None and self.value_date:
            self.accounting_year = self.value_date.year
        super().save(*args, **kwargs)

    def _generate_import_hash(self) -> str:
        """Generiert einen Hash für Duplikat-Erkennung beim Import."""
        data = (
            f"{self.bank_account_id}|"
            f"{self.booking_date}|"
            f"{self.value_date}|"
            f"{self.amount}|"
            f"{self.counterpart_iban or ''}|"
            f"{self.booking_text[:100] if self.booking_text else ''}"
        )
        return hashlib.sha256(data.encode()).hexdigest()[:64]

    def auto_match(self) -> bool:
        """
        Versucht automatische Zuordnung via MatchingRules.
        Returns: True wenn erfolgreich gematcht
        """
        from .matching_rule import MatchingRule

        rule = MatchingRule.find_matching_rule(
            iban=self.counterpart_iban,
            counterpart_name=self.counterpart_name,
            booking_text=self.booking_text,
            amount=float(self.amount)
        )

        if rule:
            self.matched_by_rule = rule
            self.is_matched = True

            if rule.target_renter:
                self.renter = rule.target_renter

            if rule.target_transaction_type:
                self.transaction_type = rule.target_transaction_type

            return True

        return False

    @property
    def is_income(self) -> bool:
        return self.amount > 0

    @property
    def is_expense(self) -> bool:
        return self.amount < 0

    @property
    def is_rental_income(self) -> bool:
        """Ist dies eine Mieteinnahme?"""
        return self.renter is not None and self.amount > 0

    @property
    def is_owner_occupied_payment(self) -> bool:
        """Ist dies eine Zahlung für eigengenutzte Wohnung?"""
        return self.renter and self.renter.is_owner_occupied

    @property
    def is_fully_linked_to_bills(self) -> bool:
        """Prüft ob der Transaktionsbetrag vollständig mit Bills verknüpft ist."""
        if self.amount >= 0:
            return True  # Nur für Ausgaben relevant
        linked_total = sum(
            link.amount for link in self.bill_links.all()
        )
        return abs(linked_total - abs(self.amount)) < Decimal('0.01')

    @property
    def unlinked_amount(self) -> Decimal:
        """Noch nicht mit Bills verknüpfter Betrag."""
        if self.amount >= 0:
            return Decimal('0')
        linked_total = sum(link.amount for link in self.bill_links.all())
        return abs(self.amount) - linked_total

    # === Klassenweite Auswertungen ===

    @classmethod
    def get_rental_income_for_year(cls, year: int, exclude_owner_occupied: bool = True) -> dict:
        """
        Mieteinnahmen für Steuererklärung (Anlage V Zeile 9).

        Returns:
            {
                'total': Decimal,      # Gesamte Mieteinnahmen
                'by_renter': [...],    # Aufschlüsselung nach Mieter
            }
        """
        from django.db.models import Sum

        start = date(year, 1, 1)
        end = date(year, 12, 31)

        qs = cls.objects.filter(
            booking_date__gte=start,
            booking_date__lte=end,
            transaction_type=cls.TransactionType.RENTER,
            renter__isnull=False
        )

        if exclude_owner_occupied:
            qs = qs.exclude(renter__is_owner_occupied=True)

        total = qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')

        by_renter = qs.values(
            'renter__first_name',
            'renter__last_name',
            'renter__apartment__name'
        ).annotate(
            total=Sum('amount')
        ).order_by('renter__last_name')

        return {
            'total': total,
            'by_renter': list(by_renter)
        }

    @classmethod
    def get_unmatched_transactions(cls):
        """Gibt alle noch nicht zugeordneten Transaktionen zurück."""
        return cls.objects.filter(
            is_matched=False,
            transaction_type=cls.TransactionType.OTHER
        ).order_by('-booking_date')

    @classmethod
    def get_account_balance(cls, bank_account, as_of_date: date = None) -> Decimal:
        """Berechnet den Kontostand basierend auf allen Transaktionen."""
        from django.db.models import Sum

        qs = cls.objects.filter(bank_account=bank_account)
        if as_of_date:
            qs = qs.filter(booking_date__lte=as_of_date)

        return qs.aggregate(total=Sum('amount'))['total'] or Decimal('0')
