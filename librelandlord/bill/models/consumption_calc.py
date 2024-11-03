from django.db import models
from django.utils.translation import gettext_lazy as _
from .meter_place import MeterPlace


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
