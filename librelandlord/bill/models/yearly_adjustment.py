from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator

from .renter import Renter


class YearlyAdjustment(models.Model):
    """
    Model für zusätzliche Posten in der Jahresabrechnung.

    Beispiele:
    - Schlüssel verloren: -20,00 € (Abzug vom Mieter-Guthaben)
    - Streusalz gekauft: +5,00 € (Gutschrift für Mieter)
    - Kaution erhalten: +500,00 €
    - Kaution zurückgezahlt: -500,00 €
    """
    renter = models.ForeignKey(
        Renter, on_delete=models.CASCADE,
        related_name='yearly_adjustments',
        verbose_name=_("Renter"))
    billing_year = models.PositiveSmallIntegerField(
        verbose_name=_("Billing Year"),
        validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    description = models.CharField(
        max_length=200,
        verbose_name=_("Description"),
        help_text=_("z.B. 'Schlüssel verloren', 'Streusalz', 'Kaution'"))
    amount = models.DecimalField(
        max_digits=10, decimal_places=2,
        verbose_name=_("Amount"),
        help_text=_("Positiv = Gutschrift für Mieter, Negativ = Abzug"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Yearly Adjustment")
        verbose_name_plural = _("Yearly Adjustments")
        ordering = ['billing_year', 'renter', 'description']
        indexes = [
            models.Index(fields=['billing_year']),
            models.Index(fields=['renter']),
        ]

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f"{self.renter} ({self.billing_year}): {self.description} {sign}{self.amount} €"
