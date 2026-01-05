from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from decimal import Decimal

from .bank_transaction import BankTransaction
from .bill import Bill


class TransactionBillLink(models.Model):
    """
    Verknüpfung zwischen Banktransaktion und Rechnung.

    Ermöglicht:
    - Teilzahlungen: Eine Bill wird durch mehrere Transaktionen bezahlt
    - Sammelüberweisungen: Eine Transaktion bezahlt mehrere Bills
    - Vorauszahlungen: Transaktion vor Bill-Erstellung

    Die Steuer-/Werbungskosten-Berechnung läuft über Bill → CostCenter,
    nicht über die Transaktion direkt.
    """

    transaction = models.ForeignKey(
        BankTransaction,
        on_delete=models.CASCADE,
        related_name='bill_links',
        verbose_name=_("Transaction"))

    bill = models.ForeignKey(
        Bill,
        on_delete=models.CASCADE,
        related_name='transaction_links',
        verbose_name=_("Bill"))

    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name=_("Amount"),
        help_text=_("Betrag dieser Verknüpfung (Teilzahlung möglich)"))

    notes = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Notes"),
        help_text=_("z.B. 'Anzahlung', '2. Rate', 'Teilbetrag'"))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Transaction-Bill Link")
        verbose_name_plural = _("Transaction-Bill Links")
        ordering = ['transaction__booking_date']

    def __str__(self):
        return f"{self.transaction.booking_date} → {self.bill} ({self.amount} €)"

    def clean(self):
        from django.core.exceptions import ValidationError

        # Prüfen ob Transaktion eine Ausgabe ist
        if self.transaction.amount > 0:
            raise ValidationError(
                _("Only expenses (negative amounts) can be linked to bills."))

    @classmethod
    def get_linked_total_for_bill(cls, bill: Bill) -> Decimal:
        """Summe aller verknüpften Zahlungen für eine Bill."""
        from django.db.models import Sum
        result = cls.objects.filter(bill=bill).aggregate(total=Sum('amount'))
        return result['total'] or Decimal('0')

    @classmethod
    def get_open_amount_for_bill(cls, bill: Bill) -> Decimal:
        """Noch offener Betrag einer Bill."""
        return bill.value - cls.get_linked_total_for_bill(bill)

    @classmethod
    def get_linked_total_for_transaction(cls, transaction: BankTransaction) -> Decimal:
        """Summe aller verknüpften Beträge für eine Transaktion."""
        from django.db.models import Sum
        result = cls.objects.filter(
            transaction=transaction).aggregate(total=Sum('amount'))
        return result['total'] or Decimal('0')

    @classmethod
    def get_unlinked_amount_for_transaction(cls, transaction: BankTransaction) -> Decimal:
        """Noch nicht verknüpfter Betrag einer Transaktion."""
        if transaction.amount >= 0:
            return Decimal('0')
        return abs(transaction.amount) - cls.get_linked_total_for_transaction(transaction)
