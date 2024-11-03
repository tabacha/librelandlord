from django.db import models
from django.utils.translation import gettext_lazy as _
# Define a model representing a place where meters are installed.


class MeterPlace(models.Model):
    # Define choices for the type of meter
    class MeterType(models.TextChoices):
        ELECTRICITY = 'EL', _('electricity')
        GAS = 'GA', _('gas')
        COLDWATER = 'KW', _('cold water')
        WARMWATER = 'WW', _('warm water')
        HEAT = 'HE', _('heating')
        OIL = 'OI', _('fuel oil')
    type = models.CharField(
        max_length=2,
        choices=MeterType.choices,
        verbose_name=_("Meter Type")
    )
    name = models.CharField(
        max_length=50, verbose_name=_("Name of the Meter Place"))
    remark = models.CharField(
        max_length=40, verbose_name=_("Remark"), default='', blank=True)
    location = models.CharField(
        max_length=200, verbose_name=_("Location"), default='')

    def __str__(self):
        return self.name+' '+self.type+' '+self.location
