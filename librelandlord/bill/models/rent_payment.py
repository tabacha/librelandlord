from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator

from .renter import Renter


class RentPayment(models.Model):
    """
    Model für die Miethöhe eines Mieters über einen bestimmten Zeitraum.
    """
    renter = models.ForeignKey(
        Renter, on_delete=models.CASCADE,
        related_name='rent_payments',
        verbose_name=_("Renter"))
    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(
        null=True, blank=True,
        verbose_name=_("End Date"),
        help_text=_("Leave empty if still active"))
    cold_rent = models.DecimalField(
        max_digits=8, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name=_("Cold Rent"),
        help_text=_("Monthly cold rent in EUR"))
    advance_payment = models.DecimalField(
        max_digits=8, decimal_places=2,
        validators=[MinValueValidator(0)],
        verbose_name=_("Advance Payment"),
        help_text=_("Monthly advance payment for utilities in EUR"))

    class Meta:
        verbose_name = _("Rent Payment")
        verbose_name_plural = _("Rent Payments")
        ordering = ['-start_date']

    def __str__(self):
        end = self.end_date.strftime('%d.%m.%Y') if self.end_date else 'heute'
        return f"{self.renter} - {self.start_date.strftime('%d.%m.%Y')} bis {end}: {self.total_rent} €"

    @property
    def total_rent(self):
        """Gesamtmiete (Kaltmiete + Vorauszahlung)"""
        return self.cold_rent + self.advance_payment
