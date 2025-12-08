from django.db import models
from django.utils.translation import gettext_lazy as _


class Bill(models.Model):
    text = models.CharField(max_length=40, verbose_name=_("Booking Text"))
    bill_date = models.DateField(verbose_name=_("Date"))
    bill_number = models.CharField(
        max_length=20, verbose_name=_("Bill number"))
    value = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Value"))
    from_date = models.DateField(
        verbose_name=_("From Date"))
    to_date = models.DateField(
        verbose_name=_("To Date"))

    cost_center = models.ForeignKey(
        'CostCenter', on_delete=models.CASCADE, verbose_name=_("Cost Center"))
    account_period = models.ForeignKey(
        'AccountPeriod', on_delete=models.CASCADE, verbose_name=_("Account Period"))

    def __str__(self):
        return f"{self.bill_date} {self.text} {self.value}"
