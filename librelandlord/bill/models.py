from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MaxValueValidator
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
        return self.name

# Define a model representing different types of meters.


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

    def __str__(self):
        if self.out_of_order_date is None:
            return f"{self.place.name} {self.meter_number} from: {self.build_in_date:%Y-%m-%d}"
        return f"{self.place.name} {self.meter_number} ooodate: {self.out_of_order_date:%Y-%m-%d}"

# Define a model representing meter readings.


class MeterReading(models.Model):
    meter = models.ForeignKey(
        Meter, on_delete=models.CASCADE, verbose_name=_("Meter"))
    date = models.DateField(verbose_name=_("Date"))
    time = models.TimeField(verbose_name=_("Time"), null=True, blank=True)
    meter_reading = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name=_("Meter Reading"))

    def __str__(self):
        return f"{str(self.meter)} {self.meter_reading}"
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
        MeterPlace, related_name="arg1", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Argument 1"))
    argument1_value = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name=_("Argument 1 Value"))
    operator1 = models.CharField(
        max_length=1,
        choices=Operator.choices,
        blank=True,
        null=True,
        verbose_name=_("Operator 1")
    )
    argument2 = models.ForeignKey(
        MeterPlace, related_name="arg2", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Argument 2"))
    argument2_value = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name=_("Argument 2 Value"))

    operator2 = models.CharField(
        max_length=1,
        choices=Operator.choices,
        blank=True,
        null=True,
        verbose_name=_("Operator 2")
    )
    argument3 = models.ForeignKey(
        MeterPlace,  related_name="arg3", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Argument 3"))
    argument3_value = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name=_("Argument 3 Value"))

    def __str__(self):
        return f"{self.name}"


class Bill(models.Model):
    text = models.CharField(max_length=40, verbose_name=_("Booking Text"))
    date = models.DateField(verbose_name=_("Date"))
    bill_number = models.CharField(
        max_length=15, verbose_name=_("Bill number"))
    value = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Value"))

    def __str__(self):
        return f"{self.date} {self.text} {self.value}"


class AccountPeriod(models.Model):
    text = models.CharField(
        max_length=27, verbose_name=_("Account Period Name"))
    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(verbose_name=_("End Date"))


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

    def __str__(self):
        return f"{self.first_name} {self.last_name} {self.apartment}"


# CostCenter
# Examples:
# m2 Kalt+Warmwasserzähler der jeweiligen Wohnugen


class CostCenter(models.Model):
    text = models.CharField(max_length=27, verbose_name=_("Cost Center Text"))
    is_oiltank = models.BooleanField(
        verbose_name=_('Is Oiltank')
    )

    def __str__(self):
        return f"{self.text}"

# Example
# Costcenter: Wasserzäher
# Flat: Wohnung Ost
# Consuption_cost: Wasserzählerberechung Ost


class CostCenterContribution(models.Model):
    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.CASCADE, verbose_name=_("Cost Center"))
    apartment = models.ForeignKey(
        Apartment,  related_name="appartment", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Apartment"))
    consumption_calc = models.ForeignKey(
        ConsumptionCalc, related_name="consumption_calc", on_delete=models.CASCADE, verbose_name=_("Consumption"))

    def __str__(self):
        return f"{self.cost_center} {self.apartment}"

# Example:
# Costcenter: Wasserzäher
# Account_entry: Wasserkosten ohne Zählerkosten


class CostCenterBillEntry(models.Model):
    cost_center = models.ForeignKey(
        CostCenter, on_delete=models.CASCADE, verbose_name=_("Cost Center"))
    account_entry = models.ForeignKey(
        AccountEntry, on_delete=models.CASCADE, verbose_name=_("Account Entry"))
    oil_in_liter = models.DecimalField(max_digits=8, decimal_places=0,
                                       verbose_name=_("Oil in Liter"), blank=True, null=True)

    def __str__(self):
        return f"{self.cost_center} {self.account_entry}"


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
