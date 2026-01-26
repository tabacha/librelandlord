import os
import json
import decimal
from functools import wraps

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from ..models import CostCenter, Meter, MeterReading, Bill

import logging

logger = logging.getLogger(__name__)


def check_mbus_api_key(view_func):
    """Decorator to check M-Bus API key from environment variable."""

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


@login_required
@require_http_methods(["GET"])
def costcenter_distribution_type(request, cost_center_id):
    """
    API-Endpunkt für den Admin: Gibt den distribution_type eines CostCenters zurück.
    Wird verwendet um das consumption_calc Feld dynamisch ein-/auszublenden.
    """
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


@login_required
@require_http_methods(["POST"])
def bill_paperless_id_update(request, bill_id: int):
    """
    API-Endpunkt zum Aktualisieren der Paperless-ID einer Rechnung.

    POST-Parameter:
    - paperless_id: Die neue Paperless-ID (integer oder leer zum Löschen)
    """
    # Prüfen ob Paperless konfiguriert ist
    if not settings.PAPERLESS_BASE_URL:
        return JsonResponse({
            'success': False,
            'error': 'Paperless ist nicht konfiguriert'
        }, status=400)

    try:
        bill = Bill.objects.get(pk=bill_id)
    except Bill.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Rechnung nicht gefunden'
        }, status=404)

    paperless_id_str = request.POST.get('paperless_id', '').strip()

    if paperless_id_str == '':
        bill.paperless_id = None
    else:
        try:
            bill.paperless_id = int(paperless_id_str)
        except ValueError:
            return JsonResponse({
                'success': False,
                'error': 'Ungültige Paperless-ID (muss eine Zahl sein)'
            }, status=400)

    bill.save()

    return JsonResponse({
        'success': True,
        'paperless_id': bill.paperless_id
    })
