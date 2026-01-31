"""
View für die Jahresabrechnung (Nebenkostenabrechnung).
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from datetime import date, timedelta
import decimal

from ...models import (
    Renter, AccountPeriod, Landlord, BankTransaction,
    RentPayment, YearlyAdjustment, RenterNotice
)
from .common import render_calculation_error, render_not_found_error


def calculate_rent_payments_for_renter(renter, billing_year: int):
    """
    Berechnet die Zahlungsdaten für einen Mieter im Abrechnungsjahr.

    Args:
        renter: Renter-Objekt
        billing_year: Das Abrechnungsjahr

    Returns:
        dict mit Zahlungsinformationen inkl. Kaltmiete, Vorauszahlungen, Anpassungen
    """
    year_start = date(billing_year, 1, 1)
    year_end = date(billing_year, 12, 31)

    # Banktransaktionen des Mieters für das Abrechnungsjahr
    transactions = BankTransaction.objects.filter(
        renter=renter,
        accounting_year=billing_year,
        transaction_type=BankTransaction.TransactionType.RENTER
    ).order_by('value_date')

    transaction_list = []
    total_payments = decimal.Decimal('0.00')
    for trans in transactions:
        transaction_list.append({
            'date': trans.value_date,
            'booking_text': trans.booking_text[:50] if trans.booking_text else '',
            'amount': trans.amount
        })
        total_payments += trans.amount

    # Hole alle RentPayments die das Jahr betreffen
    rent_periods = RentPayment.objects.filter(
        renter=renter,
        start_date__lte=year_end
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=year_start)
    ).order_by('start_date')

    cold_rent_total = decimal.Decimal('0.00')
    cold_rent_details = []

    for rent in rent_periods:
        # Bestimme den effektiven Zeitraum innerhalb des Jahres
        period_start = max(rent.start_date, year_start)
        period_end = min(
            rent.end_date, year_end) if rent.end_date else year_end

        if period_start <= period_end:
            # Anzahl der Monate berechnen (anteilig)
            months = decimal.Decimal('0')
            current = period_start
            while current <= period_end:
                # Tage in diesem Monat
                if current.month == 12:
                    next_month = date(current.year + 1, 1, 1)
                else:
                    next_month = date(
                        current.year, current.month + 1, 1)
                month_end = next_month - timedelta(days=1)

                # Effektiver Zeitraum in diesem Monat
                eff_start = max(current, period_start)
                eff_end = min(month_end, period_end)

                days_in_month = (
                    month_end - date(current.year, current.month, 1)).days + 1
                days_counted = (eff_end - eff_start).days + 1

                months += decimal.Decimal(days_counted) / \
                    decimal.Decimal(days_in_month)
                current = next_month

            amount = months * rent.cold_rent
            cold_rent_total += amount
            cold_rent_details.append({
                'months': round(months, 2),
                'monthly_rent': rent.cold_rent,
                'amount': round(amount, 2),
                'period_start': period_start,
                'period_end': period_end
            })

    # Perioden mit gleicher Kaltmiete zusammenfassen
    grouped_details = {}
    for detail in cold_rent_details:
        rent_key = detail['monthly_rent']
        if rent_key not in grouped_details:
            grouped_details[rent_key] = {
                'months': decimal.Decimal('0'),
                'monthly_rent': detail['monthly_rent'],
                'amount': decimal.Decimal('0'),
                'period_start': detail['period_start'],
                'period_end': detail['period_end']
            }
        grouped_details[rent_key]['months'] += decimal.Decimal(
            str(detail['months']))
        grouped_details[rent_key]['amount'] += decimal.Decimal(
            str(detail['amount']))
        # Erweitere den Zeitraum
        if detail['period_start'] < grouped_details[rent_key]['period_start']:
            grouped_details[rent_key]['period_start'] = detail['period_start']
        if detail['period_end'] > grouped_details[rent_key]['period_end']:
            grouped_details[rent_key]['period_end'] = detail['period_end']

    # Zurück in Liste umwandeln und runden
    cold_rent_details = [
        {
            'months': round(v['months'], 2),
            'monthly_rent': v['monthly_rent'],
            'amount': round(v['amount'], 2),
            'period_start': v['period_start'],
            'period_end': v['period_end']
        }
        for v in sorted(grouped_details.values(), key=lambda x: x['monthly_rent'])
    ]

    # Nebenkostenvorauszahlung berechnen
    advance_payment_total = total_payments - cold_rent_total

    # Zusätzliche Posten (YearlyAdjustments) laden
    adjustments = YearlyAdjustment.objects.filter(
        renter=renter,
        billing_year=billing_year
    ).order_by('description')

    adjustment_list = []
    adjustments_total = decimal.Decimal('0.00')
    for adj in adjustments:
        adjustment_list.append({
            'description': adj.description,
            'amount': adj.amount
        })
        adjustments_total += adj.amount

    return {
        'renter_id': renter.id,
        'renter_name': f"{renter.first_name} {renter.last_name}",
        'apartment_name': renter.apartment.name if renter.apartment else '',
        'transactions': transaction_list,
        'total_payments': total_payments,
        'cold_rent_total': round(cold_rent_total, 2),
        'cold_rent_details': cold_rent_details,
        'advance_payment_total': round(advance_payment_total, 2),
        'adjustments': adjustment_list,
        'adjustments_total': round(adjustments_total, 2),
    }


@login_required
@require_http_methods(["GET"])
def yearly_calculation(request, billing_year: int, renter_id: int = None):
    """
    View der die vollständige Berechnung aller AccountPeriods eines Jahres über ein Template ausgibt.

    Liefert sowohl Rechnungsdaten als auch Verbrauchsberechnungen pro CostCenter
    für alle AccountPeriods des angegebenen Abrechnungsjahres.

    URL: /yearly-calculation/<year>/
    URL: /yearly-calculation/<year>/renter/<renter_id>/

    Returns:
        Gerenderte HTML-Seite mit allen AccountPeriodCalculations des Jahres
    """
    try:
        # Alle AccountPeriods für das Jahr holen
        account_periods = AccountPeriod.objects.filter(
            billing_year=billing_year
        ).order_by('start_date')

        if not account_periods.exists():
            return render_not_found_error(request, billing_year)

        # Berechnungen für alle Perioden durchführen
        all_period_calculations = []
        grand_total_all_periods = decimal.Decimal('0.00')
        total_bill_count_all_periods = 0

        # Struktur für die Gesamttabelle: {renter_key: {cost_center_key: euro_anteil}}
        overall_summary = {}
        all_renters = {}  # {renter_id: {'first_name': ..., 'last_name': ...}}
        all_cost_centers = {}  # {cost_center_id: cost_center_text}

        # Nummerierung für Kostenstellen (Mieter-Ansicht)
        cost_center_numbers = {}  # {cost_center_name: nummer}
        next_cost_center_number = 1

        for account_period in account_periods:
            # Berechnung durchführen
            calculation = account_period.calculate_bills_by_cost_center()

            # Euro-Anteil für jede Contribution berechnen
            cost_center_summaries = []
            for summary in calculation.cost_center_summaries:
                total_amount = getattr(summary, 'total_amount', None)
                if not total_amount:
                    total_amount = 0

                # CostCenter für Gesamttabelle sammeln
                cost_center = summary.cost_center
                all_cost_centers[cost_center.id] = cost_center.text

                if hasattr(summary, 'cost_center_calculation') and summary.cost_center_calculation:
                    # Optional: Beiträge nach Renter-ID filtern
                    if renter_id is not None:
                        filtered_results = [
                            cr for cr in summary.cost_center_calculation.contribution_results
                            if cr.renter_id == renter_id
                        ]
                    else:
                        filtered_results = list(
                            summary.cost_center_calculation.contribution_results)

                    new_contribs = []
                    sum_euro_anteil = 0
                    for contrib in filtered_results:
                        perc = getattr(contrib, 'percentage', 0.0)
                        euro_anteil = (perc / 100) * float(total_amount)
                        contrib_dict = contrib._asdict()
                        contrib_dict['euro_anteil'] = euro_anteil

                        # HEATING_MIXED: Berechne separate Euro-Anteile für Fläche und Verbrauch
                        if cost_center.distribution_type == 'HEATING_MIXED':
                            area_pct = float(cost_center.area_percentage)
                            consumption_pct = float(cost_center.consumption_percentage)
                            area_percentage_value = getattr(contrib, 'area_percentage_value', 0.0)
                            consumption_percentage_value = getattr(contrib, 'consumption_percentage_value', 0.0)

                            # Betrag nach Fläche und Verbrauch
                            area_amount = float(total_amount) * area_pct / 100
                            consumption_amount = float(total_amount) * consumption_pct / 100

                            # Euro-Anteil für Fläche und Verbrauch
                            contrib_dict['area_euro'] = area_amount * area_percentage_value / 100
                            contrib_dict['consumption_euro'] = consumption_amount * consumption_percentage_value / 100
                            contrib_dict['area_amount_total'] = area_amount
                            contrib_dict['consumption_amount_total'] = consumption_amount

                        # Prüfe ob es eine special_designation gibt
                        contribution_obj = contrib.contribution
                        has_special_designation = bool(
                            contribution_obj and
                            hasattr(contribution_obj, 'special_designation') and
                            contribution_obj.special_designation and
                            contribution_obj.special_designation.strip()
                        )
                        contrib_dict['is_special_designation'] = has_special_designation

                        new_contribs.append(contrib_dict)
                        sum_euro_anteil += euro_anteil

                        # Für Gesamttabelle sammeln
                        r_id = contrib.renter_id
                        apartment_name = getattr(contrib, 'apartment_name', '')
                        if r_id:
                            renter_key = r_id
                            all_renters[r_id] = {
                                'first_name': contrib.renter_first_name,
                                'last_name': contrib.renter_last_name,
                                'apartment_name': apartment_name
                            }
                        else:
                            # Verwende apartment_name als Key für separate Summierung
                            renter_key = f'special_{apartment_name}'
                            if has_special_designation:
                                # Special Designation (z.B. Eigentümer)
                                all_renters[renter_key] = {
                                    'first_name': apartment_name,
                                    'last_name': '',
                                    'apartment_name': '',
                                    'is_special': True
                                }
                            else:
                                # Leerstand einer Wohnung
                                all_renters[renter_key] = {
                                    'first_name': 'Leerstand',
                                    'last_name': apartment_name,
                                    'apartment_name': '',
                                    'is_special': False
                                }

                        if renter_key not in overall_summary:
                            overall_summary[renter_key] = {}
                        if cost_center.id not in overall_summary[renter_key]:
                            overall_summary[renter_key][cost_center.id] = decimal.Decimal(
                                '0.00')
                        overall_summary[renter_key][cost_center.id] += decimal.Decimal(
                            str(euro_anteil))

                    calc_dict = summary.cost_center_calculation._asdict()
                    calc_dict['contribution_results'] = new_contribs

                    # Berechne Summe der Prozente für gefilterten Mieter (für Verbrauchsverteilung)
                    if renter_id is not None and cost_center.distribution_type == 'CONSUMPTION':
                        renter_contribs_for_sum = [
                            c for c in new_contribs
                            if c.get('renter_id') == renter_id
                        ]
                        calc_dict['renter_percentage_sum'] = sum(
                            c.get('percentage', 0) for c in renter_contribs_for_sum
                        )
                        calc_dict['renter_consumption_count'] = len(renter_contribs_for_sum)

                    summary_dict = summary._asdict() if hasattr(
                        summary, '_asdict') else dict(summary)
                    summary_dict['cost_center_calculation'] = calc_dict
                    summary_dict['total_amount'] = total_amount
                    summary_dict['sum_euro_anteil'] = sum_euro_anteil
                    # Flag: Hat diese Kostenstelle Beiträge für den gefilterten Mieter?
                    summary_dict['has_renter_contributions'] = len(
                        new_contribs) > 0
                    rounding_diff = round(
                        float(total_amount) - sum_euro_anteil, 2)
                    if abs(rounding_diff) >= 0.01:
                        summary_dict['rounding_diff'] = rounding_diff
                    else:
                        summary_dict['rounding_diff'] = None

                    # Nummerierung für Kostenstellen
                    cc_name = cost_center.text
                    if renter_id is not None:
                        # Mieter-Ansicht: nur nummerieren wenn Beiträge vorhanden
                        if summary_dict['has_renter_contributions']:
                            if cc_name not in cost_center_numbers:
                                cost_center_numbers[cc_name] = next_cost_center_number
                                next_cost_center_number += 1
                            summary_dict['cost_center_number'] = cost_center_numbers[cc_name]
                    else:
                        # Vermieter-Ansicht: alle Kostenstellen nummerieren
                        if cc_name not in cost_center_numbers:
                            cost_center_numbers[cc_name] = next_cost_center_number
                            next_cost_center_number += 1
                        summary_dict['cost_center_number'] = cost_center_numbers[cc_name]

                    # Nur hinzufügen wenn nicht nach Mieter gefiltert wird oder Beiträge vorhanden sind
                    if renter_id is None or summary_dict['has_renter_contributions']:
                        cost_center_summaries.append(summary_dict)
                else:
                    cost_center_summaries.append(summary)

            # Nur Perioden hinzufügen, die Kostenstellen haben (wichtig bei Mieter-Filter)
            if cost_center_summaries:
                # Prüfe ob es nicht-HEATING_MIXED Kostenstellen gibt
                has_non_heating_mixed = any(
                    s.get('cost_center', {}).distribution_type != 'HEATING_MIXED'
                    if hasattr(s.get('cost_center', {}), 'distribution_type')
                    else s.get('cost_center', {}).get('distribution_type') != 'HEATING_MIXED'
                    for s in cost_center_summaries
                    if s.get('cost_center_calculation')
                )
                has_consumption = any(
                    s.get('cost_center', {}).distribution_type == 'CONSUMPTION'
                    if hasattr(s.get('cost_center', {}), 'distribution_type')
                    else s.get('cost_center', {}).get('distribution_type') == 'CONSUMPTION'
                    for s in cost_center_summaries
                    if s.get('cost_center_calculation')
                )
                period_data = {
                    'account_period': account_period,
                    'calculation': calculation,
                    'cost_center_summaries': cost_center_summaries,
                    'has_non_heating_mixed': has_non_heating_mixed,
                    'has_consumption': has_consumption,
                    'summary': {
                        'grand_total': calculation.grand_total,
                        'total_bill_count': calculation.total_bill_count,
                        'cost_center_count': calculation.cost_center_count
                    }
                }
                all_period_calculations.append(period_data)
                grand_total_all_periods += calculation.grand_total
                total_bill_count_all_periods += calculation.total_bill_count

        # Gesamttabelle vorbereiten: Liste von {renter_info, cost_center_amounts, row_total}
        overall_table = []
        # Sortiere nach Kostenstellen-Nummer (statt alphabetisch)
        sorted_cost_center_ids = sorted(
            all_cost_centers.keys(),
            key=lambda x: cost_center_numbers.get(all_cost_centers[x], 999)
        )

        for renter_key, cost_centers in overall_summary.items():
            if renter_id is not None and renter_key != renter_id:
                continue
            renter_info = all_renters.get(
                renter_key, {'first_name': 'Unbekannt', 'last_name': '', 'apartment_name': ''})
            amounts = []
            row_total = decimal.Decimal('0.00')
            for cc_id in sorted_cost_center_ids:
                amount = cost_centers.get(cc_id, decimal.Decimal('0.00'))
                amounts.append(amount)
                row_total += amount
            # Nur Zeilen mit tatsächlichen Beträgen hinzufügen
            if row_total > 0:
                overall_table.append({
                    'renter_id': renter_key,
                    'renter_info': renter_info,
                    'amounts': amounts,
                    'row_total': row_total
                })

        # Nach Nachname sortieren
        overall_table.sort(key=lambda x: (
            x['renter_info']['last_name'], x['renter_info']['first_name']))

        # Bei Mieter-Filterung: Spalten mit 0,00 € ausblenden
        if renter_id is not None and overall_table:
            # Finde Spalten mit Werten > 0
            non_zero_columns = []
            for i, cc_id in enumerate(sorted_cost_center_ids):
                has_value = any(row['amounts'][i] > 0 for row in overall_table)
                if has_value:
                    non_zero_columns.append(i)

            # Filtere die Spalten
            filtered_cost_center_ids = [
                sorted_cost_center_ids[i] for i in non_zero_columns]
            for row in overall_table:
                row['amounts'] = [row['amounts'][i] for i in non_zero_columns]
            sorted_cost_center_ids = filtered_cost_center_ids

        # Spaltensummen berechnen
        column_totals = [decimal.Decimal('0.00')
                         for _ in sorted_cost_center_ids]
        grand_total_overall = decimal.Decimal('0.00')
        for row in overall_table:
            for i, amount in enumerate(row['amounts']):
                column_totals[i] += amount
            grand_total_overall += row['row_total']

        # Cost-Center-Namen als Liste in der richtigen Reihenfolge
        cost_center_names = [all_cost_centers[cc_id]
                             for cc_id in sorted_cost_center_ids]

        # Kombinierte Liste mit Namen und Nummern für die Gesamttabelle
        cost_center_headers = [
            {'name': name, 'number': cost_center_numbers.get(name, 0)}
            for name in cost_center_names
        ]

        # Vertikale Tabelle für Mieter-Ansicht vorbereiten
        # Pro Kostenstelle ein Eintrag mit Gesamtsumme
        vertical_table = []
        if renter_id is not None:
            # Sammle Euro-Anteile pro Kostenstelle (aggregiert über alle Perioden)
            cost_center_totals = {}  # {cost_center_name: {'amount': float, 'total_amount': float, 'is_direct': bool, 'number': int}}

            for period_data in all_period_calculations:
                for summary in period_data['cost_center_summaries']:
                    cost_center = summary.get('cost_center') if isinstance(summary, dict) else summary.cost_center
                    calc = summary.get('cost_center_calculation') if isinstance(summary, dict) else getattr(summary, 'cost_center_calculation', None)
                    total_amount = summary.get('total_amount', 0) if isinstance(summary, dict) else getattr(summary, 'total_amount', 0)
                    cc_number = summary.get('cost_center_number', 0) if isinstance(summary, dict) else getattr(summary, 'cost_center_number', 0)

                    if not calc:
                        continue

                    cc_name = cost_center.text if hasattr(cost_center, 'text') else cost_center.get('text', '')
                    distribution_type = cost_center.distribution_type if hasattr(cost_center, 'distribution_type') else cost_center.get('distribution_type')

                    # Hole die contribution_results
                    contribs = calc.get('contribution_results', []) if isinstance(calc, dict) else calc.contribution_results

                    # Prüfe ob dieser Mieter Contributions hat
                    renter_contribs = [
                        c for c in contribs
                        if (c.get('renter_id') if isinstance(c, dict) else c.renter_id) == renter_id
                    ]

                    if not renter_contribs:
                        continue

                    if distribution_type == 'DIRECT':
                        # Bei DIRECT: Bills direkt dem Mieter zuordnen
                        bills = summary.get('bills', []) if isinstance(summary, dict) else getattr(summary, 'bills', [])
                        for bill in bills:
                            bill_name = bill.text
                            if bill_name not in cost_center_totals:
                                cost_center_totals[bill_name] = {'amount': 0, 'total_amount': 0, 'is_direct': True, 'number': cc_number}
                            cost_center_totals[bill_name]['amount'] += float(bill.value)
                            cost_center_totals[bill_name]['total_amount'] += float(bill.value)
                    else:
                        # Berechne Euro-Anteil für diesen Mieter
                        sum_euro = sum(
                            (c.get('euro_anteil', 0) if isinstance(c, dict) else getattr(c, 'euro_anteil', 0))
                            for c in renter_contribs
                        )

                        if sum_euro > 0:
                            if cc_name not in cost_center_totals:
                                cost_center_totals[cc_name] = {'amount': 0, 'total_amount': 0, 'is_direct': False, 'number': cc_number}
                            cost_center_totals[cc_name]['amount'] += sum_euro
                            cost_center_totals[cc_name]['total_amount'] += float(total_amount)

            # Erstelle vertical_table aus aggregierten Daten, sortiert nach Nummer
            for cc_name, data in sorted(cost_center_totals.items(), key=lambda x: (x[1]['number'], x[0])):
                if data['is_direct']:
                    # DIRECT: Keine Berechnung anzeigen
                    vertical_table.append({
                        'cost_center_name': cc_name,
                        'amount': data['amount'],
                        'show_calculation': False,
                        'number': data['number'],
                    })
                else:
                    # Berechne Prozentsatz aus Anteil/Gesamtbetrag
                    total = data['total_amount']
                    amount = data['amount']
                    percentage = (amount / total * 100) if total > 0 else 0
                    vertical_table.append({
                        'cost_center_name': cc_name,
                        'amount': amount,
                        'show_calculation': True,
                        'total_amount': total,
                        'percentage': percentage,
                        'number': data['number'],
                    })

            renter_total = decimal.Decimal(str(sum(item['amount'] for item in vertical_table)))
        else:
            renter_total = decimal.Decimal('0.00')

        # Mieterdaten für gefilterte Ansicht (inkl. Adresse für Briefkopf)
        renter_filter_name = None
        renter_address = None
        if renter_id is not None:
            try:
                renter = Renter.objects.get(id=renter_id)
                if renter.apartment:
                    renter_filter_name = f"{renter.first_name} {renter.last_name} - {renter.apartment.name}"
                else:
                    renter_filter_name = f"{renter.first_name} {renter.last_name}"

                # Adresse für Briefkopf
                renter_address = {
                    'name': f"{renter.first_name} {renter.last_name}",
                    'street': renter.alt_street if renter.alt_street else (renter.apartment.street if renter.apartment else ''),
                    'postal_code': renter.postal_code if renter.postal_code else (renter.apartment.postal_code if renter.apartment else ''),
                    'city': renter.city if renter.city else (renter.apartment.city if renter.apartment else ''),
                }
            except Renter.DoesNotExist:
                renter_filter_name = f"Mieter #{renter_id}"

        # Mietzahlungen und Kaltmiete berechnen
        rent_payments_data = None
        all_renters_payments = []

        if renter_id is not None:
            # Einzelner Mieter
            try:
                renter = Renter.objects.get(id=renter_id)
                rent_payments_data = calculate_rent_payments_for_renter(
                    renter, billing_year)
                # Tatsächliche Nebenkosten hinzufügen (aus renter_total)
                rent_payments_data['actual_costs'] = renter_total
                # Ergebnis berechnen: Vorauszahlung - tatsächliche Kosten + Anpassungen
                # Positiv = Guthaben für Mieter, Negativ = Nachzahlung
                rent_payments_data['balance'] = (
                    rent_payments_data['advance_payment_total']
                    - renter_total
                    + rent_payments_data['adjustments_total']
                )
            except Renter.DoesNotExist:
                pass
        else:
            # Alle Mieter die im Jahr aktiv waren
            year_start = date(billing_year, 1, 1)
            year_end = date(billing_year, 12, 31)

            active_renters = Renter.objects.filter(
                move_in_date__lte=year_end
            ).filter(
                Q(move_out_date__isnull=True) | Q(
                    move_out_date__gte=year_start)
            ).exclude(
                is_owner_occupied=True
            ).select_related('apartment').order_by('apartment__number', 'last_name')

            for renter in active_renters:
                renter_data = calculate_rent_payments_for_renter(
                    renter, billing_year)
                # Nur hinzufügen wenn es Zahlungen oder Kaltmiete gibt
                if renter_data['transactions'] or renter_data['cold_rent_details']:
                    # Tatsächliche Nebenkosten aus overall_summary holen
                    actual_costs = overall_summary.get(renter.id, {})
                    total_costs = sum(actual_costs.values(
                    )) if actual_costs else decimal.Decimal('0.00')
                    renter_data['actual_costs'] = total_costs
                    # Ergebnis berechnen inkl. Anpassungen
                    renter_data['balance'] = (
                        renter_data['advance_payment_total']
                        - total_costs
                        + renter_data['adjustments_total']
                    )
                    all_renters_payments.append(renter_data)

        # Vermieterdaten laden
        landlord = Landlord.get_instance()

        # Hinweise für Mieter laden
        renter_notices = []
        if renter_id is not None:
            renter_notices = RenterNotice.objects.filter(
                billing_year=billing_year,
                renters__id=renter_id
            ).order_by('title')

        # Zahlungszieldatum für Nachzahlung (14 Tage ab heute, nicht am Wochenende)
        payment_due_date = date.today() + timedelta(days=14)
        # Samstag (5) -> Montag (+2), Sonntag (6) -> Montag (+1)
        if payment_due_date.weekday() == 5:
            payment_due_date += timedelta(days=2)
        elif payment_due_date.weekday() == 6:
            payment_due_date += timedelta(days=1)

        context = {
            'billing_year': billing_year,
            'all_period_calculations': all_period_calculations,
            'grand_total_all_periods': grand_total_all_periods,
            'total_bill_count_all_periods': total_bill_count_all_periods,
            'period_count': len(all_period_calculations),
            'renter_filter_id': renter_id,
            'renter_filter_name': renter_filter_name,
            'renter_address': renter_address,
            'landlord': landlord,
            'payment_due_date': payment_due_date,
            # Gesamttabelle
            'overall_table': overall_table,
            'cost_center_names': cost_center_names,
            'cost_center_headers': cost_center_headers,
            'column_totals': column_totals,
            'grand_total_overall': grand_total_overall,
            # Vertikale Tabelle für Mieter-Ansicht
            'vertical_table': vertical_table,
            'renter_total': renter_total,
            # Mietzahlungen und Kaltmiete
            'rent_payments_data': rent_payments_data,
            'all_renters_payments': all_renters_payments,
            # Hinweise für Mieter
            'renter_notices': renter_notices,
        }

        return render(request, 'yearly_calculation.html', context)

    except Exception as e:
        return render_calculation_error(request, billing_year, e)
