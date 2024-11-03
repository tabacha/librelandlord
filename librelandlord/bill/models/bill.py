from django.db import models
from django.utils.translation import gettext_lazy as _


class Bill(models.Model):
    text = models.CharField(max_length=40, verbose_name=_("Booking Text"))
    date = models.DateField(verbose_name=_("Date"))
    bill_number = models.CharField(
        max_length=15, verbose_name=_("Bill number"))
    value = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Value"))

    def __str__(self):
        return f"{self.date} {self.text} {self.value}"
