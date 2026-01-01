from django.db import models
from django.utils.translation import gettext_lazy as _
from datetime import date
from typing import List, NamedTuple
from decimal import Decimal


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

    class ContributionResult(NamedTuple):
        """Ergebnis einer einzelnen CostCenterContribution"""
        contribution: 'CostCenterContribution'
        apartment_name: str
        consumption_calc_name: str
        consumption_result: 'ConsumptionCalc.ConsumptionResult'
        final_consumption: Decimal
        percentage: float
        # Renter-Informationen
        renter_id: int  # None bei Leerstand
        renter_first_name: str  # None bei Leerstand
        renter_last_name: str  # None bei Leerstand
        period_start: date  # Tatsächliches Startdatum für diesen Renter/Leerstand
        period_end: date  # Tatsächliches Enddatum für diesen Renter/Leerstand

    class CostCenterCalculation(NamedTuple):
        """Gesamtberechnung eines CostCenters"""
        cost_center: 'CostCenter'
        calculation_period_start: date
        calculation_period_end: date
        contribution_results: List['ContributionResult']
        total_consumption: Decimal
        apartment_count: int
        total_consumption_unit: str

    def calculate_total_consumption(self, start_date: date, end_date: date) -> CostCenterCalculation:
        """
        Berechnet den Gesamtverbrauch dieses CostCenters für den angegebenen Zeitraum.

        Ruft für alle zugehörigen CostCenterContributions die ConsumptionCalc auf
        und summiert die Ergebnisse.

        Args:
            start_date: Startdatum der Berechnung
            end_date: Enddatum der Berechnung

        Returns:
            CostCenterCalculation mit allen Details der Berechnung

        Raises:
            ValueError: Bei ungültigen Eingabedaten
        """
        from .cost_center_contribution import CostCenterContribution
        if start_date >= end_date:
            raise ValueError(
                f"Total Consumption {self.text} Start date {start_date} must be before end date {end_date}")

        # Alle CostCenterContributions für dieses CostCenter holen
        contributions = CostCenterContribution.objects.filter(
            cost_center=self
        ).select_related('apartment', 'consumption_calc')

        if not contributions.exists():
            return self.CostCenterCalculation(
                cost_center=self,
                calculation_period_start=start_date,
                calculation_period_end=end_date,
                contribution_results=[],
                total_consumption=Decimal('0.00'),
                apartment_count=0,
                total_consumption_unit=""
            )

        contribution_results = []
        total_consumption = Decimal('0.00')
        apartment_names = set()
        total_consumption_unit = ""

        # Erst alle Contributions sammeln um Gesamtverbrauch zu berechnen
        temp_results = []

        # Für jede Contribution die ConsumptionCalc berechnen
        # Aber jetzt für jede Renter-Periode separat
        for contribution in contributions:
            try:
                # Hole alle Renter-Perioden für diese Wohnung
                if contribution.apartment:
                    periods = contribution.apartment.get_renters_for_period(
                        start_date=start_date,
                        end_date=end_date
                    )
                else:
                    # Keine Wohnung (special_designation) - behandle als eine Periode ohne Renter
                    periods = [{
                        'start_date': start_date,
                        'end_date': end_date,
                        'renter_id': None,
                        'renter': None
                    }]

                # Für jede Periode eine separate Berechnung
                for period in periods:
                    # Prüfe ob die Periode mit dem gültigen Bereich der ConsumptionCalc überlappt
                    calc_start = contribution.consumption_calc.start_date
                    calc_end = contribution.consumption_calc.end_date

                    # Wenn end_date der ConsumptionCalc None ist, gibt es kein oberes Limit
                    # Prüfe ob überhaupt eine Überlappung existiert
                    if period['end_date'] <= calc_start:
                        # Periode endet vor dem gültigen Bereich - überspringen
                        continue
                    if calc_end is not None and period['start_date'] >= calc_end:
                        # Periode beginnt nach dem gültigen Bereich - überspringen
                        continue

                    # Passe die Datumsangaben an den gültigen Bereich an
                    adjusted_start = max(period['start_date'], calc_start)
                    if calc_end is not None:
                        adjusted_end = min(period['end_date'], calc_end)
                    else:
                        adjusted_end = period['end_date']

                    # Stelle sicher, dass adjusted_start < adjusted_end
                    if adjusted_start >= adjusted_end:
                        continue

                    # ConsumptionResult von der ConsumptionCalc holen mit angepassten Daten
                    consumption_result = contribution.consumption_calc.calculate(
                        start_date=adjusted_start,
                        end_date=adjusted_end
                    )

                    # Apartment-Name ermitteln
                    apartment_name = contribution.get_display_name()
                    apartment_names.add(apartment_name)

                    # Renter-Informationen
                    renter = period.get('renter')
                    renter_id = period.get('renter_id')
                    renter_first_name = renter.first_name if renter else None
                    renter_last_name = renter.last_name if renter else None

                    # Einheit vom ersten Ergebnis übernehmen
                    if not total_consumption_unit and consumption_result.calculation_steps:
                        final_step = consumption_result.calculation_steps[-1]
                        total_consumption_unit = final_step.unit or ""

                    # Temporär speichern
                    temp_results.append({
                        'contribution': contribution,
                        'apartment_name': apartment_name,
                        'consumption_result': consumption_result,
                        'final_consumption': consumption_result.final_result,
                        'renter_id': renter_id,
                        'renter_first_name': renter_first_name,
                        'renter_last_name': renter_last_name,
                        'period_start': adjusted_start,
                        'period_end': adjusted_end
                    })

                    total_consumption += consumption_result.final_result

            except Exception as e:
                # Bei Fehlern detaillierte Information ausgeben
                consumption_calc_name = contribution.consumption_calc.name if contribution.consumption_calc else 'N/A'
                consumption_calc_id = contribution.consumption_calc.id if contribution.consumption_calc else 'N/A'
                raise ValueError(
                    f"Fehler bei Berechnung für Apartment {contribution.apartment} "
                    f"(CostCenterContribution ID: {contribution.id}, "
                    f"ConsumptionCalc: '{consumption_calc_name}' [ID: {consumption_calc_id}]): "
                    f"{str(e)}"
                ) from e

        # Jetzt ContributionResults mit Prozentsätzen erstellen
        for temp_result in temp_results:
            # Prozentsatz berechnen
            if total_consumption != 0:
                percentage = float(
                    (temp_result['final_consumption'] / total_consumption) * 100)
            else:
                percentage = 0.0

            contribution_result = self.ContributionResult(
                contribution=temp_result['contribution'],
                apartment_name=temp_result['apartment_name'],
                consumption_calc_name=temp_result['contribution'].consumption_calc.name,
                consumption_result=temp_result['consumption_result'],
                final_consumption=temp_result['final_consumption'],
                percentage=percentage,
                renter_id=temp_result['renter_id'],
                renter_first_name=temp_result['renter_first_name'],
                renter_last_name=temp_result['renter_last_name'],
                period_start=temp_result['period_start'],
                period_end=temp_result['period_end']
            )

            contribution_results.append(contribution_result)

        return self.CostCenterCalculation(
            cost_center=self,
            calculation_period_start=start_date,
            calculation_period_end=end_date,
            contribution_results=contribution_results,
            total_consumption=total_consumption,
            apartment_count=len(apartment_names),
            total_consumption_unit=total_consumption_unit
        )
