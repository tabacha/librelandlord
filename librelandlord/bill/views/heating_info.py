from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db.models import Q
from datetime import datetime, timedelta, date
import decimal
import json

from weasyprint import HTML

from ..models import Renter, HeatingInfo, HeatingInfoTemplate

import logging

logger = logging.getLogger(__name__)


def to_datetime(d):
    """Konvertiert ein date-Objekt zu einem datetime-Objekt."""
    return datetime(year=d.year, month=d.month, day=d.day)


def calculate_max(value: decimal.Decimal, current_max: decimal.Decimal) -> decimal.Decimal:
    """Berechnet das Maximum mit einem Faktor von 1.4."""
    max_factor = decimal.Decimal(1.4)
    if value:
        return max(current_max, value * max_factor)
    else:
        return current_max


def get_heating_info_context(request, renter_id: int):
    """
    Erstellt den Kontext für die Heizungsinfo-Ansicht eines Mieters.

    Returns:
        dict: Kontext mit Heizungs- und Warmwasserdaten oder None falls nicht benötigt.
    """
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
            water_year_before = None
            date = datetime(year=entry.year, month=entry.month, day=1)
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
                    'actual_percent': 100 * (entry.hot_water_energy_kwh/max_water),
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
    """Zeigt die Heizungsinfo-Seite für einen Mieter."""
    template = loader.get_template('heating_info.html')
    context = get_heating_info_context(request=request, renter_id=id)
    html = template.render(context, request)
    return HttpResponse(html)


@login_required
def heating_info_pdf(request, id: int):
    """Generiert ein PDF der Heizungsinfo für einen Mieter."""
    template = loader.get_template('heating_info.html')
    context = get_heating_info_context(request=request, renter_id=id)
    html = template.render(context, request)

    # Generiere das PDF mit WeasyPrint
    pdf = HTML(string=html).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="heating_info.pdf"'

    return response


def run_heating_info_task():
    """
    Kernlogik zur Berechnung der monatlichen Heizungsinfos.

    Berechnet für alle HeatingInfoTemplates die noch ausstehenden Monate
    und erstellt entsprechende HeatingInfo-Einträge. Läuft so lange,
    bis alle ausstehenden Monate abgearbeitet sind.

    Heizung und Warmwasser werden unabhängig voneinander berechnet.
    Fehlende Werte werden beim nächsten Aufruf nachgeholt.

    Returns:
        dict: Ergebnis mit 'processed' und 'pending' Listen
    """
    today = date.today()
    target_year = today.year
    target_month = today.month
    if target_month == 1:
        target_year = target_year - 1
        target_month = 12
    else:
        target_month = target_month - 1

    data = {'processed': [], 'pending': []}
    processed_months = set()  # Verhindert Endlosschleife

    while True:
        templates = HeatingInfoTemplate.objects.filter(
            Q(next_year__lt=target_year) |
            (Q(next_year=target_year) & Q(next_month__lte=target_month))
        ).order_by('next_year', 'next_month')

        if not templates:
            break

        calc_year = templates[0].next_year
        calc_month = templates[0].next_month

        # Endlosschleife verhindern: Monat nur einmal pro Aufruf verarbeiten
        month_key = (calc_year, calc_month)
        if month_key in processed_months:
            break
        processed_months.add(month_key)
        next_year = calc_year
        next_month = calc_month + 1
        if next_month > 12:
            next_month = 1
            next_year = next_year + 1
        start_date = date(calc_year, calc_month, 1)
        end_date = date(next_year, next_month, 1)

        # Erste Runde: Werte berechnen und sammeln
        compare_group_heating = {}
        compare_group_water = {}
        template_results = []
        any_progress = False

        for template in templates:
            if template.next_year != calc_year or template.next_month != calc_month:
                continue

            heat_val = None
            heat_error = None
            water_val = None
            water_error = None

            # Heizung berechnen
            if template.calc_heating is not None:
                try:
                    result = template.calc_heating.calculate(start_date, end_date)
                    heat_val = result.value if result.success else None
                    if heat_val is None:
                        heat_error = getattr(result, 'error', 'no value')
                except Exception as e:
                    heat_error = str(e)

            # Warmwasser berechnen
            if template.calc_hot_water is not None:
                try:
                    result = template.calc_hot_water.calculate(start_date, end_date)
                    water_val = result.value if result.success else None
                    if water_val is None:
                        water_error = getattr(result, 'error', 'no value')
                except Exception as e:
                    water_error = str(e)

            # Für Vergleichsgruppen sammeln (nur erfolgreiche Werte)
            if heat_val is not None:
                groupname = template.compare_heating_group
                if groupname not in compare_group_heating:
                    compare_group_heating[groupname] = {'m2': 0, 'sum': 0}
                compare_group_heating[groupname]['sum'] += heat_val
                compare_group_heating[groupname]['m2'] += template.apartment.size_in_m2

            if water_val is not None:
                groupname = template.compare_hot_water_group
                if groupname not in compare_group_water:
                    compare_group_water[groupname] = {'sum': 0, 'num': 0}
                compare_group_water[groupname]['sum'] += water_val
                compare_group_water[groupname]['num'] += 1

            # Prüfen ob mindestens ein Wert berechnet werden konnte
            has_heating = heat_val is not None or template.calc_heating is None
            has_water = water_val is not None or template.calc_hot_water is None

            template_results.append({
                'template': template,
                'heat_val': heat_val,
                'heat_error': heat_error,
                'water_val': water_val,
                'water_error': water_error,
                'complete': has_heating and has_water,
                'has_any_value': heat_val is not None or water_val is not None
            })

            if heat_val is not None or water_val is not None:
                any_progress = True

        # Wenn kein Fortschritt, abbrechen
        if not any_progress:
            for tr in template_results:
                pending_info = {
                    'apartment': str(tr['template'].apartment),
                    'month': f"{calc_year}-{calc_month:02d}"
                }
                if tr['heat_error']:
                    pending_info['heating_error'] = tr['heat_error']
                if tr['water_error']:
                    pending_info['water_error'] = tr['water_error']
                data['pending'].append(pending_info)
            break

        # Zweite Runde: HeatingInfo erstellen/aktualisieren
        for tr in template_results:
            template = tr['template']

            # Nur verarbeiten wenn mindestens ein Wert vorhanden
            if not tr['has_any_value']:
                pending_info = {
                    'apartment': str(template.apartment),
                    'month': f"{calc_year}-{calc_month:02d}"
                }
                if tr['heat_error']:
                    pending_info['heating_error'] = tr['heat_error']
                if tr['water_error']:
                    pending_info['water_error'] = tr['water_error']
                data['pending'].append(pending_info)
                continue

            # HeatingInfo holen oder erstellen
            hi, created = HeatingInfo.objects.get_or_create(
                apartment=template.apartment,
                year=calc_year,
                month=calc_month,
                defaults={
                    'heating_energy_kwh': None,
                    'compare_heating_energy_kwh': None,
                    'hot_water_energy_kwh': None,
                    'compare_hot_water_energy_kwh': None,
                    'hot_water_m3': None
                }
            )

            processed_info = {
                'apartment': str(template.apartment),
                'month': f"{calc_year}-{calc_month:02d}",
                'updated': []
            }

            # Heizung aktualisieren wenn Wert vorhanden
            if tr['heat_val'] is not None:
                hi.heating_energy_kwh = tr['heat_val']
                groupname = template.compare_heating_group
                if compare_group_heating.get(groupname, {}).get('m2', 0) > 0:
                    hi.compare_heating_energy_kwh = template.apartment.size_in_m2 * (
                        compare_group_heating[groupname]['sum'] / compare_group_heating[groupname]['m2']
                    )
                processed_info['updated'].append('heating')
            elif tr['heat_error']:
                processed_info['heating_pending'] = tr['heat_error']

            # Warmwasser aktualisieren wenn Wert vorhanden
            if tr['water_val'] is not None:
                hi.hot_water_m3 = tr['water_val']
                kwh_factor = decimal.Decimal(template.kwh_per_m3_hot_water)
                hi.hot_water_energy_kwh = tr['water_val'] * kwh_factor
                groupname = template.compare_hot_water_group
                if compare_group_water.get(groupname, {}).get('num', 0) > 0:
                    compare_water_m3 = compare_group_water[groupname]['sum'] / compare_group_water[groupname]['num']
                    hi.compare_hot_water_energy_kwh = compare_water_m3 * kwh_factor
                processed_info['updated'].append('hot_water')
            elif tr['water_error']:
                processed_info['water_pending'] = tr['water_error']

            hi.save()
            data['processed'].append(processed_info)

            # Template nur weitersetzen wenn komplett
            if tr['complete']:
                template.next_year = next_year
                template.next_month = next_month
                template.save()

    return data


@login_required
def heating_info_task(request):
    """
    HTTP-Endpunkt für den Heizungsinfo-Task.
    """
    data = run_heating_info_task()
    return HttpResponse(json.dumps(data, indent=2), content_type='application/json')
