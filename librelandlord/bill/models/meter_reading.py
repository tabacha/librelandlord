from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from .meter import Meter


class MeterReading(models.Model):
    meter = models.ForeignKey(
        Meter, on_delete=models.CASCADE, verbose_name=_("Meter"))
    date = models.DateField(verbose_name=_("Date"))
    time = models.TimeField(verbose_name=_("Time"), null=True, blank=True)
    meter_reading = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name=_("Meter Reading"))

    class Meta:
        constraints = [
            # Sicherstellen, dass es pro Zähler nur einen Messwert pro Tag gibt
            models.UniqueConstraint(
                fields=["meter", "date"],
                name="unique_meter_reading_per_day"
            ),
        ]

    def clean(self):
        # Verhindern von rückläufigen Messwerten
        previous_reading = MeterReading.objects.filter(
            meter=self.meter, date__lt=self.date
        ).order_by('-date').first()
        if previous_reading and self.meter_reading < previous_reading.meter_reading:
            raise ValidationError(
                _("Meter reading cannot be less than the previous reading on %(date)s"),
                params={'date': previous_reading.date},
            )

        # Datum der Messung prüfen: Nicht vor `build_in_date` und nicht nach `out_of_order_date`
        if self.date < self.meter.build_in_date:
            raise ValidationError(
                _("Meter reading cannot be before the meter's build-in date."))

        if self.meter.out_of_order_date and self.date > self.meter.out_of_order_date:
            raise ValidationError(
                _("Meter reading cannot be after the meter's out-of-order date."))

    def __str__(self):
        return f"{str(self.meter)} {self.meter_reading}"
