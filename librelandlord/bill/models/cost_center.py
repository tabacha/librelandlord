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
                f"Start date {start_date} must be before end date {end_date}")

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
        for contribution in contributions:
            try:
                # ConsumptionResult von der ConsumptionCalc holen
                consumption_result = contribution.consumption_calc.calculate(
                    start_date=start_date,
                    end_date=end_date
                )

                # Apartment-Name ermitteln
                apartment_name = contribution.get_display_name()
                apartment_names.add(apartment_name)

                # Einheit vom ersten Ergebnis übernehmen
                if not total_consumption_unit and consumption_result.calculation_steps:
                    final_step = consumption_result.calculation_steps[-1]
                    total_consumption_unit = final_step.unit or ""

                # Temporär speichern
                temp_results.append({
                    'contribution': contribution,
                    'apartment_name': apartment_name,
                    'consumption_result': consumption_result,
                    'final_consumption': consumption_result.final_result
                })

                total_consumption += consumption_result.final_result

            except Exception as e:
                # Bei Fehlern in einzelnen Contributions weiterfahren
                raise ValueError(
                    f"Fehler bei Berechnung für Apartment {contribution.apartment}: {str(e)}"
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
                percentage=percentage
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
