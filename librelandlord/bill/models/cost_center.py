from django.db import models
from django.utils.translation import gettext_lazy as _
from datetime import date
from typing import List, NamedTuple
from decimal import Decimal


class CostCenter(models.Model):
    """
    Kostenstelle für die Nebenkostenabrechnung.

    Distribution Types:
    - CONSUMPTION: Anteil nach consumption_calc Ergebnis (z.B. Wasser nach Zähler)
    - TIME: Anteil nach Tagen, aufgeteilt bei Mieterwechsel (z.B. Müll, Internet)
    - AREA: Anteil nach m², aufgeteilt bei Mieterwechsel (z.B. Grundsteuer)
    - DIRECT: Bill geht 1:1 an den Mieter im Bill-Zeitraum (z.B. Waschvorgänge)
    """

    class DistributionType(models.TextChoices):
        CONSUMPTION = 'CONSUMPTION', _('Consumption based (meter reading)')
        TIME = 'TIME', _('By time (days)')
        AREA = 'AREA', _('By area (m²)')
        DIRECT = 'DIRECT', _('Direct assignment (bill period = renter)')
        HEATING_MIXED = 'HEATING_MIXED', _(
            'Heating mixed (area + consumption)')

    text = models.CharField(max_length=27, verbose_name=_("Cost Center Text"))
    is_oiltank = models.BooleanField(
        verbose_name=_('Is Oiltank')
    )
    distribution_type = models.CharField(
        max_length=20,
        choices=DistributionType.choices,
        default=DistributionType.CONSUMPTION,
        verbose_name=_("Distribution Type"),
        help_text=_(
            "CONSUMPTION: by meter, TIME: by days, AREA: by m², DIRECT: bill goes to renter in bill period")
    )
    main_meter_place = models.ForeignKey(
        'MeterPlace',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Main Meter"),
        help_text=_(
            "Main meter for consumption-based distribution (used for mid-year tenant changes)")
    )
    area_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('30.00'),
        verbose_name=_("Area Percentage"),
        help_text=_("Percentage distributed by area (default 30%)")
    )
    consumption_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('70.00'),
        verbose_name=_("Consumption Percentage"),
        help_text=_("Percentage distributed by consumption (default 70%)")
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
        # HEATING_MIXED specific fields (optional, with defaults)
        area_share: Decimal = Decimal('0')
        area_percentage_value: float = 0.0
        consumption_share: Decimal = Decimal('0')
        consumption_percentage_value: float = 0.0

    class CostCenterCalculation(NamedTuple):
        """Gesamtberechnung eines CostCenters"""
        cost_center: 'CostCenter'
        calculation_period_start: date
        calculation_period_end: date
        contribution_results: List['ContributionResult']
        total_consumption: Decimal
        apartment_count: int
        total_consumption_unit: str
        # Zusätzliche Felder für die Darstellung der Berechnungsformel
        total_days: int = 0  # Gesamttage des Abrechnungszeitraums
        # Gesamt-m² aller Wohnungen (für AREA)
        total_area: Decimal = Decimal('0')

    def calculate_total_consumption(self, start_date: date, end_date: date, bills=None) -> CostCenterCalculation:
        """
        Berechnet den Gesamtverbrauch/Anteil dieses CostCenters für den angegebenen Zeitraum.

        Je nach distribution_type:
        - CONSUMPTION: Nutzt consumption_calc für Verbrauchsberechnung
        - TIME: Berechnet Anteil nach Tagen (gleiche Aufteilung pro Wohnung)
        - AREA: Berechnet Anteil nach m² der Wohnung
        - DIRECT: 1:1 Zuordnung zum Mieter im Bill-Zeitraum (pro Bill)

        Args:
            start_date: Startdatum der Berechnung
            end_date: Enddatum der Berechnung
            bills: Optional - Liste von Bills für DIRECT-Berechnung (verwendet Bill-Zeiträume)

        Returns:
            CostCenterCalculation mit allen Details der Berechnung

        Raises:
            ValueError: Bei ungültigen Eingabedaten
        """
        from .cost_center_contribution import CostCenterContribution
        from .consumption_calc import ConsumptionCalc

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

        # Je nach distribution_type unterschiedliche Berechnung
        if self.distribution_type == self.DistributionType.CONSUMPTION:
            return self._calculate_consumption_based(contributions, start_date, end_date)
        elif self.distribution_type == self.DistributionType.TIME:
            return self._calculate_time_based(contributions, start_date, end_date)
        elif self.distribution_type == self.DistributionType.AREA:
            return self._calculate_area_based(contributions, start_date, end_date)
        elif self.distribution_type == self.DistributionType.DIRECT:
            return self._calculate_direct(contributions, start_date, end_date, bills)
        elif self.distribution_type == self.DistributionType.HEATING_MIXED:
            return self._calculate_heating_mixed(contributions, start_date, end_date)
        else:
            raise ValueError(
                f"Unknown distribution_type: {self.distribution_type}")

    def _calculate_consumption_based(self, contributions, start_date: date, end_date: date) -> CostCenterCalculation:
        """Berechnung basierend auf consumption_calc (Zählerstand)"""
        from .consumption_calc import ConsumptionCalc

        contribution_results = []
        total_consumption = Decimal('0.00')
        apartment_names = set()
        total_consumption_unit = ""
        temp_results = []

        for contribution in contributions:
            try:
                if not contribution.consumption_calc:
                    raise ValueError(
                        "consumption_calc is required for CONSUMPTION distribution type")

                # Hole alle Renter-Perioden für diese Wohnung
                if contribution.apartment:
                    periods = contribution.apartment.get_renters_for_period(
                        start_date=start_date,
                        end_date=end_date
                    )
                else:
                    periods = [{
                        'start_date': start_date,
                        'end_date': end_date,
                        'renter_id': None,
                        'renter': None
                    }]

                for period in periods:
                    calc_start = contribution.consumption_calc.start_date
                    calc_end = contribution.consumption_calc.end_date

                    if period['end_date'] <= calc_start:
                        continue
                    if calc_end is not None and period['start_date'] >= calc_end:
                        continue

                    adjusted_start = max(period['start_date'], calc_start)
                    adjusted_end = min(
                        period['end_date'], calc_end) if calc_end else period['end_date']

                    if adjusted_start >= adjusted_end:
                        continue

                    consumption_result = contribution.consumption_calc.calculate(
                        start_date=adjusted_start,
                        end_date=adjusted_end
                    )

                    apartment_name = contribution.get_display_name()
                    apartment_names.add(apartment_name)

                    renter = period.get('renter')
                    renter_id = period.get('renter_id')

                    if not total_consumption_unit and consumption_result.calculation_steps:
                        final_step = consumption_result.calculation_steps[-1]
                        total_consumption_unit = final_step.unit or ""

                    temp_results.append({
                        'contribution': contribution,
                        'apartment_name': apartment_name,
                        'consumption_result': consumption_result,
                        'final_consumption': consumption_result.final_result,
                        'renter_id': renter_id,
                        'renter_first_name': renter.first_name if renter else None,
                        'renter_last_name': renter.last_name if renter else None,
                        'period_start': adjusted_start,
                        'period_end': adjusted_end
                    })

                    total_consumption += consumption_result.final_result

            except Exception as e:
                consumption_calc_name = contribution.consumption_calc.name if contribution.consumption_calc else 'N/A'
                consumption_calc_id = contribution.consumption_calc.id if contribution.consumption_calc else 'N/A'
                raise ValueError(
                    f"Fehler bei Berechnung für Apartment {contribution.apartment} "
                    f"(CostCenterContribution ID: {contribution.id}, "
                    f"ConsumptionCalc: '{consumption_calc_name}' [ID: {consumption_calc_id}]): "
                    f"{str(e)}"
                ) from e

        # ContributionResults mit Prozentsätzen erstellen
        for temp_result in temp_results:
            percentage = float(
                (temp_result['final_consumption'] / total_consumption) * 100) if total_consumption != 0 else 0.0

            contribution_results.append(self.ContributionResult(
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
            ))

        return self.CostCenterCalculation(
            cost_center=self,
            calculation_period_start=start_date,
            calculation_period_end=end_date,
            contribution_results=contribution_results,
            total_consumption=total_consumption,
            apartment_count=len(apartment_names),
            total_consumption_unit=total_consumption_unit
        )

    def _calculate_time_based(self, contributions, start_date: date, end_date: date) -> CostCenterCalculation:
        """Berechnung basierend auf Zeit (Tage) - gleiche Aufteilung pro Wohnung"""
        from .consumption_calc import ConsumptionCalc

        contribution_results = []
        total_consumption = Decimal('0.00')
        apartment_names = set()
        temp_results = []

        total_days = (end_date - start_date).days

        for contribution in contributions:
            try:
                if contribution.apartment:
                    # Verwende Vertragsdaten für TIME-Berechnung
                    periods = contribution.apartment.get_renters_for_period(
                        start_date=start_date,
                        end_date=end_date,
                        use_contract_dates=True
                    )
                else:
                    periods = [{
                        'start_date': start_date,
                        'end_date': end_date,
                        'renter_id': None,
                        'renter': None
                    }]

                for period in periods:
                    period_start = period['start_date']
                    period_end = period['end_date']
                    period_days = (period_end - period_start).days

                    # Anteil = Tage der Periode (wird später durch Gesamttage aller Contributions geteilt)
                    consumption_value = Decimal(str(period_days))

                    apartment_name = contribution.get_display_name()
                    apartment_names.add(apartment_name)

                    renter = period.get('renter')
                    renter_id = period.get('renter_id')

                    # Dummy ConsumptionResult erstellen
                    dummy_result = ConsumptionCalc.ConsumptionResult(
                        consumption_calc=None,
                        calculation_period_start=period_start,
                        calculation_period_end=period_end,
                        argument_results=[],
                        final_result=consumption_value,
                        calculation_steps=[
                            ConsumptionCalc.CalculationStep(
                                step_type="result",
                                description=f"Zeitanteil: {period_days} Tage",
                                operand1=None,
                                operator=None,
                                operand2=None,
                                result=consumption_value,
                                argument_name=None,
                                source_details=None,
                                unit="Tage"
                            )
                        ]
                    )

                    temp_results.append({
                        'contribution': contribution,
                        'apartment_name': apartment_name,
                        'consumption_result': dummy_result,
                        'final_consumption': consumption_value,
                        'renter_id': renter_id,
                        'renter_first_name': renter.first_name if renter else None,
                        'renter_last_name': renter.last_name if renter else None,
                        'period_start': period_start,
                        'period_end': period_end
                    })

                    total_consumption += consumption_value

            except Exception as e:
                raise ValueError(
                    f"Fehler bei TIME-Berechnung für Apartment {contribution.apartment} "
                    f"(CostCenterContribution ID: {contribution.id}): {str(e)}"
                ) from e

        # ContributionResults mit Prozentsätzen erstellen
        for temp_result in temp_results:
            percentage = float(
                (temp_result['final_consumption'] / total_consumption) * 100) if total_consumption != 0 else 0.0

            contribution_results.append(self.ContributionResult(
                contribution=temp_result['contribution'],
                apartment_name=temp_result['apartment_name'],
                consumption_calc_name="TIME",
                consumption_result=temp_result['consumption_result'],
                final_consumption=temp_result['final_consumption'],
                percentage=percentage,
                renter_id=temp_result['renter_id'],
                renter_first_name=temp_result['renter_first_name'],
                renter_last_name=temp_result['renter_last_name'],
                period_start=temp_result['period_start'],
                period_end=temp_result['period_end']
            ))

        return self.CostCenterCalculation(
            cost_center=self,
            calculation_period_start=start_date,
            calculation_period_end=end_date,
            contribution_results=contribution_results,
            total_consumption=total_consumption,
            apartment_count=len(apartment_names),
            total_consumption_unit="Tage",
            total_days=total_days
        )

    def _calculate_area_based(self, contributions, start_date: date, end_date: date) -> CostCenterCalculation:
        """Berechnung basierend auf Fläche (m²) und Zeit"""
        from .consumption_calc import ConsumptionCalc

        contribution_results = []
        total_consumption = Decimal('0.00')
        apartment_names = set()
        apartment_areas = {}  # Speichere m² pro Wohnung um Gesamt-m² zu berechnen
        temp_results = []

        total_days = (end_date - start_date).days

        for contribution in contributions:
            try:
                if not contribution.apartment:
                    raise ValueError(
                        "AREA distribution requires an apartment with size_in_m2")

                apartment_area = contribution.apartment.size_in_m2 or Decimal(
                    '0')
                apartment_areas[contribution.apartment.id] = apartment_area

                periods = contribution.apartment.get_renters_for_period(
                    start_date=start_date,
                    end_date=end_date
                )

                for period in periods:
                    period_start = period['start_date']
                    period_end = period['end_date']
                    period_days = (period_end - period_start).days

                    # Anteil = m² × Tage (wird später durch Gesamt-m²-Tage geteilt)
                    consumption_value = apartment_area * \
                        Decimal(str(period_days))

                    apartment_name = contribution.get_display_name()
                    apartment_names.add(apartment_name)

                    renter = period.get('renter')
                    renter_id = period.get('renter_id')

                    dummy_result = ConsumptionCalc.ConsumptionResult(
                        consumption_calc=None,
                        calculation_period_start=period_start,
                        calculation_period_end=period_end,
                        argument_results=[],
                        final_result=consumption_value,
                        calculation_steps=[
                            ConsumptionCalc.CalculationStep(
                                step_type="result",
                                description=f"Flächenanteil: {apartment_area} m² × {period_days} Tage",
                                operand1=apartment_area,
                                operator="×",
                                operand2=Decimal(str(period_days)),
                                result=consumption_value,
                                argument_name=None,
                                source_details=None,
                                unit="m²×Tage",
                                operand1_label="Fläche",
                                operand2_label="Tage",
                                operand1_unit="m²",
                                operand2_unit="Tage"
                            )
                        ]
                    )

                    temp_results.append({
                        'contribution': contribution,
                        'apartment_name': apartment_name,
                        'consumption_result': dummy_result,
                        'final_consumption': consumption_value,
                        'renter_id': renter_id,
                        'renter_first_name': renter.first_name if renter else None,
                        'renter_last_name': renter.last_name if renter else None,
                        'period_start': period_start,
                        'period_end': period_end
                    })

                    total_consumption += consumption_value

            except Exception as e:
                raise ValueError(
                    f"Fehler bei AREA-Berechnung für Apartment {contribution.apartment} "
                    f"(CostCenterContribution ID: {contribution.id}): {str(e)}"
                ) from e

        # ContributionResults mit Prozentsätzen erstellen
        for temp_result in temp_results:
            percentage = float(
                (temp_result['final_consumption'] / total_consumption) * 100) if total_consumption != 0 else 0.0

            contribution_results.append(self.ContributionResult(
                contribution=temp_result['contribution'],
                apartment_name=temp_result['apartment_name'],
                consumption_calc_name="AREA",
                consumption_result=temp_result['consumption_result'],
                final_consumption=temp_result['final_consumption'],
                percentage=percentage,
                renter_id=temp_result['renter_id'],
                renter_first_name=temp_result['renter_first_name'],
                renter_last_name=temp_result['renter_last_name'],
                period_start=temp_result['period_start'],
                period_end=temp_result['period_end']
            ))

        # Berechne Gesamt-m² aller beteiligten Wohnungen
        total_area = sum(apartment_areas.values())

        return self.CostCenterCalculation(
            cost_center=self,
            calculation_period_start=start_date,
            calculation_period_end=end_date,
            contribution_results=contribution_results,
            total_consumption=total_consumption,
            apartment_count=len(apartment_names),
            total_consumption_unit="m²×Tage",
            total_days=total_days,
            total_area=total_area
        )

    def _calculate_direct(self, contributions, start_date: date, end_date: date, bills=None) -> CostCenterCalculation:
        """
        Direkte Zuordnung - Alle Kosten gehen 1:1 an den Mieter der Wohnung.

        Bei DIRECT:
        - Pro Wohnung wird geprüft, dass ein Mieter ALLE Bill-Zeiträume abdeckt
        - Es wird NUR EIN Eintrag pro Wohnung erstellt (100% wenn nur eine Wohnung)
        - Fehler bei: Kein Mieter, Leerstand, oder verschiedene Mieter für verschiedene Bills

        Args:
            contributions: CostCenterContributions (Wohnungen) für dieses CostCenter
            start_date: Fallback-Startdatum wenn keine Bills übergeben
            end_date: Fallback-Enddatum wenn keine Bills übergeben
            bills: Liste von Bills - zur Validierung der Mieter-Zeiträume
        """
        from .consumption_calc import ConsumptionCalc

        contribution_results = []
        total_consumption = Decimal('0.00')
        apartment_names = set()
        temp_results = []

        # Pro Contribution (Wohnung) prüfen
        for contribution in contributions:
            if not contribution.apartment:
                raise ValueError(
                    f"DIRECT-Zuordnung erfordert eine Wohnung "
                    f"(CostCenterContribution ID: {contribution.id})"
                )

            apartment_name = contribution.get_display_name()
            validated_renter = None
            validated_renter_id = None
            overall_start = None
            overall_end = None

            # Wenn Bills übergeben wurden, validiere dass der gleiche Mieter alle Bills abdeckt
            if bills:
                for bill in bills:
                    bill_start = bill.from_date
                    bill_end = bill.to_date
                    bill_info = f"'{bill.text}' ({bill.bill_date}, {bill.value}€, Zeitraum: {bill_start} - {bill_end})"

                    # Verwende Vertragsdaten für DIRECT-Berechnung
                    periods = contribution.apartment.get_renters_for_period(
                        start_date=bill_start,
                        end_date=bill_end,
                        use_contract_dates=True
                    )

                    # Prüfe auf Leerstand
                    vacancy_periods = [p for p in periods if p.get('renter_id') is None]
                    if vacancy_periods:
                        vacancy_info = ", ".join([
                            f"{p['start_date']} - {p['end_date']}"
                            for p in vacancy_periods
                        ])
                        raise ValueError(
                            f"DIRECT-Zuordnung fehlgeschlagen für '{apartment_name}':\n"
                            f"  Bill: {bill_info}\n"
                            f"  Fehler: Leerstand im Rechnungszeitraum ({vacancy_info})"
                        )

                    # Filtere nur Mieter-Perioden
                    renter_periods = [p for p in periods if p.get('renter_id') is not None]

                    if not renter_periods:
                        raise ValueError(
                            f"DIRECT-Zuordnung fehlgeschlagen für '{apartment_name}':\n"
                            f"  Bill: {bill_info}\n"
                            f"  Fehler: Kein Mieter im Rechnungszeitraum"
                        )

                    if len(renter_periods) > 1:
                        renter_info = ", ".join([
                            f"{p['renter'].first_name} {p['renter'].last_name} ({p['start_date']} - {p['end_date']})"
                            for p in renter_periods
                        ])
                        raise ValueError(
                            f"DIRECT-Zuordnung fehlgeschlagen für '{apartment_name}':\n"
                            f"  Bill: {bill_info}\n"
                            f"  Fehler: Mieterwechsel im Rechnungszeitraum\n"
                            f"  Gefundene Mieter: {renter_info}"
                        )

                    # Mieter für diese Bill
                    period = renter_periods[0]
                    current_renter = period['renter']
                    current_renter_id = period['renter_id']

                    # Prüfe ob der gleiche Mieter wie bei vorherigen Bills
                    if validated_renter_id is None:
                        validated_renter = current_renter
                        validated_renter_id = current_renter_id
                        overall_start = bill_start
                        overall_end = bill_end
                    elif validated_renter_id != current_renter_id:
                        raise ValueError(
                            f"DIRECT-Zuordnung fehlgeschlagen für '{apartment_name}':\n"
                            f"  Bill: {bill_info}\n"
                            f"  Fehler: Verschiedene Mieter für verschiedene Bills\n"
                            f"  Erwartet: {validated_renter.first_name} {validated_renter.last_name}\n"
                            f"  Gefunden: {current_renter.first_name} {current_renter.last_name}"
                        )
                    else:
                        # Erweitere den Gesamtzeitraum
                        overall_start = min(overall_start, bill_start)
                        overall_end = max(overall_end, bill_end)

                # Nach Validierung aller Bills: EIN Eintrag pro Wohnung
                consumption_value = Decimal('1')
                apartment_names.add(apartment_name)

                dummy_result = ConsumptionCalc.ConsumptionResult(
                    consumption_calc=None,
                    calculation_period_start=overall_start,
                    calculation_period_end=overall_end,
                    argument_results=[],
                    final_result=consumption_value,
                    calculation_steps=[
                        ConsumptionCalc.CalculationStep(
                            step_type="result",
                            description="Direkte Zuordnung",
                            operand1=None,
                            operator=None,
                            operand2=None,
                            result=consumption_value,
                            argument_name=None,
                            source_details=None,
                            unit="Anteil"
                        )
                    ]
                )

                temp_results.append({
                    'contribution': contribution,
                    'apartment_name': apartment_name,
                    'consumption_result': dummy_result,
                    'final_consumption': consumption_value,
                    'renter_id': validated_renter_id,
                    'renter_first_name': validated_renter.first_name,
                    'renter_last_name': validated_renter.last_name,
                    'period_start': overall_start,
                    'period_end': overall_end
                })

                total_consumption += consumption_value
            else:
                # Fallback: Verwende start_date/end_date wenn keine Bills übergeben
                # Verwende Vertragsdaten für DIRECT-Berechnung
                periods = contribution.apartment.get_renters_for_period(
                    start_date=start_date,
                    end_date=end_date,
                    use_contract_dates=True
                )

                # Prüfe auf Leerstand
                vacancy_periods = [p for p in periods if p.get('renter_id') is None]
                if vacancy_periods:
                    vacancy_info = ", ".join([
                        f"{p['start_date']} - {p['end_date']}"
                        for p in vacancy_periods
                    ])
                    raise ValueError(
                        f"DIRECT-Zuordnung fehlgeschlagen für '{apartment_name}':\n"
                        f"  Zeitraum: {start_date} - {end_date}\n"
                        f"  Fehler: Leerstand im Zeitraum ({vacancy_info})"
                    )

                # Filtere nur Mieter-Perioden
                renter_periods = [p for p in periods if p.get('renter_id') is not None]

                if not renter_periods:
                    raise ValueError(
                        f"DIRECT-Zuordnung fehlgeschlagen für '{apartment_name}':\n"
                        f"  Zeitraum: {start_date} - {end_date}\n"
                        f"  Fehler: Kein Mieter im Zeitraum"
                    )

                if len(renter_periods) > 1:
                    renter_info = ", ".join([
                        f"{p['renter'].first_name} {p['renter'].last_name} ({p['start_date']} - {p['end_date']})"
                        for p in renter_periods
                    ])
                    raise ValueError(
                        f"DIRECT-Zuordnung fehlgeschlagen für '{apartment_name}':\n"
                        f"  Zeitraum: {start_date} - {end_date}\n"
                        f"  Fehler: Mieterwechsel im Zeitraum\n"
                        f"  Gefundene Mieter: {renter_info}"
                    )

                # Genau ein Mieter - 100% Zuordnung
                period = renter_periods[0]
                renter = period['renter']
                renter_id = period['renter_id']

                consumption_value = Decimal('1')
                apartment_names.add(apartment_name)

                dummy_result = ConsumptionCalc.ConsumptionResult(
                    consumption_calc=None,
                    calculation_period_start=period['start_date'],
                    calculation_period_end=period['end_date'],
                    argument_results=[],
                    final_result=consumption_value,
                    calculation_steps=[
                        ConsumptionCalc.CalculationStep(
                            step_type="result",
                            description="Direkte Zuordnung",
                            operand1=None,
                            operator=None,
                            operand2=None,
                            result=consumption_value,
                            argument_name=None,
                            source_details=None,
                            unit="Anteil"
                        )
                    ]
                )

                temp_results.append({
                    'contribution': contribution,
                    'apartment_name': apartment_name,
                    'consumption_result': dummy_result,
                    'final_consumption': consumption_value,
                    'renter_id': renter_id,
                    'renter_first_name': renter.first_name,
                    'renter_last_name': renter.last_name,
                    'period_start': period['start_date'],
                    'period_end': period['end_date']
                })

                total_consumption += consumption_value

        # ContributionResults mit Prozentsätzen erstellen
        for temp_result in temp_results:
            percentage = float(
                (temp_result['final_consumption'] / total_consumption) * 100) if total_consumption != 0 else 0.0

            contribution_results.append(self.ContributionResult(
                contribution=temp_result['contribution'],
                apartment_name=temp_result['apartment_name'],
                consumption_calc_name="DIRECT",
                consumption_result=temp_result['consumption_result'],
                final_consumption=temp_result['final_consumption'],
                percentage=percentage,
                renter_id=temp_result['renter_id'],
                renter_first_name=temp_result['renter_first_name'],
                renter_last_name=temp_result['renter_last_name'],
                period_start=temp_result['period_start'],
                period_end=temp_result['period_end']
            ))

        return self.CostCenterCalculation(
            cost_center=self,
            calculation_period_start=start_date,
            calculation_period_end=end_date,
            contribution_results=contribution_results,
            total_consumption=total_consumption,
            apartment_count=len(apartment_names),
            total_consumption_unit="Anteil"
        )

    def _calculate_heating_mixed(self, contributions, start_date: date, end_date: date) -> CostCenterCalculation:
        """
        Berechnung nach Heizkostenverordnung:
        - area_percentage (default 30%) nach Wohnfläche
        - consumption_percentage (default 70%) nach Verbrauch (Wärmemengenzähler)
        """
        from .consumption_calc import ConsumptionCalc

        contribution_results = []
        apartment_names = set()
        apartment_areas = {}
        temp_results = []

        total_days = (end_date - start_date).days
        total_consumption_value = Decimal('0.00')
        total_area_days = Decimal('0.00')
        total_consumption_unit = ""

        # Sammle alle Daten für beide Berechnungen (AREA + CONSUMPTION)
        for contribution in contributions:
            try:
                if not contribution.apartment:
                    raise ValueError(
                        "HEATING_MIXED requires an apartment with size_in_m2")
                if not contribution.consumption_calc:
                    raise ValueError(
                        "HEATING_MIXED requires consumption_calc for meter reading")

                apartment_area = contribution.apartment.size_in_m2 or Decimal(
                    '0')
                apartment_areas[contribution.apartment.id] = apartment_area

                # Hole Renter-Perioden
                periods = contribution.apartment.get_renters_for_period(
                    start_date=start_date,
                    end_date=end_date
                )

                for period in periods:
                    period_start = period['start_date']
                    period_end = period['end_date']
                    period_days = (period_end - period_start).days

                    # ConsumptionCalc-Zeitraumprüfung
                    calc_start = contribution.consumption_calc.start_date
                    calc_end = contribution.consumption_calc.end_date

                    if period_end <= calc_start:
                        continue
                    if calc_end is not None and period_start >= calc_end:
                        continue

                    adjusted_start = max(period_start, calc_start)
                    adjusted_end = min(
                        period_end, calc_end) if calc_end else period_end

                    if adjusted_start >= adjusted_end:
                        continue

                    # Berechne Verbrauch
                    consumption_result = contribution.consumption_calc.calculate(
                        start_date=adjusted_start,
                        end_date=adjusted_end
                    )
                    consumption_value = consumption_result.final_result

                    # Berechne Flächen-Anteil (m² × Tage)
                    adjusted_period_days = (adjusted_end - adjusted_start).days
                    area_days = apartment_area * \
                        Decimal(str(adjusted_period_days))

                    apartment_name = contribution.get_display_name()
                    apartment_names.add(apartment_name)

                    renter = period.get('renter')
                    renter_id = period.get('renter_id')

                    if not total_consumption_unit and consumption_result.calculation_steps:
                        final_step = consumption_result.calculation_steps[-1]
                        total_consumption_unit = final_step.unit or ""

                    temp_results.append({
                        'contribution': contribution,
                        'apartment_name': apartment_name,
                        'consumption_result': consumption_result,
                        'consumption_value': consumption_value,
                        'area_days': area_days,
                        'apartment_area': apartment_area,
                        'period_days': adjusted_period_days,
                        'renter_id': renter_id,
                        'renter_first_name': renter.first_name if renter else None,
                        'renter_last_name': renter.last_name if renter else None,
                        'period_start': adjusted_start,
                        'period_end': adjusted_end
                    })

                    total_consumption_value += consumption_value
                    total_area_days += area_days

            except Exception as e:
                consumption_calc_name = contribution.consumption_calc.name if contribution.consumption_calc else 'N/A'
                consumption_calc_id = contribution.consumption_calc.id if contribution.consumption_calc else 'N/A'
                raise ValueError(
                    f"Fehler bei HEATING_MIXED-Berechnung für Apartment {contribution.apartment} "
                    f"(CostCenterContribution ID: {contribution.id}, "
                    f"ConsumptionCalc: '{consumption_calc_name}' [ID: {consumption_calc_id}]): "
                    f"{str(e)}"
                ) from e

        # Berechne kombinierte Prozentsätze
        area_weight = self.area_percentage / Decimal('100')
        consumption_weight = self.consumption_percentage / Decimal('100')

        for temp_result in temp_results:
            # Flächenanteil berechnen
            if total_area_days > 0:
                area_pct = float(
                    (temp_result['area_days'] / total_area_days) * 100)
            else:
                area_pct = 0.0

            # Verbrauchsanteil berechnen
            if total_consumption_value > 0:
                consumption_pct = float(
                    (temp_result['consumption_value'] / total_consumption_value) * 100)
            else:
                consumption_pct = 0.0

            # Gewichtete Kombination: (area_pct × 0.30) + (consumption_pct × 0.70)
            combined_percentage = (
                area_pct * float(area_weight) +
                consumption_pct * float(consumption_weight)
            )

            # Dummy ConsumptionResult mit Berechnungsschritten erstellen
            dummy_result = ConsumptionCalc.ConsumptionResult(
                consumption_calc=temp_result['contribution'].consumption_calc,
                calculation_period_start=temp_result['period_start'],
                calculation_period_end=temp_result['period_end'],
                argument_results=[],
                final_result=temp_result['consumption_value'],
                calculation_steps=[
                    ConsumptionCalc.CalculationStep(
                        step_type="result",
                        description=f"Flächenanteil: {temp_result['apartment_area']} m² × {temp_result['period_days']} Tage = {area_pct:.2f}% × {self.area_percentage}%",
                        operand1=temp_result['apartment_area'],
                        operator="×",
                        operand2=Decimal(str(temp_result['period_days'])),
                        result=temp_result['area_days'],
                        argument_name=None,
                        source_details=None,
                        unit="m²×Tage",
                        operand1_label="Fläche",
                        operand2_label="Tage",
                        operand1_unit="m²",
                        operand2_unit="Tage"
                    ),
                    ConsumptionCalc.CalculationStep(
                        step_type="result",
                        description=f"Verbrauchsanteil: {temp_result['consumption_value']} {total_consumption_unit} = {consumption_pct:.2f}% × {self.consumption_percentage}%",
                        operand1=None,
                        operator=None,
                        operand2=None,
                        result=temp_result['consumption_value'],
                        argument_name=None,
                        source_details=None,
                        unit=total_consumption_unit
                    )
                ]
            )

            contribution_results.append(self.ContributionResult(
                contribution=temp_result['contribution'],
                apartment_name=temp_result['apartment_name'],
                consumption_calc_name=temp_result['contribution'].consumption_calc.name,
                consumption_result=dummy_result,
                final_consumption=temp_result['consumption_value'],
                percentage=combined_percentage,
                renter_id=temp_result['renter_id'],
                renter_first_name=temp_result['renter_first_name'],
                renter_last_name=temp_result['renter_last_name'],
                period_start=temp_result['period_start'],
                period_end=temp_result['period_end'],
                # HEATING_MIXED specific fields
                area_share=temp_result['area_days'],
                area_percentage_value=area_pct,
                consumption_share=temp_result['consumption_value'],
                consumption_percentage_value=consumption_pct
            ))

        # Berechne Gesamt-m² aller beteiligten Wohnungen
        total_area = sum(apartment_areas.values())

        return self.CostCenterCalculation(
            cost_center=self,
            calculation_period_start=start_date,
            calculation_period_end=end_date,
            contribution_results=contribution_results,
            total_consumption=total_consumption_value,
            apartment_count=len(apartment_names),
            total_consumption_unit=total_consumption_unit,
            total_days=total_days,
            total_area=total_area
        )

    def clean(self):
        """Validierung für HEATING_MIXED"""
        from django.core.exceptions import ValidationError
        super().clean() if hasattr(super(), 'clean') else None

        if self.distribution_type == self.DistributionType.HEATING_MIXED:
            total = self.area_percentage + self.consumption_percentage
            if total != Decimal('100.00'):
                raise ValidationError(
                    _("Area percentage + Consumption percentage must equal 100%% (currently: %(total)s%%)"),
                    params={'total': total}
                )
