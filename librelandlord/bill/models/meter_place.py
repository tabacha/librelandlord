from django.db import models
from django.utils.translation import gettext_lazy as _
from datetime import date
from typing import Dict, List, Optional, NamedTuple
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)
# Define a model representing a place where meters are installed.


class BillingError(Exception):
    """Basis-Exception für Abrechnungsfehler"""
    pass


class NoActiveMetersError(BillingError):
    """Exception wenn keine aktiven Meter im Abrechnungszeitraum gefunden werden"""
    pass


class MeterCalculationError(BillingError):
    """Exception wenn die Berechnung für einen Meter fehlschlägt"""
    pass


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

    @property
    def unit(self) -> str:
        """
        Gibt die Einheit basierend auf dem Zählertyp zurück.

        Returns:
            str: Die entsprechende Einheit (kWh, m³, Liter)
        """
        unit_mapping = {
            self.MeterType.ELECTRICITY: 'kWh',
            self.MeterType.GAS: 'kWh',
            self.MeterType.COLDWATER: 'm³',
            self.MeterType.WARMWATER: 'm³',
            self.MeterType.HEAT: 'kWh',
            self.MeterType.OIL: 'Liter'
        }
        return unit_mapping.get(self.type, '')

    def __str__(self):
        return self.name+' '+self.type+' '+self.location

    class MeterPeriod(NamedTuple):
        """Zeitraum eines einzelnen Meters mit Zählerständen"""
        meter: 'Meter'
        period_start: date
        period_end: date
        days_active: int
        start_reading: 'MeterReadingAtDate'
        end_reading: 'MeterReadingAtDate'
        consumption: Optional[Decimal]

    class BillingCalculation(NamedTuple):
        """Komplette Abrechnungsberechnung für einen MeterPlace"""
        meter_place: 'MeterPlace'
        billing_period_start: date
        billing_period_end: date
        meter_periods: List['MeterPeriod']
        total_consumption: Decimal
        total_days_active: int

    def calculate_billing(self, start_date: date, end_date: date) -> BillingCalculation:
        """
        Berechnet eine vollständige Abrechnung für diesen MeterPlace im angegebenen Zeitraum.

        Berücksichtigt automatisch Zählerauswechslungen und dokumentiert den kompletten Rechenweg.

        Args:
            start_date: Startdatum der Abrechnung
            end_date: Enddatum der Abrechnung

        Returns:
            BillingCalculation mit stark typisierten Objekten

        Raises:
            ValueError: Bei ungültigen Eingabedaten
            NoActiveMetersError: Wenn keine aktiven Meter im Zeitraum gefunden werden
            MeterCalculationError: Wenn die Berechnung für einen Meter fehlschlägt
        """
        from .meter import Meter
        from .meter_reading import MeterReading, MeterNotActiveError, InsufficientDataError

        if start_date >= end_date:
            raise ValueError(
                f"Start date {start_date} must be before end date {end_date}")

        meter_periods = []
        total_consumption = Decimal('0.00')
        total_days_active = 0

        # Alle Meter finden, die im Zeitraum aktiv waren
        meters = self.meter_set.filter(
            models.Q(build_in_date__lte=end_date) &
            # Meter ist aktiv oder wurde nach start_date außer Betrieb genommen
            (models.Q(out_of_order_date__isnull=True) |
             models.Q(out_of_order_date__gte=start_date))
        ).order_by('build_in_date')

        if not meters.exists():
            raise NoActiveMetersError(
                f"Keine aktiven Meter im Zeitraum {start_date} bis {end_date} "
                f"für MeterPlace '{self.name}' gefunden"
            )

        # Für jeden Meter den relevanten Zeitraum und Verbrauch berechnen
        for meter in meters:
            # Effektive Periode für diesen Meter berechnen
            meter_start = max(start_date, meter.build_in_date)
            meter_end = end_date
            if meter.out_of_order_date:
                meter_end = min(end_date, meter.out_of_order_date)

            days_active = (meter_end - meter_start).days + 1
            if days_active <= 0:
                raise MeterCalculationError(
                    f"Meter {meter.meter_number} war im Zeitraum {start_date} bis {end_date} "
                    f"nicht aktiv (Meter-Zeitraum: {meter_start} bis {meter_end})"
                )

            try:
                # Anfangsstand berechnen/interpolieren
                start_reading = MeterReading.objects.get_reading_at_date(
                    meter, meter_start)

                # Endstand berechnen/interpolieren
                end_reading = MeterReading.objects.get_reading_at_date(
                    meter, meter_end)

                # Verbrauch berechnen
                if start_reading.calculated_reading is None or end_reading.calculated_reading is None:
                    raise MeterCalculationError(
                        f"Verbrauch für Meter {meter.meter_number} konnte nicht berechnet werden: "
                        f"Anfangsstand={start_reading.calculated_reading}, "
                        f"Endstand={end_reading.calculated_reading}"
                    )

                consumption = Decimal(str(
                    end_reading.calculated_reading)) - Decimal(str(start_reading.calculated_reading))
                total_consumption += consumption
                total_days_active += days_active

            except (MeterNotActiveError, InsufficientDataError) as e:
                raise MeterCalculationError(
                    f"Fehler bei Meter {meter.meter_number} ({meter_start} bis {meter_end}): {str(e)}"
                ) from e
            # MeterPeriod erstellen
            meter_period = self.MeterPeriod(
                meter=meter,
                period_start=meter_start,
                period_end=meter_end,
                days_active=days_active,
                start_reading=start_reading,
                end_reading=end_reading,
                consumption=consumption
            )
            meter_periods.append(meter_period)

        return self.BillingCalculation(
            meter_place=self,
            billing_period_start=start_date,
            billing_period_end=end_date,
            meter_periods=meter_periods,
            total_consumption=total_consumption,
            total_days_active=total_days_active
        )
