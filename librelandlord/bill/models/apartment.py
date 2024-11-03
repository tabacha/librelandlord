from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator


# Define a model representing apartments.


class Apartment(models.Model):
    number = models.CharField(
        max_length=10, verbose_name=_("Apartment Number"))
    name = models.CharField(max_length=30, verbose_name=_("Apartment Name"))
    street = models.CharField(max_length=30, verbose_name=_("Street"))
    postal_code = models.CharField(
        max_length=10, verbose_name=_("Postal Code"))
    city = models.CharField(max_length=30, verbose_name=_("City"))
    size_in_m2 = models.DecimalField(
        max_digits=4, decimal_places=2, verbose_name=_("Size in Square Meters"))

    def __str__(self):
        return f"{self.number} {self.name}"
