from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError

from .renter import Renter


class RentPayment(models.Model):
    """
    Model für die Miethöhe eines Mieters über einen bestimmten Zeitraum.

    Zeiträume dürfen sich nicht überlappen. Das end_date ist inklusiv,
    d.h. der letzte Tag an dem diese Miete gilt. Die nächste Periode
    muss am Folgetag beginnen.
    """
    renter = models.ForeignKey(
        Renter, on_delete=models.CASCADE,
        related_name='rent_payments',
        verbose_name=_("Renter"))
    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(
        null=True, blank=True,
        verbose_name=_("End Date"),
        help_text=_("Letzter Tag dieser Mietperiode. Leer lassen wenn noch aktiv."))
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
        constraints = [
            models.CheckConstraint(
                check=Q(end_date__isnull=True) | Q(end_date__gte=models.F('start_date')),
                name='rent_payment_end_date_after_start_date'
            ),
        ]

    def __str__(self):
        end = self.end_date.strftime('%d.%m.%Y') if self.end_date else 'heute'
        return f"{self.renter} - {self.start_date.strftime('%d.%m.%Y')} bis {end}: {self.total_rent} €"

    def clean(self):
        """Validiert dass sich Zeiträume nicht überlappen."""
        super().clean()

        if self.end_date and self.end_date < self.start_date:
            raise ValidationError({
                'end_date': _('Das Enddatum muss nach dem Startdatum liegen.')
            })

        # Prüfe auf Überlappungen mit anderen RentPayments desselben Mieters
        if self.renter_id:
            overlapping = RentPayment.objects.filter(renter_id=self.renter_id)

            # Eigenen Eintrag ausschließen bei Update
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)

            # Finde überlappende Perioden
            # Überlappung: (start1 <= end2) AND (end1 >= start2)
            # Bei offenem Ende (end_date=NULL) gilt: end = unendlich
            for other in overlapping:
                # Bestimme effektives Ende (NULL = weit in der Zukunft)
                from datetime import date
                my_end = self.end_date or date(9999, 12, 31)
                other_end = other.end_date or date(9999, 12, 31)

                # Prüfe Überlappung
                if self.start_date <= other_end and my_end >= other.start_date:
                    other_end_str = other.end_date.strftime('%d.%m.%Y') if other.end_date else 'offen'
                    raise ValidationError(
                        _('Überlappung mit bestehender Mietperiode: %(start)s - %(end)s'),
                        code='overlap',
                        params={
                            'start': other.start_date.strftime('%d.%m.%Y'),
                            'end': other_end_str
                        }
                    )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def total_rent(self):
        """Gesamtmiete (Kaltmiete + Vorauszahlung)"""
        return self.cold_rent + self.advance_payment
