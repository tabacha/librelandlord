from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from datetime import date, time
from typing import Optional, NamedTuple
from .meter import Meter
import logging

logger = logging.getLogger(__name__)


class MeterReadingError(Exception):
    """Basis-Exception für MeterReading-Fehler"""
    pass


class MeterNotActiveError(MeterReadingError):
    """Exception wenn Datum außerhalb der Meter-Laufzeit liegt"""
    pass


class InsufficientDataError(MeterReadingError):
    """Exception wenn nicht genügend Daten für Interpolation vorhanden sind"""
    pass


class MeterReadingAtDate(NamedTuple):
    """Zählerstand zu einem bestimmten Datum"""
    meter: 'Meter'
    date: date
    time: time
    calculated_reading: Optional[float]
    is_exact: bool  # True wenn exakter Messwert, False wenn interpoliert
    reading_before: Optional['MeterReading']  # Messwert vor dem Datum
    reading_after: Optional['MeterReading']   # Messwert nach dem Datum
    # Interpolations-Details (nur bei is_exact=False)
    interpolation_formula: Optional[str] = None  # Berechnungsformel als Text
    days_total: Optional[int] = None  # Tage zwischen before und after
    days_to_target: Optional[int] = None  # Tage von before zu target
    daily_consumption: Optional[float] = None  # Täglicher Verbrauch


class MeterReadingManager(models.Manager):
    """Manager für MeterReading mit erweiterten Abfrage-Methoden"""

    def get_reading_at_date(self, meter: Meter, target_date: date) -> MeterReadingAtDate:
        """
        Berechnet den Zählerstand für einen Meter zu einem bestimmten Datum.

        Wenn ein exakter Messwert vorhanden ist, wird dieser verwendet.
        Andernfalls wird zwischen zwei Messwerten interpoliert.

        Args:
            meter: Der Meter für den der Stand berechnet werden soll
            target_date: Das Datum für das der Stand benötigt wird

        Returns:
            MeterReadingAtDate mit berechnetem Stand und verwendeten Referenzwerten
        """
        # Prüfen ob Datum im gültigen Bereich des Meters liegt
        if target_date < meter.build_in_date:
            raise MeterNotActiveError(
                f"Meter {meter} was not active on {target_date}. "
                f"Build-in date: {meter.build_in_date}"
            )

        if meter.out_of_order_date and target_date > meter.out_of_order_date:
            raise MeterNotActiveError(
                f"Meter {meter} was out of order on {target_date}. "
                f"Out-of-order date: {meter.out_of_order_date}"
            )

        # Exakten Messwert für das Datum suchen
        exact_reading = self.filter(
            meter=meter,
            date=target_date
        ).first()

        if exact_reading:
            return MeterReadingAtDate(
                meter=meter,
                date=target_date,
                # Default to noon if time is None
                time=exact_reading.time or time(12, 0),
                calculated_reading=float(exact_reading.meter_reading),
                is_exact=True,
                reading_before=exact_reading,
                reading_after=exact_reading
            )

        # Messwerte vor und nach dem Zieldatum finden
        reading_before = self.filter(
            meter=meter,
            date__lt=target_date
        ).order_by('-date').first()

        reading_after = self.filter(
            meter=meter,
            date__gt=target_date
        ).order_by('date').first()

        # Interpolation berechnen
        if reading_before and reading_after:
            # Lineare Interpolation zwischen zwei Messwerten
            days_total = (reading_after.date - reading_before.date).days
            days_to_target = (target_date - reading_before.date).days

            if days_total > 0:
                reading_diff = float(
                    reading_after.meter_reading - reading_before.meter_reading)
                daily_consumption = reading_diff / days_total
                calculated_reading = float(
                    reading_before.meter_reading) + (daily_consumption * days_to_target)

                # Erstelle Formel-String
                interpolation_formula = (
                    f"{reading_before.meter_reading:.0f} + "
                    f"(({reading_after.meter_reading:.0f} - {reading_before.meter_reading:.0f}) / {days_total}) * {days_to_target}"
                )
            else:
                # Gleiche Daten - sollte nicht passieren durch unique constraint
                calculated_reading = float(reading_before.meter_reading)
                daily_consumption = 0
                interpolation_formula = f"{reading_before.meter_reading:.0f} (gleiche Daten)"

        elif reading_before and not reading_after:
            # Nur Messwert davor vorhanden - Exception werfen
            raise InsufficientDataError(
                f"No meter reading found after {target_date} for meter {meter}. "
                f"Last available reading: {reading_before.meter_reading} on {reading_before.date}"
            )

        elif reading_after and not reading_before:
            # Nur Messwert danach vorhanden - Exception werfen
            raise InsufficientDataError(
                f"No meter reading found before {target_date} for meter {meter}. "
                f"First available reading: {reading_after.meter_reading} on {reading_after.date}"
            )

        else:
            # Gar keine Messwerte vorhanden
            raise InsufficientDataError(
                f"No meter readings found for meter {meter} to interpolate value for {target_date}"
            )

        rtn = MeterReadingAtDate(
            meter=meter,
            date=target_date,
            time=time(12, 0),  # Default to noon for interpolated readings
            calculated_reading=calculated_reading,
            is_exact=False,
            reading_before=reading_before,
            reading_after=reading_after,
            interpolation_formula=interpolation_formula,
            days_total=days_total,
            days_to_target=days_to_target,
            daily_consumption=daily_consumption
        )
        logger.error("Interpolated reading: %s", rtn)
        return rtn


class MeterReading(models.Model):
    meter = models.ForeignKey(
        Meter, on_delete=models.CASCADE, verbose_name=_("Meter"))
    date = models.DateField(verbose_name=_("Date"))
    time = models.TimeField(verbose_name=_("Time"), null=True, blank=True)
    meter_reading = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name=_("Meter Reading"))

    # Verwende den benutzerdefinierten Manager
    objects = MeterReadingManager()

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
        return f"{str(self.date)} {str(self.meter)} {self.meter_reading}"
