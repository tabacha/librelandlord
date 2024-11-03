from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator

from .apartment import Apartment
from .consumption_calc import ConsumptionCalc


class HeatingInfoTemplate(models.Model):
    apartment = models.ForeignKey(
        Apartment, on_delete=models.CASCADE, verbose_name=_("Appartment"))
    next_year = models.IntegerField(
        validators=[MinValueValidator(2023), MaxValueValidator(2300)])
    next_month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(12)])
    calc_heating = models.ForeignKey(
        ConsumptionCalc,
        on_delete=models.CASCADE,
        verbose_name=_("Consumption Heating"),
        related_name='calc_heating',
        blank=True,
        null=True
    )

    calc_hot_water = models.ForeignKey(
        ConsumptionCalc,
        on_delete=models.CASCADE,
        verbose_name=_("Consumption Hot Water"),
        related_name='calc_hot_water',
        blank=True,
        null=True
    )
    kwh_per_liter_hot_water = models.FloatField()
    compare_heating_group = models.IntegerField()
    compare_hot_water_group = models.IntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['apartment'],
                name='unique_rentrecord_per_apartment'
            )
        ]
        # Optionale Indexierung für bessere Abfrageleistung
        indexes = [
            models.Index(fields=['apartment'])
        ]

    def __str__(self):
        return f"{self.apartment}"
