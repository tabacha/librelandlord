from django.shortcuts import render
from django.http import HttpResponse
from django.template import loader
from .models import Renter, HeatingInfo, MeterReading, Meter, HeatingInfoTemplate
from weasyprint import HTML
from django.conf import settings
from django.db.models import Q
from datetime import datetime, timedelta, date
import decimal
import json
from django.forms.models import model_to_dict
from django.db.models.query import QuerySet


def index(request):
    renter_list = Renter.objects.order_by('last_name')
    template = loader.get_template('index.html')
    context = {
        'renter_list': renter_list
    }
    return HttpResponse(template.render(context, request))


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
        Q(year=start_date_year, month__gte=start_date_month) | Q(
            year__gt=start_date_year)  # Bedingung kombinieren
    ).order_by('year', 'month').reverse()  # Ergebnisse nach Jahr und Monat sortieren

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
                comp_percent = None
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


def heating_info(request):
    template = loader.get_template('heating_info.html')
    context = get_heating_info_context(request=request, renter_id=2)
    html = template.render(context, request)
    return HttpResponse(html)


def heating_info_pdf(request):
    template = loader.get_template('heating_info.html')
    context = get_heating_info_context(request=request, renter_id=2)
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
                "Nicht genug Messwerte vorhanden, um Startwert zu interpolieren")

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
        # sum = sum + mconsumption.consumption
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


def meter_place_consumption(request, meter_place: int):
    consumption = calculate_meter_place_consumption(
        meter_place, date(2024, 7, 1), date(2024, 9, 20))
    # consumption = calculate_meter_consumption(
    #    4, date(2024, 7, 1), date(2024, 9, 6))

    # huhu = {'x': 42}
    # Sende die PDF-Datei als HTTP-Antwort zurück
    response = HttpResponse(json.dumps(
        consumption, default=serialize_helper), content_type='text/json')
    # response['Content-Disposition'] = 'attachment; filename="heating_info.pdf"'

    return response


def heating_info_task(request):
    templates = HeatingInfoTemplate.objects.filter(Q(date__year__lt=2024) |
                                                    (Q(date__year=2024) & Q(
                                                        date__month__lt=10))
                                                   )
    data = {}
    response = HttpResponse(json.dumps(
        data), content_type='text/json')
    # response['Content-Disposition'] = 'attachment; filename="heating_info.pdf"'

    return response
