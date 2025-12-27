from time import sleep
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.template import loader
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings

from .models import Renter, HeatingInfo, MeterReading, Meter, HeatingInfoTemplate, ConsumptionCalc, CostCenterContribution, AccountPeriod, MeterPlace
from weasyprint import HTML
from django.conf import settings
from django.db.models import Q
from datetime import datetime, timedelta, date
import decimal
import json
from django.forms.models import model_to_dict
from django.db.models.query import QuerySet

import operator

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
    renter_list = Renter.objects.order_by('last_name')
    costcentercontributions = CostCenterContribution.objects.all()
    template = loader.get_template('index.html')
    context = {
        'renter_list': renter_list,
        'costcentercontributions': costcentercontributions
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


def heating_info(request, id: int):
    template = loader.get_template('heating_info.html')
    context = get_heating_info_context(request=request, renter_id=id)
    html = template.render(context, request)
    return HttpResponse(html)


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


def process_calc_argument(argument_value, argument, label, calculation, start_date, end_date):
    if argument_value:
        calculation[label] = {'type': 'fixed', 'val': argument_value}
        return argument_value
    elif argument:
        calc_result = calculate_meter_place_consumption(
            argument, start_date, end_date)
        calculation[label] = {'type': 'consumption', 'calc': calc_result}
        return calc_result['consumption']
#                           consumption
    return None


def calc_consumption_calc(calc: ConsumptionCalc,
                          start_date: date, end_date: date):
    operations = {
        '+': operator.add,
        '-': operator.sub,
        '*': operator.mul,
        '/': operator.truediv
    }
    calculation = {}
    arg1 = process_calc_argument(
        argument_value=calc.argument1_value,
        argument=calc.argument1,
        label='arg1',
        calculation=calculation,
        start_date=start_date,
        end_date=end_date)
    arg2 = process_calc_argument(
        argument_value=calc.argument2_value,
        argument=calc.argument2,
        label='arg2',
        calculation=calculation,
        start_date=start_date,
        end_date=end_date)
    arg3 = process_calc_argument(
        argument_value=calc.argument3_value,
        argument=calc.argument3,
        label='arg3',
        calculation=calculation,
        start_date=start_date,
        end_date=end_date)
    # Berechne den finalen Wert basierend auf den Operatoren
    try:
        if arg1 is not None and arg2 is not None:
            result = operations[calc.operator1](arg1, arg2)
            result_calc = f' {arg1} {calc.operator1} {arg2}'
            if arg3 is not None:
                result = operations[calc.operator2](result, arg3)
                result_calc = f'{result_calc} {calc.operator2} {arg3}'
        else:
            result = arg1
            result_calc = ''
    except ZeroDivisionError:
        result = None  # Division durch Null vermeiden
    return {'result': result,
            'result_calc': result_calc,
            'arg_calc': calculation
            }


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
                        heat_val = calc_consumption_calc(
                            template.calc_heating, start_date, end_date)['result']
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
                        water_val = calc_consumption_calc(
                            template.calc_hot_water, start_date, end_date)['result']
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


@require_http_methods(["GET"])
def account_period_calculation(request, account_period_id):
    """
    View der die vollständige Berechnung einer AccountPeriod über ein Template ausgibt.

    Liefert sowohl Rechnungsdaten als auch Verbrauchsberechnungen pro CostCenter
    über ein Jinja Template.

    URL: /account-period/<id>/calculation/
    Method: GET

    Returns:
        Gerenderte HTML-Seite mit der AccountPeriodCalculation
    """
    try:
        # AccountPeriod holen
        account_period = get_object_or_404(AccountPeriod, id=account_period_id)

        # Berechnung durchführen
        calculation = account_period.calculate_bills_by_cost_center()

        # Template-Kontext erstellen
        context = {
            'calculation': calculation,
            'account_period': calculation.account_period,
            'summary': {
                'grand_total': calculation.grand_total,
                'total_bill_count': calculation.total_bill_count,
                'cost_center_count': calculation.cost_center_count
            },
            'cost_center_summaries': calculation.cost_center_summaries,
        }

        # Template rendern
        return render(request, 'account_period_calculation.html', context)

    except Exception as e:
        # Fehler-Template rendern
        error_context = {
            'error_message': str(e),
            'error_type': type(e).__name__,
            'account_period_id': account_period_id
        }
        return render(request, 'account_period_calculation_error.html', error_context, status=500)


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
