from django.db import models
from django.utils.translation import gettext_lazy as _

from .renter import Renter
from .bank_transaction import BankTransaction


class MatchingRule(models.Model):
    """
    Flexible Zuordnungsregeln für automatisches Matching von Banktransaktionen.

    Bedingungen werden per AND verknüpft (alle angegebenen müssen zutreffen).
    Regeln werden nach Priorität absteigend ausgewertet.

    Beispiele:
    - IBAN=DE63... → Renter "Schwarz" (Direktzahlung)
    - counterpart_name contains "Kasse.Hamburg" AND booking_text contains "Schwarz, Dieter"
      → Renter "Schwarz" (Sozialamt-Zahlung)
    - counterpart_name contains "DKB AG" AND booking_text contains "Entgeltinformation"
      → transaction_type = IGNORE
    """

    name = models.CharField(
        max_length=100,
        verbose_name=_("Rule Name"),
        help_text=_("Beschreibung der Regel (z.B. 'Schwarz via Sozialamt')"))

    priority = models.PositiveIntegerField(
        default=100,
        verbose_name=_("Priority"),
        help_text=_("Höher = wird zuerst ausgewertet"))

    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Active"))

    # === BEDINGUNGEN (alle optional, AND-verknüpft) ===

    match_iban = models.CharField(
        max_length=34,
        blank=True,
        null=True,
        verbose_name=_("Match IBAN"),
        help_text=_("IBAN des Absenders/Empfängers (exakt)"))

    match_counterpart_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Match Counterpart Name"),
        help_text=_("Text im Namen des Absenders/Empfängers (contains, case-insensitive)"))

    match_booking_text = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Match Booking Text"),
        help_text=_("Text im Verwendungszweck (contains, case-insensitive)"))

    match_amount_positive = models.BooleanField(
        null=True,
        blank=True,
        verbose_name=_("Match Amount Direction"),
        help_text=_("True = nur Eingänge, False = nur Ausgänge, None = beide"))

    # === ZUORDNUNG (Ergebnis der Regel) ===

    target_renter = models.ForeignKey(
        Renter,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='matching_rules',
        verbose_name=_("Target Renter"),
        help_text=_("Mieter dem zugeordnet werden soll"))

    target_transaction_type = models.CharField(
        max_length=10,
        choices=BankTransaction.TransactionType.choices,
        null=True,
        blank=True,
        verbose_name=_("Target Transaction Type"),
        help_text=_("Transaktionstyp (wenn kein Renter, wird automatisch gesetzt)"))

    notes = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Notes"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Matching Rule")
        verbose_name_plural = _("Matching Rules")
        ordering = ['-priority', 'name']

    def __str__(self):
        target = self.target_renter.last_name if self.target_renter else self.target_transaction_type
        return f"{self.name} → {target} (Prio {self.priority})"

    def save(self, *args, **kwargs):
        if self.match_iban:
            self.match_iban = self.match_iban.replace(' ', '').upper()
        # Wenn Renter gesetzt, automatisch RENTER als Typ
        if self.target_renter and not self.target_transaction_type:
            self.target_transaction_type = BankTransaction.TransactionType.RENTER
        super().save(*args, **kwargs)

    def clean(self):
        from django.core.exceptions import ValidationError

        # Mindestens eine Bedingung muss gesetzt sein
        if not any([
            self.match_iban,
            self.match_counterpart_name,
            self.match_booking_text,
            self.match_amount_positive is not None
        ]):
            raise ValidationError(
                _("At least one matching condition must be specified."))

        # Mindestens ein Ziel muss gesetzt sein
        if not self.target_renter and not self.target_transaction_type:
            raise ValidationError(
                _("Either a target renter or transaction type must be specified."))

    def matches(self, iban: str, counterpart_name: str, booking_text: str, amount: float) -> bool:
        """
        Prüft ob die Regel auf die gegebenen Werte zutrifft.
        Alle gesetzten Bedingungen müssen erfüllt sein (AND).
        """
        # IBAN-Check (exakt)
        if self.match_iban:
            if not iban:
                return False
            if iban.replace(' ', '').upper() != self.match_iban:
                return False

        # Counterpart Name (contains, case-insensitive)
        if self.match_counterpart_name:
            if not counterpart_name:
                return False
            if self.match_counterpart_name.lower() not in counterpart_name.lower():
                return False

        # Booking Text (contains, case-insensitive)
        if self.match_booking_text:
            if not booking_text:
                return False
            if self.match_booking_text.lower() not in booking_text.lower():
                return False

        # Amount Direction
        if self.match_amount_positive is not None:
            is_positive = amount > 0
            if self.match_amount_positive != is_positive:
                return False

        return True

    @classmethod
    def find_matching_rule(cls, iban: str, counterpart_name: str, booking_text: str, amount: float):
        """
        Findet die erste passende Regel (nach Priorität sortiert).
        Returns: MatchingRule oder None
        """
        for rule in cls.objects.filter(is_active=True).order_by('-priority'):
            if rule.matches(iban, counterpart_name, booking_text, amount):
                return rule
        return None
