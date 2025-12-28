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
                f"Start date {start_date} must be before end date {end_date}")

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
            description=f"Argument 1 ({arg1_result.source_type})",
            operand1=None,
            operator=None,
            operand2=None,
            result=arg1_result.value,
            argument_name="Argument 1",
            source_details=self._get_source_details(arg1_result),
            unit=self._get_unit_from_argument(arg1_result)
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
                description=f"Argument 2 ({arg2_result.source_type})",
                operand1=None,
                operator=None,
                operand2=None,
                result=arg2_result.value,
                argument_name="Argument 2",
                source_details=self._get_source_details(arg2_result),
                unit=self._get_unit_from_argument(arg2_result)
            ))

            old_result = result
            result = self._apply_operator(
                result, self.operator1, arg2_result.value)

            calculation_steps.append(self.CalculationStep(
                step_type="operation",
                description=f"Operation: {old_result} {self.operator1} {arg2_result.value}",
                operand1=old_result,
                operator=self.operator1,
                operand2=arg2_result.value,
                result=result,
                argument_name=None,
                source_details=None,
                unit=self._calculate_operation_unit(
                    arg1_result, self.operator1, arg2_result)
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
                description=f"Argument 3 ({arg3_result.source_type})",
                operand1=None,
                operator=None,
                operand2=None,
                result=arg3_result.value,
                argument_name="Argument 3",
                source_details=self._get_source_details(arg3_result),
                unit=self._get_unit_from_argument(arg3_result)
            ))

            old_result = result
            result = self._apply_operator(
                result, self.operator2, arg3_result.value)

            calculation_steps.append(self.CalculationStep(
                step_type="operation",
                description=f"Operation: {old_result} {self.operator2} {arg3_result.value}",
                operand1=old_result,
                operator=self.operator2,
                operand2=arg3_result.value,
                result=result,
                argument_name=None,
                source_details=None,
                unit=self._calculate_operation_unit(
                    calculation_steps[-2], self.operator2, arg3_result) if calculation_steps else None
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
            # Fester Wert
            return self.ArgumentResult(
                source_type="value",
                source=None,
                value=value,
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

    def _get_unit_from_argument(self, arg_result: ArgumentResult) -> str:
        """Ermittelt die Einheit eines Arguments"""
        if arg_result.source_type == "meter_place" and arg_result.source:
            return arg_result.source.unit
        else:
            # Für feste Werte keine Einheit oder eine Standard-Einheit
            return ""

    def _calculate_operation_unit(self, operand1_source, operator: str, operand2_source) -> str:
        """Berechnet die Einheit nach einer Operation zwischen zwei Operanden"""
        # Hole Einheiten der beiden Operanden
        if hasattr(operand1_source, 'unit'):
            unit1 = operand1_source.unit
        elif isinstance(operand1_source, self.CalculationStep):
            unit1 = operand1_source.unit or ""
        else:
            unit1 = self._get_unit_from_argument(operand1_source)

        unit2 = self._get_unit_from_argument(operand2_source)

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
            # Bei Multiplikation werden Einheiten multipliziert
            if unit1 and unit2:
                return f"{unit1}×{unit2}"
            elif unit1:
                return unit1
            elif unit2:
                return unit2
            else:
                return ""
        elif operator == '/':
            # Bei Division wird durch die zweite Einheit geteilt
            if unit1 and unit2:
                return f"{unit1}/{unit2}"
            elif unit1:
                return unit1
            else:
                return ""
        else:
            return unit1 or ""
