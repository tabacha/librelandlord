from django.db import models
from django.utils.translation import gettext_lazy as _


class Bill(models.Model):
    text = models.CharField(max_length=60, verbose_name=_("Booking Text"))
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

    paperless_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name=_("Paperless ID"),
        help_text=_("ID des Dokuments in Paperless-NGX"))

    show_in_tax_overview = models.BooleanField(
        default=True,
        verbose_name=_("Show in tax overview"),
        help_text=_("If checked, this bill will appear in the tax overview for the landlord."))

    def __str__(self):
        return f"{self.bill_date} {self.text} {self.value}"
