from django.db import models
from django.utils.translation import gettext_lazy as _


class MeterPlace(models.Model):
    name = models.CharField(max_length=30)

    def __str__(self):
        return self.name


class Meter(models.Model):
    class MeterType(models.TextChoices):
        ELECTRICITY = 'EL', _('electricity')
        GAS = 'GA', _('gas')
        COLDWATER = 'KW', _('cold water')
        WARMWATER = 'WW', _('warm water')
        HEAT = 'HE', _('heating')
        OIL = 'OI', _('fuel oil')

    place = models.ForeignKey(MeterPlace, on_delete=models.CASCADE)
    remark = models.CharField(max_length=40)
    meter_number = models.CharField(max_length=30)
    type = models.CharField(
        max_length=2,
        choices=MeterType.choices
    )
    build_in_date = models.DateField()
    out_of_order_date = models.DateField(null=True, blank=True)

    def __str__(self):
        if self.out_of_order_date is None:
            return f"{self.name} {self.meter_nummer} from: {self.build_in_date:%Y-%m-%d}"
        return f"{self.name} {self.meter_nummer} ooodate: {self.out_of_order_date:%Y-%m-%d}"


class MeterReading(models.Model):
    meter = models.ForeignKey(MeterPlace, on_delete=models.CASCADE)
    date = models.DateField()
    meter_reading = models.DecimalField(max_digits=15, decimal_places=2)


class ConsumptionCalc(models.Model):
    class Operator(models.TextChoices):
        PLUS = '+', '+'
        MINUS = '-', '-'
        MULTIPLY = '*', '*'
        DIVIDE = '/', '/'
        NONE = ' ', ' '

    name = models.CharField(max_length=30)
    argument1 = models.ForeignKey(
        MeterPlace, related_name="arg1", on_delete=models.CASCADE)
    operator1 = models.CharField(
        max_length=1,
        choices=Operator.choices,
        blank=True,
        null=True
    )
    argument2 = models.ForeignKey(
        MeterPlace, related_name="arg2", on_delete=models.CASCADE, blank=True, null=True)
    operator2 = models.CharField(
        max_length=1,
        choices=Operator.choices,
        blank=True,
        null=True
    )
    argument3 = models.ForeignKey(
        MeterPlace,  related_name="arg3", on_delete=models.CASCADE, blank=True, null=True)


class AccountEntry(models.Model):
    class EntryType(models.TextChoices):
        ELECTRICITY = 'EL', _('electricity')
        HEAT = 'HE', _('heating')
    date = models.DateField()
    text = models.CharField(max_length=30)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    type = models.CharField(
        max_length=2,
        choices=EntryType.choices
    )


class Apartment(models.Model):
    number = models.CharField(max_length=10)
    name = models.CharField(max_length=30)
    street = models.CharField(max_length=30)
    postal_code = models.CharField(max_length=10)
    city = models.CharField(max_length=30)
    size_in_m2 = models.DecimalField(
        max_digits=4, decimal_places=2)


class Renter(models.Model):
    apartment = models.ForeignKey(Apartment, on_delete=models.CASCADE)
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)
    alt_street = models.CharField(max_length=30, blank=True, null=True)
    postal_code = models.CharField(max_length=10, blank=True, null=True)
    city = models.CharField(max_length=30, blank=True, null=True)
    