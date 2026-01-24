from time import sleep
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
import os

from .models import Renter, HeatingInfo, MeterReading, Meter, HeatingInfoTemplate, ConsumptionCalc, CostCenterContribution, AccountPeriod, MeterPlace, Landlord, Apartment, CostCenter, BankTransaction, RentPayment, YearlyAdjustment
from weasyprint import HTML
from django.conf import settings
from django.db.models import Q
from datetime import datetime, timedelta, date
import decimal
import json
from django.forms.models import model_to_dict
from django.db.models.query import QuerySet

import logging

logger = logging.getLogger(__name__)


def custom_login(request):
    """Custom login view that supports both OIDC and local authentication"""
    context = {
        'USE_OIDC_ONLY': getattr(settings, 'USE_OIDC_ONLY', False),
        'INSTALLED_APPS': settings.INSTALLED_APPS,
    }
    return render(request, 'registration/login.html', context)


@login_required
def index(request):
    """Redirect zum Admin Dashboard"""
    from django.shortcuts import redirect
    return redirect('/admin/')


@login_required
def dashboard_stats_api(request):
    """API-Endpunkt für Dashboard-Statistiken (JSON)"""
    stats = {
        'apartments': Apartment.objects.count(),
        'active_renters': Renter.objects.filter(move_out_date__isnull=True).count(),
        'meters': Meter.objects.filter(out_of_order_date__isnull=True).count(),
        'cost_centers': CostCenter.objects.count(),
    }

    def get_active_renters_for_year(year):
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        return Renter.objects.filter(
            move_in_date__lte=year_end
        ).filter(
            Q(move_out_date__isnull=True) |
            Q(move_out_date__gte=year_start)
        ).select_related('apartment').order_by('apartment__number', 'last_name')

    current_year = datetime.now().year
    available_years = []
    for year in range(current_year, current_year - 4, -1):
        if AccountPeriod.objects.filter(billing_year=year).exists():
            renters = get_active_renters_for_year(year)
            available_years.append({
                'year': year,
                'renters': [
                    {'id': r.id, 'name': f"{r.first_name} {r.last_name}",
                        'apartment_number': r.apartment.number}
                    for r in renters
                ]
            })
        if len(available_years) >= 3:
            break

    return JsonResponse({
        **stats,
        'available_years': available_years,
    })


def to_datetime(date):
    return datetime(year=date.year, month=date.month, day=date.day)


def calculate_max(value: decimal.Decimal, current_max: decimal.Decimal) -> decimal.Decimal:
    max_factor = decimal.Decimal(1.4)
    if value:
        return max(current_max, value * max_factor)
    else:
        return current_max


def get_heating_info_context(request, renter_id: int):
    renter = Renter.objects.get(id=renter_id)
    today = datetime.now()
    first_day_of_current_month = today.replace(day=1)
    last_day_of_last_month = first_day_of_current_month - timedelta(days=1)
    end_date_year = last_day_of_last_month.year
    end_date_month = last_day_of_last_month.month
    start_date_year = first_day_of_current_month.year-2
    start_date_month = first_day_of_current_month.month

    if to_datetime(renter.move_in_date) > datetime(year=start_date_year, month=start_date_month, day=1):
        start_date_month = renter.move_in_date.month
        start_date_year = renter.move_in_date.year
        if renter.move_in_date.day > 1:
            if start_date_month < 12:
                start_date_month = start_date_month+1
            else:
                start_date_month = 1
                start_date_year = start_date_year+1
    if renter.move_out_date is not None and renter.move_out_date < last_day_of_last_month:
        # Keinen Context zurückgeben, Mieter braucht für diesen Monat keine Heating Info
        return None

    # Abfrage durchführen

    heating_info_entries = HeatingInfo.objects.filter(
        (Q(year=start_date_year, month__gte=start_date_month) |
         Q(year__gt=start_date_year)),
        apartment_id=renter.apartment.id
        # Ergebnisse nach Jahr und Monat sortieren
    ).order_by('year', 'month').reverse()

    heating = []
    hot_water = []
    max_heating = 100
    max_water = 100
    for ele in heating_info_entries:
        max_heating = calculate_max(ele.heating_energy_kwh, max_heating)
        max_heating = calculate_max(
            ele.compare_heating_energy_kwh, max_heating)
        max_water = calculate_max(ele.hot_water_energy_kwh, max_water)
        max_water = calculate_max(ele.compare_hot_water_energy_kwh, max_water)

    for i in range(12):
        if len(heating_info_entries) > i:
            entry = heating_info_entries[i]
            heating_year_before = None
            if len(heating_info_entries) >= i+12:
                heating_year_before = heating_info_entries[i +
                                                           12].heating_energy_kwh
                water_year_before = heating_info_entries[i +
                                                         12].hot_water_energy_kwh
            if entry.heating_energy_kwh is not None:
                comp_percent = 0
                if entry.compare_heating_energy_kwh:
                    comp_percent = 100 * \
                        (entry.compare_heating_energy_kwh/max_heating)
                date = datetime(year=entry.year, month=entry.month, day=1)
                heating.append({
                    'date': date,
                    'actual': entry.heating_energy_kwh,
                    'year_before': heating_year_before,
                    'compare': entry.compare_heating_energy_kwh,
                    'actual_percent': 100 * (entry.heating_energy_kwh/max_heating),
                    'compare_percent': comp_percent
                })
            if entry.hot_water_energy_kwh is not None:
                hot_water.append({
                    'date': date,
                    'actual': entry.hot_water_energy_kwh,
                    'year_before': water_year_before,
                    'compare': entry.compare_hot_water_energy_kwh,
                    'actual_percent': 100 * (entry.hot_water_energy/max_water),
                    'compare_percent': 100 * (entry.compare_hot_water_energy_kwh/max_water),
                })

    context = {
        'renter': renter,
        'apartment': renter.apartment,
        'heating': heating,
        'hot_water': hot_water,
        'landlord_info': settings.HEATING_INFO_FOOTER,
        'page_break': (len(hot_water)+len(heating)) > 18,
    }
    return context


@login_required
def heating_info(request, id: int):
    template = loader.get_template('heating_info.html')
    context = get_heating_info_context(request=request, renter_id=id)
    html = template.render(context, request)
    return HttpResponse(html)


@login_required
def heating_info_pdf(request, id: int):
    template = loader.get_template('heating_info.html')
    context = get_heating_info_context(request=request, renter_id=id)
    html = template.render(context, request)

    # Generiere das PDF mit WeasyPrint
    pdf = HTML(string=html).write_pdf()

    # Sende die PDF-Datei als HTTP-Antwort zurück
    response = HttpResponse(pdf, content_type='application/pdf')
    # response['Content-Disposition'] = 'attachment; filename="heating_info.pdf"'
    response['Content-Disposition'] = 'inline; filename="heating_info.pdf"'

    return response


def interpolate_reading(before, after, target_date):
    """
    Berechnet einen interpolierten Messwert für ein Ziel-Datum.
    :param before: Das erste MeterReading-Objekt vor dem Ziel-Datum.
    :param after: Das erste MeterReading-Objekt nach dem Ziel-Datum.
    :param target_date: Das Datum, für das interpoliert werden soll.
    :return: Der interpolierte Messwert.
    """
    days_between = (after.date - before.date).days
    daily_change = (after.meter_reading - before.meter_reading) / days_between
    interpolated_value = round(before.meter_reading +
                               daily_change * (target_date - before.date).days)
    return interpolated_value


def calculate_meter_consumption(meter_id: int, start_date: date, end_date: date):
    readings = MeterReading.objects.filter(
        meter_id=meter_id,
        date__range=(start_date, end_date)
    ).order_by('date')

    # Falls Messungen außerhalb des Zeitraums fehlen, die naheliegenden Messwerte abrufen
    before_start = None
    # return not readings or readings.first().date > start_date
    if not readings or readings.first().date > start_date:
        before_start = MeterReading.objects.filter(
            meter_id=meter_id, date__lt=start_date
        ).order_by('-date').first()

    after_end = None
    if not readings or readings.last().date < end_date:
        after_end = MeterReading.objects.filter(
            meter_id=meter_id, date__gt=end_date
        ).order_by('date').first()

    readings_rtn = []
    # Bestimme den Startwert
    if readings and readings.first().date <= start_date:
        start_reading = readings.first().meter_reading
        readings_rtn.append({
            'date': readings.first().date,
            'value': start_reading,
            'calulated': False
        })
    else:
        if before_start and readings:
            # Lineare Interpolation für Startwert
            start_reading = interpolate_reading(
                before_start, readings.first(), start_date)
            readings_rtn.append({
                'date': before_start.date,
                'value': before_start.meter_reading,
                'calculated': False,
            })
            readings_rtn.append({
                'date': start_date,
                'value': start_reading,
                'calculated': True,
            })
            readings_rtn.append({
                'date': readings.first().date,
                'value': readings.first().meter_reading,
                'calculated': False,
            })

        elif before_start and after_end:
            # Falls keine Messwerte im Zeitraum, aber vor/nachher Messungen
            start_reading = interpolate_reading(
                before_start, after_end, start_date)
            readings_rtn.append({
                'date': before_start.date,
                'value': before_start.reading,
                'calculated': False,
            })
            readings_rtn.append({
                'date': start_date,
                'value': start_reading,
                'calculated': True,
            })
        else:
            raise ValueError(
                f"Nicht genug Messwerte in Meter {meter_id} vorhanden, um Startwert {start_date} zu interpolieren")

    # Bestimme den Endwert
    if readings and readings.last().date >= end_date:
        end_reading = readings.last().meter_reading
        readings_rtn.append({
            'date': readings.last().date,
            'value': end_reading,
            'calulated': False
        })
    else:
        if readings and after_end:
            end_reading = interpolate_reading(
                readings.last(), after_end, end_date)
            readings_rtn.append({
                'date': readings.last().date,
                'value': readings.last().meter_reading,
                'calculated': False,
            })
            readings_rtn.append({
                'date': end_date,
                'value': end_reading,
                'calculated': True,
            })
            readings_rtn.append({
                'date': after_end.date,
                'value': after_end.meter_reading,
                'calculated': False,
            })
        elif before_start and after_end:
            end_reading = interpolate_reading(
                before_start, after_end, end_date)
            readings_rtn.append({
                'date': end_date,
                'value': end_reading,
                'calculated': True,
            })
            readings_rtn.append({
                'date': after_end.date,
                'value': after_end.meter_reading,
                'calculated': False,
            })
        else:
            raise ValueError(
                "Nicht genug Messwerte vorhanden, um Endwert zu interpolieren")
    ohne_duplikate = []
    for element in readings_rtn:
        if element['date'] not in list(map(lambda x: x['date'], ohne_duplikate)):
            ohne_duplikate.append(element)
    return {
        # Verbrauch berechnen
        'consumption': (end_reading - start_reading),
        'readings': ohne_duplikate
    }


def calculate_meter_place_consumption(meter_place_id: int, start_date: date, end_date: date):
    meters = Meter.objects.filter(
        place_id=meter_place_id,
        build_in_date__lte=end_date,
    ).filter(
        Q(out_of_order_date__gte=start_date) |
        Q(out_of_order_date__isnull=True)
    ).order_by('build_in_date')
    m_start_date = start_date
    rtn = []
    sum = 0
    for meter in meters:
        if meter.out_of_order_date is None:
            m_end_date = end_date
        else:
            m_end_date = meter.out_of_order_date

        mconsumption = calculate_meter_consumption(
            meter.id, m_start_date, m_end_date)
        rtn.append({
            'meter': model_to_dict(meter),
            'start_date': m_start_date,
            'end_date': m_end_date,
            'consumption': mconsumption,
        })
        sum = sum + mconsumption['consumption']
        m_start_date = m_end_date
    return {
        'consumption': sum,
        'meters': rtn,
        'place': model_to_dict(meters.first().place)
    }


def serialize_helper(obj):
    if isinstance(obj, date):
        return obj.isoformat()

    if isinstance(obj, decimal.Decimal):
        return float(obj)

    if isinstance(obj, QuerySet):
        return 'XXY'

    if isinstance(obj, MeterReading):
        return 'XXX'

    raise TypeError("Type not serializable")


@login_required
def meter_place_consumption(request, meter_place: int, start_date: date, end_date: date):
    consumption = calculate_meter_place_consumption(
        meter_place, start_date, end_date)
    # consumption = calculate_meter_consumption(
    #    4, date(2024, 7, 1), date(2024, 9, 6))

    # huhu = {'x': 42}
    # Sende die PDF-Datei als HTTP-Antwort zurück
    response = HttpResponse(json.dumps(
        consumption, default=serialize_helper), content_type='text/json')
    # response['Content-Disposition'] = 'attachment; filename="heating_info.pdf"'

    return response


# Die Funktionen process_calc_argument und calc_consumption_calc wurden entfernt.
# Stattdessen wird die calculate()-Methode des ConsumptionCalc-Models verwendet.


@login_required
def heating_info_task(request):
    today = date.today()
    year = today.year
    month = today.month
    if month == 1:
        year = year-1
        month = 12
    else:
        month = month-1
    templates = HeatingInfoTemplate.objects.filter(Q(next_year__lt=year) |
                                                    (Q(next_year=year) & Q(
                                                        next_month__lte=month))
                                                   ).order_by('next_year', 'next_month')
    data = {}
    if templates:
        calc_year = templates[0].next_year
        calc_month = templates[0].next_month
        next_year = templates[0].next_year
        next_month = templates[0].next_month+1
        if next_month > 12:
            next_month = 1
            next_year = next_year+1
        start_date = date(calc_year, calc_month, 1)
        end_date = date(next_year, next_month, 1)
        month_okay = True
        compare_group = {}
        val = {}
        for template in templates:
            for groupname in [f"h{template.compare_heating_group}", f"w{template.compare_heating_group}"]:
                if groupname not in compare_group:
                    compare_group[groupname] = {
                        'm2': 0,
                        'sum': 0,
                        'num': 0
                    }
            if month_okay and template.next_year == calc_year and template.next_month == calc_month:
                if template.calc_heating is not None:
                    try:
                        result = template.calc_heating.calculate(
                            start_date, end_date)
                        heat_val = result.value if result.success else None
                    except:
                        heat_val = None
                    if heat_val is None:
                        month_okay = False
                    else:
                        groupname = f"h{template.compare_heating_group}"
                        compare_group[groupname]['sum'] = compare_group[groupname]['sum'] + heat_val
                        compare_group[groupname]['m2'] = compare_group[groupname]['m2'] + \
                            template.apartment.size_in_m2
                        val[f"h{template.id}"] = heat_val
                if template.calc_hot_water is not None:
                    try:
                        result = template.calc_hot_water.calculate(
                            start_date, end_date)
                        water_val = result.value if result.success else None
                    except:
                        water_val = None
                    if water_val is None:
                        month_okay = False
                    else:
                        groupname = f"w{template.compare_heating_group}"
                        compare_group[groupname]['sum'] = compare_group[groupname]['sum'] + water_val
                        compare_group[groupname]['num'] = compare_group[groupname]['num'] + 1
                        val[f"w{template.id}"] = water_val

        if month_okay:
            for template in templates:
                if template.next_year == calc_year and template.next_month == calc_month:
                    groupname = f"h{template.compare_heating_group}"
                    heating_energy = None
                    compare_heating_energy = None
                    if f"h{template.id}" in val:
                        heating_energy = val[f"h{template.id}"]
                        compare_heating_energy = template.apartment.size_in_m2 * (compare_group[groupname]['sum'] /
                                                                                  compare_group[groupname]['m2'])
                    hot_water_energy = None
                    compare_water_energy = None
                    m3_hot_water = None
                    if f"w{template.id}" in val:
                        m3_hot_water = val[f"w{template.id}"]
                        hot_water_energy = m3_hot_water*template.kwh_per_m3_hot_water
                        groupname = f"w{template.compare_heating_group}"
                        compare_water_m3 = compare_group[groupname]['sum'] / \
                            compare_group[groupname]['num']
                        compare_water_energy = compare_water_m3*template.kwh_per_m3_hot_water

                    hi = HeatingInfo(
                        apartment=template.apartment,
                        year=calc_year,
                        month=calc_month,
                        heating_energy_kwh=heating_energy,
                        compare_heating_energy_kwh=compare_heating_energy,
                        hot_water_energy_kwh=hot_water_energy,
                        compare_hot_water_energy_kwh=compare_water_energy,
                        hot_water_m3=m3_hot_water
                    )
                    hi.save()
                    template.next_year = next_year
                    template.next_month = next_month
                    template.save()
    response = HttpResponse(json.dumps(
        data), content_type='text/json')
    # response['Content-Disposition'] = 'attachment; filename="heating_info.pdf"'

    return response


@login_required
@require_http_methods(["GET"])
def yearly_calculation(request, billing_year: int, renter_id: int = None):
    """
    View der die vollständige Berechnung aller AccountPeriods eines Jahres über ein Template ausgibt.

    Liefert sowohl Rechnungsdaten als auch Verbrauchsberechnungen pro CostCenter
    für alle AccountPeriods des angegebenen Abrechnungsjahres.

    URL: /yearly-calculation/<year>/
    URL: /yearly-calculation/<year>/renter/<renter_id>/
    Method: GET

    Returns:
        Gerenderte HTML-Seite mit allen AccountPeriodCalculations des Jahres
    """
    try:
        # Alle AccountPeriods für das Jahr holen
        account_periods = AccountPeriod.objects.filter(
            billing_year=billing_year
        ).order_by('start_date')

        if not account_periods.exists():
            error_context = {
                'error_message': f'Keine Abrechnungsperioden für das Jahr {billing_year} gefunden.',
                'error_type': 'NotFound',
                'billing_year': billing_year,
                'debug': settings.DEBUG
            }
            return render(request, 'yearly_calculation_error.html', error_context, status=404)

        # Berechnungen für alle Perioden durchführen
        all_period_calculations = []
        grand_total_all_periods = decimal.Decimal('0.00')
        total_bill_count_all_periods = 0

        # Struktur für die Gesamttabelle: {renter_key: {cost_center_key: euro_anteil}}
        overall_summary = {}
        all_renters = {}  # {renter_id: {'first_name': ..., 'last_name': ...}}
        all_cost_centers = {}  # {cost_center_id: cost_center_text}

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
        sorted_cost_center_ids = sorted(
            all_cost_centers.keys(), key=lambda x: all_cost_centers[x])

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

        # Vertikale Tabelle für Mieter-Ansicht vorbereiten
        vertical_table = []
        if renter_id is not None and overall_table:
            row = overall_table[0]  # Bei Mieter-Filter gibt es nur eine Zeile
            for i, cc_name in enumerate(cost_center_names):
                vertical_table.append({
                    'cost_center_name': cc_name,
                    'amount': row['amounts'][i]
                })
            renter_total = row['row_total']
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

        # Hilfsfunktion: Zahlungsdaten für einen Mieter berechnen
        def calculate_rent_payments_for_renter(renter, billing_year):
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
            # Gesamttabelle
            'overall_table': overall_table,
            'cost_center_names': cost_center_names,
            'column_totals': column_totals,
            'grand_total_overall': grand_total_overall,
            # Vertikale Tabelle für Mieter-Ansicht
            'vertical_table': vertical_table,
            'renter_total': renter_total,
            # Mietzahlungen und Kaltmiete
            'rent_payments_data': rent_payments_data,
            'all_renters_payments': all_renters_payments,
        }

        return render(request, 'yearly_calculation.html', context)

    except Exception as e:
        logger.exception(
            "Error calculating yearly calculation for %s: %s",
            billing_year,
            str(e)
        )

        import traceback
        traceback_str = traceback.format_exc()

        error_context = {
            'error_message': str(e),
            'error_type': type(e).__name__,
            'billing_year': billing_year,
            'traceback': traceback_str,
            'debug': settings.DEBUG
        }
        return render(request, 'yearly_calculation_error.html', error_context, status=500)


@login_required
@require_http_methods(["GET", "POST"])
def meter_readings_input(request):
    """
    View für die einfache Eingabe von Zählerständen.

    GET: Zeigt Formular mit aktiven Zählern für ein Datum an
    POST: Speichert die eingegebenen Zählerstände
    """
    target_date = None
    meters_data = []
    success_message = None
    error_messages = []

    target_date_str = request.GET.get('date')
    if target_date_str:
        try:
            target_date = datetime.strptime(
                target_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    # Standard: heute
    if not target_date:
        target_date = date.today()

    # Aktive Zähler für das Datum finden
    active_meters = Meter.objects.filter(
        build_in_date__lte=target_date
    ).filter(
        Q(out_of_order_date__isnull=True) | Q(
            out_of_order_date__gte=target_date)
    ).select_related('place')

    # Sortierung nach Standort (location), dann Typ, dann Zählernummer
    active_meters = active_meters.order_by(
        'place__location', 'place__type', 'meter_number')

    # Daten für jeden aktiven Zähler sammeln
    for meter in active_meters:
        # Letzten Zählerstand finden
        last_reading = MeterReading.objects.filter(
            meter=meter,
            date__lt=target_date
        ).order_by('-date').first()

        # Aktuellen Zählerstand für das Zieldatum finden (falls bereits eingegeben)
        current_reading = MeterReading.objects.filter(
            meter=meter,
            date=target_date
        ).first()
        logger.error(
            f"Current reading for meter {meter.id} on {target_date}: {current_reading}")
        meters_data.append({
            'meter': meter,
            'meter_place': meter.place,
            'last_reading': last_reading,
            'current_reading': current_reading,
        })

    context = {
        'target_date': target_date,
        'meters_data': meters_data,
        'success_message': success_message,
        'error_messages': error_messages,
    }

    return render(request, 'meter_readings_input.html', context)


@login_required
@require_http_methods(["POST"])
def meter_readings_save_single(request):
    """
    AJAX View für das Speichern einzelner Zählerstände.

    Erwartet POST-Parameter:
    - meter_id: ID des Meters
    - reading_value: Zählerstand-Wert
    - target_date: Datum des Zählerstands
    """
    try:
        meter_id = request.POST.get('meter_id')
        reading_value = request.POST.get('reading_value')
        target_date_str = request.POST.get('target_date')

        if not all([meter_id, reading_value, target_date_str]):
            return JsonResponse({'success': False, 'error': 'Fehlende Parameter'})

        # Validierung
        try:
            meter = Meter.objects.get(pk=int(meter_id))
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
            reading_decimal = decimal.Decimal(reading_value.replace(',', '.'))
        except (Meter.DoesNotExist, ValueError, decimal.InvalidOperation) as e:
            return JsonResponse({'success': False, 'error': f'Ungültige Daten: {str(e)}'})

        # Prüfen ob Meter zum Datum aktiv war
        if target_date < meter.build_in_date:
            return JsonResponse({
                'success': False,
                'error': f'Zähler war am {target_date} noch nicht aktiv (Einbaudatum: {meter.build_in_date})'
            })

        if meter.out_of_order_date and target_date > meter.out_of_order_date:
            return JsonResponse({
                'success': False,
                'error': f'Zähler war am {target_date} bereits außer Betrieb (Ausbaudatum: {meter.out_of_order_date})'
            })
        # Speichern oder aktualisieren
        reading, created = MeterReading.objects.update_or_create(
            meter=meter,
            date=target_date,
            defaults={
                'meter_reading': reading_decimal,
                'time': None  # Zeit wird nicht von der Eingabeseite gesetzt
            }
        )

        return JsonResponse({
            'success': True,
            'created': created,
            'reading_id': reading.id,
            'formatted_value': str(reading.meter_reading)
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Serverfehler: {str(e)}'})


@login_required
@require_http_methods(["GET"])
def costcenter_distribution_type(request, cost_center_id):
    """
    API-Endpunkt für den Admin: Gibt den distribution_type eines CostCenters zurück.
    Wird verwendet um das consumption_calc Feld dynamisch ein-/auszublenden.
    """
    from .models import CostCenter

    try:
        cost_center = CostCenter.objects.get(id=cost_center_id)
        # CONSUMPTION and HEATING_MIXED both require consumption_calc
        show_consumption = cost_center.distribution_type in [
            CostCenter.DistributionType.CONSUMPTION,
            CostCenter.DistributionType.HEATING_MIXED
        ]
        return JsonResponse({
            'success': True,
            'distribution_type': cost_center.distribution_type,
            'show_consumption_calc': show_consumption
        })
    except CostCenter.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'CostCenter not found'
        }, status=404)


def check_mbus_api_key(view_func):
    """Decorator to check M-Bus API key from environment variable."""
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        api_key = os.environ.get('MBUS_API_KEY', '')
        if not api_key:
            logger.error("MBUS_API_KEY environment variable not set")
            return JsonResponse({
                'success': False,
                'error': 'API not configured'
            }, status=500)

        # Check Authorization header
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            provided_key = auth_header[7:]
        else:
            provided_key = request.headers.get('X-API-Key', '')

        if provided_key != api_key:
            logger.warning("Invalid API key provided for M-Bus API")
            return JsonResponse({
                'success': False,
                'error': 'Invalid API key'
            }, status=401)

        return view_func(request, *args, **kwargs)
    return wrapper


@csrf_exempt
@require_http_methods(["POST"])
@check_mbus_api_key
def mbus_readings_import(request):
    """
    API-Endpunkt für den Import von M-Bus Zählerwerten.

    Erwartet JSON oder YAML im Body mit einer Liste von Messwerten:
    [
        {
            "meter_id": 11367181,
            "timestamp": "2026-01-04T00:37:00",
            "type": "heat",
            "value": 2843
        },
        ...
    ]

    Authentifizierung via:
    - Header: Authorization: Bearer <API_KEY>
    - Header: X-API-Key: <API_KEY>

    API_KEY wird aus der Environment Variable MBUS_API_KEY gelesen.
    """
    from datetime import datetime as dt

    body = request.body.decode('utf-8')

    # Parse JSON input
    try:
        readings_data = json.loads(body)
    except json.JSONDecodeError as e:
        return JsonResponse({
            'success': False,
            'error': f'Invalid JSON format: {str(e)}'
        }, status=400)

    if not isinstance(readings_data, list):
        return JsonResponse({
            'success': False,
            'error': 'Input must be a list of readings'
        }, status=400)

    results = {
        'imported': 0,
        'skipped_existing': 0,
        'skipped_no_meter': 0,
        'skipped_type_mismatch': 0,
        'skipped_invalid_value': 0,
        'errors': []
    }

    for reading in readings_data:
        try:
            mbus_id = str(reading.get('mbus_id', ''))
            timestamp_str = reading.get('timestamp', '')
            value = reading.get('value')
            reading_type = reading.get('type', '')

            if not all([mbus_id, timestamp_str, value is not None]):
                results['errors'].append(
                    f"Missing required fields in: {reading}")
                continue

            # Parse timestamp
            try:
                if isinstance(timestamp_str, str):
                    timestamp = dt.fromisoformat(
                        timestamp_str.replace('Z', '+00:00'))
                else:
                    timestamp = timestamp_str
                reading_date = timestamp.date()
                reading_time = timestamp.time()
            except (ValueError, AttributeError) as e:
                results['errors'].append(
                    f"Invalid timestamp for mbus_id {mbus_id}: {timestamp_str}")
                continue

            # Find meter with remote_type='mbus' and remote_address=mbus_id
            try:
                meter = Meter.objects.get(
                    remote_type=Meter.RemoteType.MBUS,
                    remote_address=mbus_id
                )
            except Meter.DoesNotExist:
                logger.info(
                    f"No M-Bus meter found with mbus_id={mbus_id}")
                results['skipped_no_meter'] += 1
                continue
            except Meter.MultipleObjectsReturned:
                logger.warning(
                    f"Multiple M-Bus meters found with mbus_id={mbus_id}")
                results['errors'].append(
                    f"Multiple meters found for mbus_id {mbus_id}")
                continue

            # Validate meter type matches the reading type
            if reading_type and meter.place.type != reading_type:
                logger.warning(
                    f"Type mismatch for meter {meter.id} (mbus_id={mbus_id}): expected {reading_type} "
                    f"but meter place type is {meter.place.type}"
                )
                results['skipped_type_mismatch'] += 1
                continue

            # Check if reading for this day already exists
            existing_reading = MeterReading.objects.filter(
                meter=meter,
                date=reading_date
            ).first()

            if existing_reading:
                logger.warning(
                    f"Reading already exists for meter {meter.id} (mbus_id={mbus_id}) on {reading_date}: "
                    f"DB={existing_reading.meter_reading}, MBus={value}, skipping")
                results['skipped_existing'] += 1
                continue

            # Validate date range
            if reading_date < meter.build_in_date:
                results['errors'].append(
                    f"Reading date {reading_date} is before build-in date for meter {meter.id} (mbus_id={mbus_id})"
                )
                continue

            if meter.out_of_order_date and reading_date > meter.out_of_order_date:
                results['errors'].append(
                    f"Reading date {reading_date} is after out-of-order date for meter {meter.id} (mbus_id={mbus_id})"
                )
                continue

            # Validate reading value is monotonically increasing
            reading_value = decimal.Decimal(str(value))

            # Get previous reading (before this date)
            previous_reading = MeterReading.objects.filter(
                meter=meter,
                date__lt=reading_date
            ).order_by('-date').first()

            if previous_reading and reading_value < previous_reading.meter_reading:
                logger.warning(
                    f"Reading {reading_value} for meter {meter.id} (mbus_id={mbus_id}) on {reading_date} "
                    f"is less than previous reading {previous_reading.meter_reading} on {previous_reading.date}"
                )
                results['skipped_invalid_value'] += 1
                continue

            # Get next reading (after this date)
            next_reading = MeterReading.objects.filter(
                meter=meter,
                date__gt=reading_date
            ).order_by('date').first()

            if next_reading and reading_value > next_reading.meter_reading:
                logger.warning(
                    f"Reading {reading_value} for meter {meter.id} (mbus_id={mbus_id}) on {reading_date} "
                    f"is greater than next reading {next_reading.meter_reading} on {next_reading.date}"
                )
                results['skipped_invalid_value'] += 1
                continue

            # Create the reading
            MeterReading.objects.create(
                meter=meter,
                date=reading_date,
                time=reading_time,
                meter_reading=reading_value,
                auto_reading=True
            )

            logger.info(
                f"Imported M-Bus reading for meter {meter.id} (mbus_id={mbus_id}): {value} on {reading_date}")
            results['imported'] += 1

        except Exception as e:
            logger.exception(f"Error processing reading: {reading}")
            results['errors'].append(
                f"Error processing mbus_id {reading.get('mbus_id', 'unknown')}: {str(e)}")

    return JsonResponse({
        'success': True,
        'results': results
    })
