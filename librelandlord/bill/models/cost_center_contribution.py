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
    consumption_calc = models.ForeignKey(
        ConsumptionCalc, related_name="consumption_calc", on_delete=models.CASCADE, verbose_name=_("Consumption"))

    def __str__(self):
        return f"{self.cost_center} {self.apartment}"
