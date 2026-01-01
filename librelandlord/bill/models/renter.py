from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.core.validators import MinValueValidator, MaxValueValidator

from .apartment import Apartment

# Define a model representing renters.


class Renter(models.Model):
    apartment = models.ForeignKey(
        Apartment, on_delete=models.CASCADE, verbose_name=_("Apartment"))
    first_name = models.CharField(max_length=30, verbose_name=_("First Name"))
    last_name = models.CharField(max_length=30, verbose_name=_("Last Name"))
    alt_street = models.CharField(
        max_length=30, blank=True, null=True, verbose_name=_("Alternative Street"))
    postal_code = models.CharField(
        max_length=10, blank=True, null=True, verbose_name=_("Postal Code"))
    city = models.CharField(max_length=30, blank=True,
                            null=True, verbose_name=_("City"))
    move_in_date = models.DateField(verbose_name=_("Move in on date"))
    move_out_date = models.DateField(
        null=True, blank=True, verbose_name=_("Move out date"))
    is_owner_occupied = models.BooleanField(
        default=False,
        verbose_name=_("Owner occupied"),
        help_text=_("Check if this unit is occupied by the owner or family members. "
                    "These are not considered rental income for tax purposes."))

    def __str__(self):
        return f"{self.first_name} {self.last_name} {self.apartment}"
