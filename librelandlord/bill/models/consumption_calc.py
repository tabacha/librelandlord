from django.db import models
from django.utils.translation import gettext_lazy as _
from datetime import date
from typing import List, Optional, NamedTuple
from decimal import Decimal
from .meter_place import MeterPlace


class ConsumptionCalcArgument(models.Model):
    """
    Ein Argument in einer ConsumptionCalc-Berechnung.
    Kann entweder ein MeterPlace, ein fester Wert oder eine verschachtelte Berechnung sein.
    """
    consumption_calc = models.ForeignKey(
        'ConsumptionCalc',
        related_name='arguments',
        on_delete=models.CASCADE,
        verbose_name=_("Berechnung")
    )

    position = models.PositiveSmallIntegerField(
        verbose_name=_("Position"),
        help_text=_("Reihenfolge in der Berechnung")
    )

    # Einer von drei möglichen Quellen für den Wert
    meter_place = models.ForeignKey(
        MeterPlace,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        verbose_name=_("Zählerplatz")
    )

    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        verbose_name=_("Festwert")
    )

    nested_calc = models.ForeignKey(
        'ConsumptionCalc',
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name='used_in_arguments',
        verbose_name=_("Verschachtelte Berechnung")
    )

    unit = models.CharField(
        max_length=10,
        choices=[
            ('', _('')),
            ('kWh', _('kWh')),
            ('m³', _('m³')),
            ('Liter', _('Liter')),
            ('m²', _('m²')),
            ('%', _('%'))
        ],
        blank=True,
        default='',
        verbose_name=_("Einheit")
    )

    explanation = models.CharField(
        max_length=200,
        blank=True,
        default='',
        verbose_name=_("Erklärung")
    )

    class Meta:
        ordering = ['position']
        unique_together = [['consumption_calc', 'position']]
        verbose_name = _("Berechnungs-Argument")
        verbose_name_plural = _("Berechnungs-Argumente")

    def __str__(self):
        if self.meter_place:
            return f"Pos {self.position}: {self.meter_place}"
        elif self.nested_calc:
            return f"Pos {self.position}: ({self.nested_calc.name})"
        elif self.value is not None:
            return f"Pos {self.position}: {self.value} {self.unit}"
        else:
            return f"Pos {self.position}: (leer)"

    def clean(self):
        """Validierung: Genau eine Quelle muss gesetzt sein"""
        from django.core.exceptions import ValidationError
        sources = sum([
            bool(self.meter_place),
            self.value is not None,
            bool(self.nested_calc)
        ])
        if sources == 0:
            raise ValidationError(
                _("Mindestens eine Quelle (Zählerplatz, Festwert oder verschachtelte Berechnung) muss angegeben werden."))
        if sources > 1:
            raise ValidationError(
                _("Es darf nur eine Quelle (Zählerplatz, Festwert oder verschachtelte Berechnung) angegeben werden."))


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
        PERCENT = '%', _('%')

    # Define fields for the ConsumptionCalc model.
    name = models.CharField(max_length=50, verbose_name=_("Name"))

    # Neuer Ansatz: Ein Operator für alle Arguments
    operator = models.CharField(
        max_length=1,
        choices=Operator.choices,
        default='+',
        verbose_name=_("Operator"),
        help_text=_("Operator, der alle Argumente verknüpft")
    )

    start_date = models.DateField(verbose_name=_("Start Date"))
    end_date = models.DateField(
        blank=True, null=True, verbose_name=_("End Date"))

    # DEPRECATED: Alte Felder bleiben für Migration erhalten
    # Diese werden in einer späteren Migration entfernt
    argument1 = models.ForeignKey(
        MeterPlace, related_name="arg1", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Argument 1 (DEPRECATED)"))
    argument1_value = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name=_("Argument 1 Value (DEPRECATED)"))
    argument1_unit = models.CharField(
        max_length=10, choices=Unit.choices, blank=True, default='', verbose_name=_("Argument 1 Unit (DEPRECATED)"))
    argument1_explanation = models.CharField(
        max_length=200, blank=True, default='', verbose_name=_("Argument 1 Explanation (DEPRECATED)"))
    operator1 = models.CharField(
        max_length=1,
        choices=Operator.choices,
        blank=True,
        null=True,
        verbose_name=_("Operator 1 (DEPRECATED)")
    )
    argument2 = models.ForeignKey(
        MeterPlace, related_name="arg2", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Argument 2 (DEPRECATED)"))
    argument2_value = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name=_("Argument 2 Value (DEPRECATED)"))
    argument2_unit = models.CharField(
        max_length=10, choices=Unit.choices, blank=True, default='', verbose_name=_("Argument 2 Unit (DEPRECATED)"))
    argument2_explanation = models.CharField(
        max_length=200, blank=True, default='', verbose_name=_("Argument 2 Explanation (DEPRECATED)"))

    operator2 = models.CharField(
        max_length=1,
        choices=Operator.choices,
        blank=True,
        null=True,
        verbose_name=_("Operator 2 (DEPRECATED)")
    )
    argument3 = models.ForeignKey(
        MeterPlace,  related_name="arg3", on_delete=models.CASCADE, blank=True, null=True, verbose_name=_("Argument 3 (DEPRECATED)"))
    argument3_value = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True, verbose_name=_("Argument 3 Value (DEPRECATED)"))
    argument3_unit = models.CharField(
        max_length=10, choices=Unit.choices, blank=True, default='', verbose_name=_("Argument 3 Unit (DEPRECATED)"))
    argument3_explanation = models.CharField(
        max_length=200, blank=True, default='', verbose_name=_("Argument 3 Explanation (DEPRECATED)"))

    def __str__(self):
        return f"{self.name}"

    class ArgumentResult(NamedTuple):
        """Ergebnis eines Arguments (MeterPlace, Wert oder verschachtelte Berechnung)"""
        source_type: str  # "meter_place", "value" oder "nested_calculation"
        source: Optional[MeterPlace]  # MeterPlace-Instanz oder None
        value: Decimal
        # Nur bei MeterPlace
        billing_calculation: Optional['MeterPlace.BillingCalculation']
        # Nur bei nested_calculation
        nested_result: Optional['ConsumptionResult'] = None

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
        # Display-Werte für Prozent-Argumente (z.B. 32.7 statt 0.327)
        operand1_display: Optional[Decimal] = None
        operand2_display: Optional[Decimal] = None
        operand1_display_unit: Optional[str] = None
        operand2_display_unit: Optional[str] = None

    class ConsumptionResult(NamedTuple):
        """Vollständiges Berechnungsergebnis"""
        consumption_calc: 'ConsumptionCalc'
        calculation_period_start: date
        calculation_period_end: date
        argument_results: List['ArgumentResult']  # Alle Argument-Ergebnisse
        final_result: Decimal
        calculation_steps: List['CalculationStep']
        # Kompakte Formel für Anzeige, z.B. "3427,6 kWh - 1430,2 kWh - 444,0 kWh = 1045,9 kWh"
        formula_display: Optional[str] = None
        formula_result_display: Optional[str] = None
        success: bool = True
        error_message: Optional[str] = None

        @property
        def value(self) -> Decimal:
            """Alias für final_result"""
            return self.final_result

    def calculate(self, start_date: date, end_date: date) -> ConsumptionResult:
        """
        Berechnet das Ergebnis dieser ConsumptionCalc für den angegebenen Zeitraum.

        Verwendet das neue ConsumptionCalcArgument System mit beliebig vielen Arguments.

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
        argument_results = []

        # Hole alle Arguments
        arguments = list(self.arguments.all().order_by('position'))

        if not arguments:
            raise ValueError(
                f"ConsumptionCalc '{self.name}' [ID: {self.id}] hat keine Argumente definiert")

        # Berechne alle Argument-Werte
        values = []
        for i, arg in enumerate(arguments):
            try:
                arg_result = self._calculate_single_argument(
                    arg, start_date, end_date)
                argument_results.append(arg_result)
                values.append(arg_result.value)

                # Erstelle Calculation Step für das Argument
                calculation_steps.append(self.CalculationStep(
                    step_type="argument",
                    description=arg.explanation or f"Argument {i+1} ({arg_result.source_type})",
                    operand1=None,
                    operator=None,
                    operand2=None,
                    result=arg_result.value,
                    argument_name=f"Argument {i+1}",
                    source_details=self._get_source_details(arg_result),
                    unit=self._get_unit_from_arg_object(arg, arg_result)
                ))
            except ValueError as e:
                raise ValueError(
                    f"Fehler bei Argument {i+1} (Position {arg.position}) in ConsumptionCalc '{self.name}' [ID: {self.id}] "
                    f"für Zeitraum {start_date} bis {end_date}: {str(e)}"
                ) from e

        # Punkt-vor-Strich: Erst alle * und / auswerten
        if self.operator in ['*', '/']:
            # Multiplikation/Division - alle Werte verknüpfen
            result = values[0]
            for i in range(1, len(values)):
                old_result = result
                result = self._apply_operator(result, self.operator, values[i])

                unit1 = calculation_steps[i -
                                          1].unit if i > 0 else calculation_steps[0].unit
                unit2 = calculation_steps[i].unit
                result_unit = self._combine_units(unit1, unit2, self.operator)

                # Display-Werte für Prozent-Argumente berechnen
                operand1_display = old_result
                operand1_display_unit = unit1
                operand2_display = values[i]
                operand2_display_unit = unit2

                # Wenn Argument i ein Prozent-Argument ist, Display-Wert anpassen
                if arguments[i].unit == self.Unit.PERCENT:
                    operand2_display = values[i] * 100
                    operand2_display_unit = '%'

                # Wenn vorheriges Argument ein Prozent-Argument ist (bei i > 0)
                if i > 0 and arguments[i - 1].unit == self.Unit.PERCENT:
                    operand1_display = old_result * 100
                    operand1_display_unit = '%'

                calculation_steps.append(self.CalculationStep(
                    step_type="operation",
                    description=f"Operation: {old_result} {self.operator} {values[i]}",
                    operand1=old_result,
                    operator=self.operator,
                    operand2=values[i],
                    result=result,
                    argument_name=None,
                    source_details=None,
                    unit=result_unit,
                    operand1_label=arguments[i -
                                             1].explanation if i > 0 else None,
                    operand2_label=arguments[i].explanation,
                    operand1_unit=unit1,
                    operand2_unit=unit2,
                    operand1_display=operand1_display,
                    operand2_display=operand2_display,
                    operand1_display_unit=operand1_display_unit,
                    operand2_display_unit=operand2_display_unit
                ))
        else:
            # Addition/Subtraktion
            result = values[0]
            for i in range(1, len(values)):
                old_result = result
                result = self._apply_operator(result, self.operator, values[i])

                unit1 = calculation_steps[i -
                                          1].unit if i > 0 else calculation_steps[0].unit
                unit2 = calculation_steps[i].unit
                result_unit = self._combine_units(unit1, unit2, self.operator)

                # Display-Werte für Prozent-Argumente berechnen
                operand1_display = old_result
                operand1_display_unit = unit1
                operand2_display = values[i]
                operand2_display_unit = unit2

                # Wenn Argument i ein Prozent-Argument ist, Display-Wert anpassen
                if arguments[i].unit == self.Unit.PERCENT:
                    operand2_display = values[i] * 100
                    operand2_display_unit = '%'

                # Wenn vorheriges Argument ein Prozent-Argument ist (bei i > 0)
                if i > 0 and arguments[i - 1].unit == self.Unit.PERCENT:
                    operand1_display = old_result * 100
                    operand1_display_unit = '%'

                calculation_steps.append(self.CalculationStep(
                    step_type="operation",
                    description=f"Operation: {old_result} {self.operator} {values[i]}",
                    operand1=old_result,
                    operator=self.operator,
                    operand2=values[i],
                    result=result,
                    argument_name=None,
                    source_details=None,
                    unit=result_unit,
                    operand1_label=arguments[i -
                                             1].explanation if i > 0 else None,
                    operand2_label=arguments[i].explanation,
                    operand1_unit=unit1,
                    operand2_unit=unit2,
                    operand1_display=operand1_display,
                    operand2_display=operand2_display,
                    operand1_display_unit=operand1_display_unit,
                    operand2_display_unit=operand2_display_unit
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

        # Erstelle kompakte Formel für Anzeige
        formula_display, formula_result_display = self._build_formula_display(
            arguments, argument_results, calculation_steps, result, final_unit
        )

        return self.ConsumptionResult(
            consumption_calc=self,
            calculation_period_start=start_date,
            calculation_period_end=end_date,
            argument_results=argument_results,
            final_result=result,
            calculation_steps=calculation_steps,
            formula_display=formula_display,
            formula_result_display=formula_result_display
        )

    def _calculate_single_argument(
        self,
        arg: 'ConsumptionCalcArgument',
        start_date: date,
        end_date: date
    ) -> ArgumentResult:
        """Berechnet den Wert eines einzelnen ConsumptionCalcArgument"""

        if arg.nested_calc:
            # Verschachtelte Berechnung ausführen
            nested_result = arg.nested_calc.calculate(start_date, end_date)
            return self.ArgumentResult(
                source_type="nested_calculation",
                source=None,
                value=nested_result.final_result,
                billing_calculation=None,
                nested_result=nested_result
            )
        elif arg.meter_place:
            # MeterPlace-Verbrauch berechnen
            billing_calculation = arg.meter_place.calculate_billing(
                start_date, end_date)
            return self.ArgumentResult(
                source_type="meter_place",
                source=arg.meter_place,
                value=billing_calculation.total_consumption,
                billing_calculation=billing_calculation,
                nested_result=None
            )
        elif arg.value is not None:
            # Fester Wert - bei Prozent durch 100 teilen
            calculated_value = arg.value
            if arg.unit == self.Unit.PERCENT:
                calculated_value = arg.value / Decimal('100')

            return self.ArgumentResult(
                source_type="value",
                source=None,
                value=calculated_value,
                billing_calculation=None,
                nested_result=None
            )
        else:
            raise ValueError(
                f"Argument Position {arg.position} muss entweder meter_place, value oder nested_calc haben")

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

    def _get_unit_from_arg_object(self, arg: 'ConsumptionCalcArgument', arg_result: ArgumentResult) -> str:
        """Ermittelt die Einheit eines ConsumptionCalcArgument

        Wichtig: Bei PERCENT wird leerstring zurückgegeben, da der Wert bereits
        durch 100 geteilt wurde für die Berechnung. Die Display-Darstellung erfolgt
        über die separaten operand_display und operand_display_unit Felder.
        """
        # Bei Prozent: Einheit ist leer, da der Wert bereits durch 100 geteilt wurde
        if arg.unit == self.Unit.PERCENT:
            return ""
        # Zuerst prüfen, ob eine explizite Unit im Argument gesetzt ist
        elif arg.unit:
            return arg.unit
        # Fallback auf MeterPlace Unit
        elif arg_result.source_type == "meter_place" and arg_result.source:
            return arg_result.source.unit
        elif arg_result.source_type == "nested_calculation" and arg_result.nested_result:
            # Bei verschachtelten Berechnungen: Einheit aus dem letzten operation oder result Schritt
            # (nicht argument steps, da diese die Einheit vor der Berechnung haben)
            nested_steps = arg_result.nested_result.calculation_steps
            for step in reversed(nested_steps):
                if step.step_type in ('operation', 'result'):
                    # Auch leere Einheit ist ein gültiges Ergebnis (z.B. bei m²/m²)
                    return step.unit or ""
            return ""
        else:
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
            # Bei Multiplikation: Wenn einer der Operanden dimensionslos ist (leer oder %), behalte die andere Einheit
            if not unit2 or unit2 == '%':
                return unit1  # unit2 ist dimensionslos
            elif not unit1 or unit1 == '%':
                return unit2  # unit1 ist dimensionslos
            elif unit1 and unit2:
                return f"{unit1}×{unit2}"
            else:
                return ""
        elif operator == '/':
            # Bei Division: Wenn der Divisor dimensionslos ist, behalte die Einheit des Dividenden
            if not unit2 or unit2 == '%':
                return unit1  # Division durch dimensionslosen Wert ändert die Einheit nicht
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

    def _build_formula_display(
        self,
        arguments: list,
        argument_results: list,
        calculation_steps: list,
        result: Decimal,
        result_unit: str
    ) -> tuple:
        """
        Erstellt eine kompakte Formel-Darstellung für die Anzeige.

        Beispiele:
        - Addition/Subtraktion: "3427,6 kWh - 1430,2 kWh - 444,0 kWh"
        - Multiplikation: "(16,0 m³ - 12,0 m³) * 28,6 %"

        Returns:
            Tuple[str, str]: (formula_display, formula_result_display)
        """
        import locale
        try:
            locale.setlocale(locale.LC_NUMERIC, 'de_DE.UTF-8')
        except locale.Error:
            pass

        def format_number(val: Decimal) -> str:
            """Formatiert eine Zahl mit Komma als Dezimaltrenner"""
            return f"{float(val):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")

        parts = []

        for i, (arg, arg_result) in enumerate(zip(arguments, argument_results)):
            # Ermittle Display-Wert und Einheit
            if arg.unit == self.Unit.PERCENT:
                # Prozent: Wert * 100 und % als Einheit
                display_value = arg_result.value * 100
                display_unit = '%'
            else:
                display_value = arg_result.value
                display_unit = self._get_unit_from_arg_object(arg, arg_result)

            # Prüfe auf verschachtelte Berechnung
            if arg_result.source_type == 'nested_calculation' and arg_result.nested_result:
                # Hole die Formel der verschachtelten Berechnung
                nested_formula = arg_result.nested_result.formula_display
                if nested_formula:
                    parts.append(f"({nested_formula})")
                else:
                    parts.append(
                        f"{format_number(display_value)} {display_unit}".strip())
            else:
                parts.append(
                    f"{format_number(display_value)} {display_unit}".strip())

        # Verbinde mit Operator
        operator_display = f" {self.operator} "
        formula_display = operator_display.join(parts)

        # Ergebnis formatieren
        formula_result_display = f"{format_number(result)} {result_unit or ''}".strip(
        )

        return formula_display, formula_result_display
