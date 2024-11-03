from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError

from .meter_place import MeterPlace


class Meter(models.Model):

    # Define fields for the Meter model
    place = models.ForeignKey(
        MeterPlace, on_delete=models.CASCADE, verbose_name=_("Meter Place"))
    remark = models.CharField(max_length=40, verbose_name=_(
        "Remark"), blank=True, default='')
    meter_number = models.CharField(
        max_length=30, verbose_name=_("Meter Number"))

    build_in_date = models.DateField(verbose_name=_("Build-in Date"))
    calibrated_until_date = models.DateField(
        verbose_name=_("Calibrated until"))
    out_of_order_date = models.DateField(
        null=True, blank=True, verbose_name=_("Out of Order Date"))

    class Meta:
        constraints = [
            # Sicherstellen, dass build_in_date immer vor out_of_order_date liegt
            models.CheckConstraint(
                check=Q(out_of_order_date__gt=models.F("build_in_date")) | Q(
                    out_of_order_date__isnull=True),
                name="check_build_in_before_out_of_order",
            ),
            # Sicherstellen, dass nur ein aktiver Zähler pro MeterPlace existiert
            models.UniqueConstraint(
                fields=["place"],
                condition=Q(out_of_order_date__isnull=True),
                name="unique_active_meter_per_place",
            ),
        ]

    def __str__(self):
        if self.out_of_order_date is None:
            return f"{self.place.name} {self.meter_number} from: {self.build_in_date:%Y-%m-%d}"
        return f"{self.place.name} {self.meter_number} ooo: {self.out_of_order_date:%Y-%m-%d}"
