from django.db import models
from django.utils.translation import gettext_lazy as _

# Define a model representing a place where meters are installed.


class MeterPlace(models.Model):
    name = models.CharField(
        max_length=30, verbose_name=_("Name of the Meter Place"))

    def __str__(self):
        return self.name

# Define a model representing different types of meters.


class Meter(models.Model):
    # Define choices for the type of meter
    class MeterType(models.TextChoices):
        ELECTRICITY = 'EL', _('electricity')
        GAS = 'GA', _('gas')
        COLDWATER = 'KW', _('cold water')
        WARMWATER = 'WW', _('warm water')
        HEAT = 'HE', _('heating')
        OIL = 'OI', _('fuel oil')

    # Define fields for the Meter model
    place = models.ForeignKey(
        MeterPlace, on_delete=models.CASCADE, verbose_name=_("Meter Place"))
    remark = models.CharField(max_length=40, verbose_name=_("Remark"))
    meter_number = models.CharField(
        max_length=30, verbose_name=_("Meter Number"))
    type = models.CharField(
        max_length=2,
        choices=MeterType.choices,
        verbose_name=_("Meter Type")
    )
    build_in_date = models.DateField(verbose_name=_("Build-in Date"))
    out_of_order_date = models.DateField(
        null=True, blank=True, verbose_name=_("Out of Order Date"))

    def __str__(self):
        if self.out_of_order_date is None:
            return f"{self.name} {self.meter_number} from: {self.build_in_date:%Y-%m-%d}"
        return f"{self.name} {self.meter_number} ooodate: {self.out_of_order_date:%Y-%m-%d}"

# Define a model representing meter readings.


class MeterReading(models.Model):
    meter = models.ForeignKey(
        MeterPlace, on_delete=models.CASCADE, verbose_name=_("Meter"))
    date = models.DateField(verbose_name=_("Date"))
    meter_reading = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name=_("Meter Reading"))

# Define a model for consumption calculation.


class ConsumptionCalc(models.Model):
    # Define choices for operators used in calculation.
    class Operator(models.TextChoices):
        PLUS = '+', _('+')
        MINUS = '-', _('-')
        MULTIPLY = '*', _('*')
        DIVIDE = '/', _('/')
        NONE = ' ', _(' ')

    # Define fields for the ConsumptionCalc model.
    name = models.CharField(max_length=30, verbose_name=_("Name"))
    argument1 = models.ForeignKey(
        MeterPlace, related_name="arg1", on_delete=models.CASCADE, verbose_name=_("Argument 1"))
    operator1 = models.CharField(
        max_length=1,
        choices=Operator.choices,
        blank=True,
        null=True,
        verbose_name=_("Operator 1")
    )
    argument2 = models.ForeignKey(
        MeterPlace, related_name="arg2", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Argument 2"))
    operator2 = models.CharField(
        max_length=1,
        choices=Operator.choices,
        blank=True,
        null=True,
        verbose_name=_("Operator 2")
    )
    argument3 = models.ForeignKey(
        MeterPlace,  related_name="arg3", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Argument 3"))

# Define a model representing account entries.


class AccountEntry(models.Model):
    # Define choices for entry types.
    class EntryType(models.TextChoices):
        ELECTRICITY = 'EL', _('Electricity')
        HEAT = 'HE', _('Heating')

    # Define fields for the AccountEntry model.
    date = models.DateField(verbose_name=_("Date"))
    text = models.CharField(max_length=30, verbose_name=_("Text"))
    value = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Value"))
    type = models.CharField(
        max_length=2,
        choices=EntryType.choices,
        verbose_name=_("Entry Type")
    )

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
