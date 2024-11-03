from django.db import models
from django.utils.translation import gettext_lazy as _
from .bill import Bill
from .account_period import AccountPeriod

# Define a model representing account entries.


class AccountEntry(models.Model):
    # Define fields for the AccountEntry model.
    date = models.DateField(verbose_name=_("Date"))
    text = models.CharField(max_length=30, verbose_name=_("Text"))
    value = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Value"))
    bill = models.ForeignKey(
        Bill,   on_delete=models.CASCADE, verbose_name=_("Bill"))
    account_period = models.ForeignKey(
        AccountPeriod, on_delete=models.CASCADE, verbose_name=_(
            "Account Period"))

    def __str__(self):
        return f"{self.date} {self.value}"
