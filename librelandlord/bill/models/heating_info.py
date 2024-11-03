from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator

from .apartment import Apartment


class HeatingInfo(models.Model):
    apartment = models.ForeignKey(
        Apartment, on_delete=models.CASCADE, verbose_name=_("Appartment"))
    year = models.IntegerField(
        validators=[MinValueValidator(2023), MaxValueValidator(2300)])
    month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)])
    heating_energy_kwh = models.DecimalField(max_digits=8, decimal_places=0,
                                             verbose_name=_("Heating energy"), blank=True, null=True)
    compare_heating_energy_kwh = models.DecimalField(max_digits=8, decimal_places=0,
                                                     verbose_name=_("Compare Heating energy"), blank=True, null=True)
    hot_water_energy_kwh = models.DecimalField(max_digits=8, decimal_places=0,
                                               verbose_name=_("Hot water energy"), blank=True, null=True)
    compare_hot_water_energy_kwh = models.DecimalField(max_digits=8, decimal_places=0,
                                                       verbose_name=_("Compare hot water energy"), blank=True, null=True)
    hot_water_m3 = models.DecimalField(max_digits=8, decimal_places=0,
                                       verbose_name=_("Hot water m3"), blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['apartment', 'year', 'month'],
                name='unique_rentrecord_per_apartment_per_month'
            )
        ]
        # Optionale Indexierung für bessere Abfrageleistung
        indexes = [
            models.Index(fields=['apartment', 'year', 'month'])
        ]

    def __str__(self):
        return f"{self.apartment} - {self.month}/{self.year}"
