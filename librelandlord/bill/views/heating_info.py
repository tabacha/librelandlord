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


@login_required
def heating_info_task(request):
    """
    Hintergrund-Task zur Berechnung der monatlichen Heizungsinfos.

    Berechnet für alle HeatingInfoTemplates die noch ausstehenden Monate
    und erstellt entsprechende HeatingInfo-Einträge.
    """
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

    return response
