from django.db import models
from django.utils.translation import gettext_lazy as _

from .cost_center import CostCenter
from .account_entry import AccountEntry

# Example:
# Costcenter: Wasserzäher
# Account_entry: Wasserkosten ohne Zählerkosten


class CostCenterBillEntry(models.Model):
    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.CASCADE, verbose_name=_("Cost Center"))
    account_entry = models.ForeignKey(
        AccountEntry, on_delete=models.CASCADE, verbose_name=_("Account Entry"))
    oil_in_liter = models.DecimalField(max_digits=8, decimal_places=0,
                                       verbose_name=_("Oil in Liter"), blank=True, null=True)

    def __str__(self):
        return f"{self.cost_center} {self.account_entry}"
