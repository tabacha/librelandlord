from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.forms.models import model_to_dict
from django.db.models.query import QuerySet
from datetime import datetime, date
import decimal
import json

from ..models import Meter, MeterReading, MeterPlace

import logging

logger = logging.getLogger(__name__)


def interpolate_reading(before, after, target_date):
    """
    Berechnet einen interpolierten Messwert für ein Ziel-Datum.

    Args:
        before: Das erste MeterReading-Objekt vor dem Ziel-Datum.
        after: Das erste MeterReading-Objekt nach dem Ziel-Datum.
        target_date: Das Datum, für das interpoliert werden soll.

    Returns:
        Der interpolierte Messwert.
    """
    days_between = (after.date - before.date).days
    daily_change = (after.meter_reading - before.meter_reading) / days_between
    interpolated_value = round(before.meter_reading +
                               daily_change * (target_date - before.date).days)
    return interpolated_value


def calculate_meter_consumption(meter_id: int, start_date: date, end_date: date):
    """
    Berechnet den Verbrauch eines Zählers in einem Zeitraum.

    Args:
        meter_id: ID des Zählers
        start_date: Startdatum des Zeitraums
        end_date: Enddatum des Zeitraums

    Returns:
        dict mit 'consumption' und 'readings' Liste
    """
    readings = MeterReading.objects.filter(
        meter_id=meter_id,
        date__range=(start_date, end_date)
    ).order_by('date')

    # Falls Messungen außerhalb des Zeitraums fehlen, die naheliegenden Messwerte abrufen
    before_start = None
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
    """
    Berechnet den Verbrauch aller Zähler an einem Standort in einem Zeitraum.

    Args:
        meter_place_id: ID des Zählerstandorts
        start_date: Startdatum des Zeitraums
        end_date: Enddatum des Zeitraums

    Returns:
        dict mit 'consumption', 'meters' Liste und 'place' Info
    """
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
    """JSON-Serialisierungs-Hilfsfunktion für spezielle Typen."""
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
    """API-Endpunkt für die Verbrauchsberechnung eines Zählerstandorts."""
    consumption = calculate_meter_place_consumption(
        meter_place, start_date, end_date)

    response = HttpResponse(json.dumps(
        consumption, default=serialize_helper), content_type='text/json')

    return response


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
