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
    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.CASCADE, verbose_name=_("Cost Center"))
    apartment = models.ForeignKey(
        Apartment,  related_name="appartment", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Apartment"))
    special_designation = models.CharField(
        max_length=100, blank=True, default='', verbose_name=_("Special Designation"),
        help_text=_("Alternative designation when no apartment is selected (e.g. 'Washing Machine Counter')"))
    consumption_calc = models.ForeignKey(
        ConsumptionCalc, related_name="consumption_calc", on_delete=models.CASCADE, verbose_name=_("Consumption"))

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
        """Validation to ensure either apartment or special_designation is provided"""
        from django.core.exceptions import ValidationError

        if not self.apartment and not self.special_designation.strip():
            raise ValidationError(
                _("Either apartment or special designation must be provided"))

        if self.apartment and self.special_designation.strip():
            raise ValidationError(
                _("Cannot have both apartment and special designation"))

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
