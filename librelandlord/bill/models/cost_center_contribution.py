from django.db import models
from django.utils.translation import gettext_lazy as _

from .cost_center import CostCenter
from .apartment import Apartment
from .consumption_calc import ConsumptionCalc

# Example
# Costcenter: Wasserzäher
# Flat: Wohnung Ost
# Consuption_cost: Wasserzählerberechung Ost


class CostCenterContribution(models.Model):
    """
    Definiert wie eine Wohnung an einem CostCenter beteiligt ist.

    Distribution Types:
    - CONSUMPTION: Anteil nach consumption_calc Ergebnis (z.B. Wasser nach Zähler)
    - TIME: Anteil nach Tagen, aufgeteilt bei Mieterwechsel (z.B. Müll, Internet)
    - AREA: Anteil nach m², aufgeteilt bei Mieterwechsel (z.B. Grundsteuer)
    - DIRECT: Bill geht 1:1 an den Mieter im Bill-Zeitraum (z.B. Waschvorgänge)
    """

    class DistributionType(models.TextChoices):
        CONSUMPTION = 'CONSUMPTION', _('Consumption based (meter reading)')
        TIME = 'TIME', _('By time (days)')
        AREA = 'AREA', _('By area (m²)')
        DIRECT = 'DIRECT', _('Direct assignment (bill period = renter)')

    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.CASCADE, verbose_name=_("Cost Center"))
    apartment = models.ForeignKey(
        Apartment, related_name="appartment", on_delete=models.CASCADE,
        blank=True, null=True, verbose_name=_("Apartment"))
    special_designation = models.CharField(
        max_length=100, blank=True, default='', verbose_name=_("Special Designation"),
        help_text=_("Alternative designation when no apartment is selected (e.g. 'Washing Machine Counter')"))

    distribution_type = models.CharField(
        max_length=20,
        choices=DistributionType.choices,
        default=DistributionType.CONSUMPTION,
        verbose_name=_("Distribution Type"),
        help_text=_(
            "CONSUMPTION: by meter, TIME: by days, AREA: by m², DIRECT: bill goes to renter in bill period")
    )

    consumption_calc = models.ForeignKey(
        ConsumptionCalc, related_name="consumption_calc", on_delete=models.CASCADE,
        blank=True, null=True,
        verbose_name=_("Consumption Calculation"),
        help_text=_("Required for consumption-based distribution"))

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(apartment__isnull=False) | models.Q(
                    special_designation__gt=''),
                name="apartment_or_special_designation_required",
                violation_error_message=_(
                    "Either apartment or special designation must be provided")
            )
        ]

    def clean(self):
        """Validation to ensure correct field combinations"""
        from django.core.exceptions import ValidationError

        if not self.apartment and not self.special_designation.strip():
            raise ValidationError(
                _("Either apartment or special designation must be provided"))

        if self.apartment and self.special_designation.strip():
            raise ValidationError(
                _("Cannot have both apartment and special designation"))

        # Distribution type specific validation
        if self.distribution_type == self.DistributionType.CONSUMPTION and not self.consumption_calc:
            raise ValidationError(
                _("Consumption calculation is required for consumption-based distribution"))

        if self.distribution_type == self.DistributionType.AREA and not self.apartment:
            raise ValidationError(
                _("Area-based distribution requires an apartment"))

        if self.distribution_type == self.DistributionType.DIRECT and not self.apartment:
            raise ValidationError(
                _("Direct distribution requires an apartment"))

    def get_display_name(self):
        """Returns the display name for this contribution"""
        if self.apartment:
            return self.apartment.name
        elif self.special_designation:
            return self.special_designation
        else:
            return "Unbekannt"

    def __str__(self):
        display_name = self.get_display_name()
        return f"{self.cost_center} - {display_name}"
