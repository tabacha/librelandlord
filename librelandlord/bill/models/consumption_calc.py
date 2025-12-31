from django.db import models
from django.utils.translation import gettext_lazy as _
from datetime import date
from typing import List, Optional, NamedTuple
from decimal import Decimal
from .meter_place import MeterPlace


class ConsumptionCalc(models.Model):
    # Define choices for operators used in calculation.
    class Operator(models.TextChoices):
        PLUS = '+', _('+')
        MINUS = '-', _('-')
        MULTIPLY = '*', _('*')
        DIVIDE = '/', _('/')
        NONE = ' ', _(' ')

    # Define choices for units
    class Unit(models.TextChoices):
        EMPTY = '', _('')
        KWH = 'kWh', _('kWh')
        M3 = 'm³', _('m³')
        LITER = 'Liter', _('Liter')
        M2 = 'm²', _('m²')
        PERCENT = '%', _('%')    # Define fields for the ConsumptionCalc model.
    name = models.CharField(max_length=30, verbose_name=_("Name"))
    argument1 = models.ForeignKey(
        MeterPlace, related_name="arg1", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Argument 1"))
    argument1_value = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name=_("Argument 1 Value"))
    argument1_unit = models.CharField(
        max_length=10, choices=Unit.choices, blank=True, default='', verbose_name=_("Argument 1 Unit"))
    argument1_explanation = models.CharField(
        max_length=200, blank=True, default='', verbose_name=_("Argument 1 Explanation"))
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
    argument2_unit = models.CharField(
        max_length=10, choices=Unit.choices, blank=True, default='', verbose_name=_("Argument 2 Unit"))
    argument2_explanation = models.CharField(
        max_length=200, blank=True, default='', verbose_name=_("Argument 2 Explanation"))

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
    argument3_unit = models.CharField(
        max_length=10, choices=Unit.choices, blank=True, default='', verbose_name=_("Argument 3 Unit"))
    argument3_explanation = models.CharField(
        max_length=200, blank=True, default='', verbose_name=_("Argument 3 Explanation"))

    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(
        blank=True, null=True, verbose_name=_("End Date"))

    def __str__(self):
        return f"{self.name}"

    class ArgumentResult(NamedTuple):
        """Ergebnis eines Arguments (MeterPlace oder Wert)"""
        source_type: str  # "meter_place" oder "value"
        source: Optional[MeterPlace]  # MeterPlace-Instanz oder None
        value: Decimal
        # Nur bei MeterPlace
        billing_calculation: Optional['MeterPlace.BillingCalculation']

    class CalculationStep(NamedTuple):
        """Ein einzelner Berechnungsschritt"""
        step_type: str  # "argument", "operation", "result"
        description: str
        operand1: Optional[Decimal]
        operator: Optional[str]
        operand2: Optional[Decimal]
        result: Optional[Decimal]
        argument_name: Optional[str]
        source_details: Optional[dict]  # Zusätzliche Informationen
        unit: Optional[str]  # Einheit des Ergebnisses
        operand1_label: Optional[str] = None  # Erklärung für Operand 1
        operand2_label: Optional[str] = None  # Erklärung für Operand 2
        operand1_unit: Optional[str] = None  # Einheit für Operand 1
        operand2_unit: Optional[str] = None  # Einheit für Operand 2

    class ConsumptionResult(NamedTuple):
        """Vollständiges Berechnungsergebnis"""
        consumption_calc: 'ConsumptionCalc'
        calculation_period_start: date
        calculation_period_end: date
        argument1_result: 'ArgumentResult'
        argument2_result: Optional['ArgumentResult']
        argument3_result: Optional['ArgumentResult']
        final_result: Decimal
        calculation_steps: List['CalculationStep']

    def calculate(self, start_date: date, end_date: date) -> ConsumptionResult:
        """
        Berechnet das Ergebnis dieser ConsumptionCalc für den angegebenen Zeitraum.

        Args:
            start_date: Startdatum der Berechnung
            end_date: Enddatum der Berechnung

        Returns:
            ConsumptionResult mit allen Details der Berechnung

        Raises:
            ValueError: Bei ungültigen Berechnungsparametern
        """
        if start_date >= end_date:
            raise ValueError(
                f"Consumption Result Start date {start_date} must be before end date {end_date}")

        # Prüfe ob der Berechnungszeitraum im gültigen Bereich liegt
        if start_date < self.start_date:
            raise ValueError(
                f"Start date {start_date} liegt vor dem gültigen Startdatum {self.start_date} der Berechnung '{self.name}'")

        if self.end_date is not None and end_date > self.end_date:
            raise ValueError(
                f"End date {end_date} liegt nach dem gültigen Enddatum {self.end_date} der Berechnung '{self.name}'")

        calculation_steps = []

        # Argument 1 berechnen (immer erforderlich)
        arg1_result = self._calculate_argument(
            meter_place=self.argument1,
            value=self.argument1_value,
            start_date=start_date,
            end_date=end_date,
            arg_name="Argument 1"
        )

        calculation_steps.append(self.CalculationStep(
            step_type="argument",
            description=self.argument1_explanation or f"Argument 1 ({arg1_result.source_type})",
            operand1=None,
            operator=None,
            operand2=None,
            result=arg1_result.value,
            argument_name="Argument 1",
            source_details=self._get_source_details(arg1_result),
            unit=self._get_unit_from_argument(arg1_result, "Argument 1")
        ))

        result = arg1_result.value

        # Argument 2 berechnen (optional)
        arg2_result = None
        if self.operator1 and (self.argument2 or self.argument2_value is not None):
            arg2_result = self._calculate_argument(
                meter_place=self.argument2,
                value=self.argument2_value,
                start_date=start_date,
                end_date=end_date,
                arg_name="Argument 2"
            )

            calculation_steps.append(self.CalculationStep(
                step_type="argument",
                description=self.argument2_explanation or f"Argument 2 ({arg2_result.source_type})",
                operand1=None,
                operator=None,
                operand2=None,
                result=arg2_result.value,
                argument_name="Argument 2",
                source_details=self._get_source_details(arg2_result),
                unit=self._get_unit_from_argument(arg2_result, "Argument 2")
            ))

            old_result = result
            result = self._apply_operator(
                result, self.operator1, arg2_result.value)

            # Einheiten direkt bestimmen
            unit1 = self._get_unit_from_argument(arg1_result, "Argument 1")
            unit2 = self._get_unit_from_argument(arg2_result, "Argument 2")
            result_unit = self._combine_units(unit1, unit2, self.operator1)

            calculation_steps.append(self.CalculationStep(
                step_type="operation",
                description=f"Operation: {old_result} {self.operator1} {arg2_result.value}",
                operand1=old_result,
                operator=self.operator1,
                operand2=arg2_result.value,
                result=result,
                argument_name=None,
                source_details=None,
                unit=result_unit,
                operand1_label=self.argument1_explanation,
                operand2_label=self.argument2_explanation,
                operand1_unit=unit1,
                operand2_unit=unit2
            ))

        # Argument 3 berechnen (optional)
        arg3_result = None
        if self.operator2 and (self.argument3 or self.argument3_value is not None):
            arg3_result = self._calculate_argument(
                meter_place=self.argument3,
                value=self.argument3_value,
                start_date=start_date,
                end_date=end_date,
                arg_name="Argument 3"
            )

            calculation_steps.append(self.CalculationStep(
                step_type="argument",
                description=self.argument3_explanation or f"Argument 3 ({arg3_result.source_type})",
                operand1=None,
                operator=None,
                operand2=None,
                result=arg3_result.value,
                argument_name="Argument 3",
                source_details=self._get_source_details(arg3_result),
                unit=self._get_unit_from_argument(arg3_result, "Argument 3")
            ))

            old_result = result
            result = self._apply_operator(
                result, self.operator2, arg3_result.value)

            # Einheiten direkt bestimmen - vorheriges Ergebnis und Argument 3
            # Hole die Einheit vom letzten operation-Schritt
            prev_unit = ""
            for step in reversed(calculation_steps):
                if step.step_type == "operation":
                    prev_unit = step.unit or ""
                    break
            unit3 = self._get_unit_from_argument(arg3_result, "Argument 3")
            result_unit = self._combine_units(prev_unit, unit3, self.operator2)
            multiply = 1
            if unit3 == '%':
                multiply = 100
            calculation_steps.append(self.CalculationStep(
                step_type="operation",
                description=f"Operation: {old_result} {self.operator2} {arg3_result.value}",
                operand1=old_result,
                operator=self.operator2,
                operand2=arg3_result.value*multiply,
                result=result,
                argument_name=None,
                source_details=None,
                unit=result_unit,
                operand1_label=None,
                operand2_label=self.argument3_explanation,
                operand1_unit=prev_unit,
                operand2_unit=unit3
            ))

        # Endergebnis
        final_unit = calculation_steps[-1].unit if calculation_steps else None
        calculation_steps.append(self.CalculationStep(
            step_type="result",
            description=f"Endergebnis der Berechnung '{self.name}'",
            operand1=None,
            operator=None,
            operand2=None,
            result=result,
            argument_name=None,
            source_details={
                'calculation_name': self.name,
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat()
            },
            unit=final_unit
        ))

        return self.ConsumptionResult(
            consumption_calc=self,
            calculation_period_start=start_date,
            calculation_period_end=end_date,
            argument1_result=arg1_result,
            argument2_result=arg2_result,
            argument3_result=arg3_result,
            final_result=result,
            calculation_steps=calculation_steps
        )

    def _calculate_argument(
        self,
        meter_place: Optional[MeterPlace],
        value: Optional[Decimal],
        start_date: date,
        end_date: date,
        arg_name: str
    ) -> ArgumentResult:
        """Berechnet den Wert eines einzelnen Arguments"""

        if meter_place:
            # MeterPlace-Verbrauch berechnen
            billing_calculation = meter_place.calculate_billing(
                start_date, end_date)
            return self.ArgumentResult(
                source_type="meter_place",
                source=meter_place,
                value=billing_calculation.total_consumption,
                billing_calculation=billing_calculation
            )
        elif value is not None:
            # Fester Wert - bei Prozent durch 100 teilen
            calculated_value = value

            # Prüfen ob die Einheit PERCENT ist und entsprechend anpassen
            if arg_name == "Argument 1" and self.argument1_unit == self.Unit.PERCENT:
                calculated_value = value / Decimal('100')
            elif arg_name == "Argument 2" and self.argument2_unit == self.Unit.PERCENT:
                calculated_value = value / Decimal('100')
            elif arg_name == "Argument 3" and self.argument3_unit == self.Unit.PERCENT:
                calculated_value = value / Decimal('100')

            return self.ArgumentResult(
                source_type="value",
                source=None,
                value=calculated_value,
                billing_calculation=None
            )
        else:
            raise ValueError(
                f"{arg_name} muss entweder einen MeterPlace oder einen Wert haben")

    def _apply_operator(self, operand1: Decimal, operator: str, operand2: Decimal) -> Decimal:
        """Wendet einen Operator auf zwei Operanden an"""
        if operator == '+':
            return operand1 + operand2
        elif operator == '-':
            return operand1 - operand2
        elif operator == '*':
            return operand1 * operand2
        elif operator == '/':
            if operand2 == 0:
                raise ValueError("Division durch Null ist nicht erlaubt")
            return operand1 / operand2
        elif operator == ' ':  # NONE
            return operand1
        else:
            raise ValueError(f"Unbekannter Operator: {operator}")

    def _get_source_details(self, arg_result: ArgumentResult) -> dict:
        """Erstellt detaillierte Informationen über die Quelle eines Arguments"""
        if arg_result.source_type == "meter_place" and arg_result.billing_calculation:
            billing = arg_result.billing_calculation
            return {
                'meter_place': arg_result.source,
                'total_consumption': float(billing.total_consumption),
                'total_days_active': billing.total_days_active,
                'meter_count': len(billing.meter_periods),
                'meters': [
                    {
                        'meter_id': period.meter.id,
                        'meter_number': period.meter.meter_number,
                        'consumption': float(period.consumption) if period.consumption else None,
                        'days_active': period.days_active,
                        'start_reading': period.start_reading,
                        'end_reading': period.end_reading,
                    }
                    for period in billing.meter_periods
                ]
            }
        elif arg_result.source_type == "value":
            return {
                'fixed_value': float(arg_result.value)
            }
        else:
            return {}

    def _get_unit_from_argument(self, arg_result: ArgumentResult, arg_name: str = "") -> str:
        """Ermittelt die Einheit eines Arguments"""
        # Zuerst prüfen, ob eine explizite Unit gesetzt ist
        if arg_name == "Argument 1" and self.argument1_unit:
            return self.argument1_unit
        elif arg_name == "Argument 2" and self.argument2_unit:
            return self.argument2_unit
        elif arg_name == "Argument 3" and self.argument3_unit:
            return self.argument3_unit
        # Fallback auf MeterPlace Unit
        elif arg_result.source_type == "meter_place" and arg_result.source:
            return arg_result.source.unit
        else:
            # Für feste Werte keine Einheit oder eine Standard-Einheit
            return ""

    def _combine_units(self, unit1: str, unit2: str, operator: str) -> str:
        """Kombiniert zwei Einheiten basierend auf dem Operator"""
        # Einfache Einheitenberechnung
        if operator == '+' or operator == '-':
            # Bei Addition/Subtraktion sollten die Einheiten gleich sein
            if unit1 == unit2:
                return unit1
            elif unit1 and not unit2:
                return unit1
            elif unit2 and not unit1:
                return unit2
            else:
                return f"{unit1}+{unit2}" if unit1 and unit2 else ""
        elif operator == '*':
            # Bei Multiplikation: Wenn einer der Operanden Prozent ist, behalte die andere Einheit
            if unit2 == '%':
                return unit1  # Prozent ist dimensionslos
            elif unit1 == '%':
                return unit2  # Prozent ist dimensionslos
            elif unit1 and unit2:
                return f"{unit1}×{unit2}"
            elif unit1:
                return unit1
            elif unit2:
                return unit2
            else:
                return ""
        elif operator == '/':
            # Bei Division: Wenn der Divisor Prozent ist, behalte die Einheit des Dividenden
            if unit2 == '%':
                return unit1  # Division durch Prozent ändert die Einheit nicht
            elif unit1 and unit2:
                if unit1 == unit2:
                    return ""  # Einheit kürzt sich weg
                return f"{unit1}/{unit2}"
            elif unit1:
                return unit1
            else:
                return ""
        else:
            return unit1 or ""
