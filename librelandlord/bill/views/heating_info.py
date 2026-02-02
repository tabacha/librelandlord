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

from ..models import Renter, HeatingInfo, HeatingInfoTemplate, Landlord

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
    if renter.move_out_date is not None and renter.move_out_date < last_day_of_last_month.date():
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
                    'actual_m3': entry.hot_water_m3,
                    'year_before': water_year_before,
                    'compare': entry.compare_hot_water_energy_kwh,
                    'actual_percent': 100 * (entry.hot_water_energy_kwh/max_water),
                    'compare_percent': 100 * (entry.compare_hot_water_energy_kwh/max_water),
                })

    landlord = Landlord.get_instance()
    context = {
        'renter': renter,
        'apartment': renter.apartment,
        'heating': heating,
        'hot_water': hot_water,
        'landlord': landlord,
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

    Berechnet für jedes HeatingInfoTemplate einzeln die noch ausstehenden Monate
    und erstellt entsprechende HeatingInfo-Einträge. Templates werden unabhängig
    voneinander verarbeitet, sodass ein blockiertes Template andere nicht aufhält.

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

    logger.info(f"run_heating_info_task gestartet: today={today}, target_year={target_year}, target_month={target_month}")

    data = {'processed': [], 'pending': []}

    # Alle Templates holen die noch Monate zu verarbeiten haben
    all_templates = HeatingInfoTemplate.objects.filter(
        Q(next_year__lt=target_year) |
        (Q(next_year=target_year) & Q(next_month__lte=target_month))
    ).order_by('apartment__name')

    logger.info(f"Gefundene Templates mit ausstehenden Monaten: {all_templates.count()}")

    # Jedes Template einzeln verarbeiten
    for template in all_templates:
        logger.info(f"=== Verarbeite Template: {template.apartment} (aktuell bei {template.next_year}-{template.next_month:02d}) ===")

        # Alle ausstehenden Monate für dieses Template verarbeiten
        while (template.next_year < target_year or
               (template.next_year == target_year and template.next_month <= target_month)):

            calc_year = template.next_year
            calc_month = template.next_month
            next_year = calc_year
            next_month = calc_month + 1
            if next_month > 12:
                next_month = 1
                next_year = next_year + 1
            start_date = date(calc_year, calc_month, 1)
            end_date = date(next_year, next_month, 1)

            logger.info(f"  Berechne Monat {calc_year}-{calc_month:02d} für {template.apartment}")

            heat_val = None
            heat_error = None
            water_val = None
            water_error = None

            # Heizung berechnen
            if template.calc_heating is not None:
                logger.info(f"    Berechne Heizung mit ConsumptionCalc '{template.calc_heating.name}' (ID: {template.calc_heating.id}) für Zeitraum {start_date} bis {end_date}")
                try:
                    result = template.calc_heating.calculate(start_date, end_date)
                    heat_val = result.value if result.success else None
                    logger.info(f"    Heizung Ergebnis: success={result.success}, value={heat_val}")
                    if heat_val is None:
                        heat_error = getattr(result, 'error', 'no value')
                        logger.warning(f"    Heizung ohne Wert: {heat_error}")
                except Exception as e:
                    heat_error = str(e)
                    logger.error(f"    Heizung Fehler: {heat_error}")
            else:
                logger.info(f"    Keine calc_heating konfiguriert")

            # Warmwasser berechnen
            if template.calc_hot_water is not None:
                logger.info(f"    Berechne Warmwasser mit ConsumptionCalc '{template.calc_hot_water.name}' (ID: {template.calc_hot_water.id}) für Zeitraum {start_date} bis {end_date}")
                try:
                    result = template.calc_hot_water.calculate(start_date, end_date)
                    water_val = result.value if result.success else None
                    logger.info(f"    Warmwasser Ergebnis: success={result.success}, value={water_val}")
                    if water_val is None:
                        water_error = getattr(result, 'error', 'no value')
                        logger.warning(f"    Warmwasser ohne Wert: {water_error}")
                except Exception as e:
                    water_error = str(e)
                    logger.error(f"    Warmwasser Fehler: {water_error}")
            else:
                logger.info(f"    Keine calc_hot_water konfiguriert")

            # Prüfen ob Werte berechnet werden konnten
            has_heating = heat_val is not None or template.calc_heating is None
            has_water = water_val is not None or template.calc_hot_water is None
            is_complete = has_heating and has_water
            has_any_value = heat_val is not None or water_val is not None

            logger.info(f"    has_heating={has_heating}, has_water={has_water}, complete={is_complete}, has_any_value={has_any_value}")

            # Wenn gar kein Wert berechnet werden konnte, zu pending und zum nächsten Template
            if not has_any_value:
                pending_info = {
                    'apartment': str(template.apartment),
                    'month': f"{calc_year}-{calc_month:02d}"
                }
                if heat_error:
                    pending_info['heating_error'] = heat_error
                if water_error:
                    pending_info['water_error'] = water_error
                data['pending'].append(pending_info)
                logger.warning(f"    Keine Werte berechenbar - Template übersprungen, weiter zum nächsten Template")
                break  # Zum nächsten Template

            # HeatingInfo erstellen/aktualisieren (ohne Vergleichswerte - die fehlen bei Einzel-Verarbeitung)
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

            # Heizung aktualisieren
            if heat_val is not None:
                hi.heating_energy_kwh = heat_val
                processed_info['updated'].append('heating')
            elif heat_error:
                processed_info['heating_pending'] = heat_error

            # Warmwasser aktualisieren
            if water_val is not None:
                hi.hot_water_m3 = water_val
                kwh_factor = decimal.Decimal(template.kwh_per_m3_hot_water)
                hi.hot_water_energy_kwh = water_val * kwh_factor
                processed_info['updated'].append('hot_water')
            elif water_error:
                processed_info['water_pending'] = water_error

            hi.save()
            data['processed'].append(processed_info)
            logger.info(f"    HeatingInfo gespeichert für {template.apartment}, {calc_year}-{calc_month:02d}")

            # Template weitersetzen wenn komplett, sonst bei diesem Template stoppen
            if is_complete:
                template.next_year = next_year
                template.next_month = next_month
                template.save()
                logger.info(f"    Template weitergesetzt auf {next_year}-{next_month:02d}")
            else:
                pending_info = {
                    'apartment': str(template.apartment),
                    'month': f"{calc_year}-{calc_month:02d}",
                    'partial': True
                }
                if heat_error:
                    pending_info['heating_error'] = heat_error
                if water_error:
                    pending_info['water_error'] = water_error
                data['pending'].append(pending_info)
                logger.warning(f"    Template NICHT weitergesetzt (incomplete) - weiter zum nächsten Template")
                break  # Zum nächsten Template

    # Zweiter Durchlauf: Vergleichswerte berechnen für alle Monate die jetzt HeatingInfo haben
    logger.info("=== Berechne Vergleichswerte ===")
    _update_compare_values(target_year, target_month)

    logger.info(f"run_heating_info_task beendet: {len(data['processed'])} verarbeitet, {len(data['pending'])} pending")
    return data


def _update_compare_values(target_year: int, target_month: int):
    """
    Aktualisiert die Vergleichswerte für alle HeatingInfo-Einträge.
    Wird nach der Hauptverarbeitung aufgerufen, um Vergleichswerte basierend
    auf allen verfügbaren Daten zu berechnen.
    """
    # Alle Templates für Vergleichsgruppen-Mapping holen
    templates = HeatingInfoTemplate.objects.all()

    # Für jeden Monat im relevanten Zeitraum die Vergleichswerte berechnen
    # Wir gehen 24 Monate zurück
    current_year = target_year
    current_month = target_month

    for _ in range(24):
        # Vergleichsgruppen für diesen Monat sammeln
        compare_group_heating = {}
        compare_group_water = {}

        for template in templates:
            try:
                hi = HeatingInfo.objects.get(
                    apartment=template.apartment,
                    year=current_year,
                    month=current_month
                )

                if hi.heating_energy_kwh is not None:
                    groupname = template.compare_heating_group
                    if groupname not in compare_group_heating:
                        compare_group_heating[groupname] = {'m2': 0, 'sum': 0}
                    compare_group_heating[groupname]['sum'] += hi.heating_energy_kwh
                    compare_group_heating[groupname]['m2'] += template.apartment.size_in_m2

                if hi.hot_water_m3 is not None:
                    groupname = template.compare_hot_water_group
                    if groupname not in compare_group_water:
                        compare_group_water[groupname] = {'sum': 0, 'num': 0}
                    compare_group_water[groupname]['sum'] += hi.hot_water_m3
                    compare_group_water[groupname]['num'] += 1

            except HeatingInfo.DoesNotExist:
                continue

        # Vergleichswerte aktualisieren
        for template in templates:
            try:
                hi = HeatingInfo.objects.get(
                    apartment=template.apartment,
                    year=current_year,
                    month=current_month
                )

                updated = False

                # Heizung Vergleichswert
                if hi.heating_energy_kwh is not None:
                    groupname = template.compare_heating_group
                    if compare_group_heating.get(groupname, {}).get('m2', 0) > 0:
                        new_compare = template.apartment.size_in_m2 * (
                            compare_group_heating[groupname]['sum'] / compare_group_heating[groupname]['m2']
                        )
                        if hi.compare_heating_energy_kwh != new_compare:
                            hi.compare_heating_energy_kwh = new_compare
                            updated = True

                # Warmwasser Vergleichswert
                if hi.hot_water_m3 is not None:
                    groupname = template.compare_hot_water_group
                    if compare_group_water.get(groupname, {}).get('num', 0) > 0:
                        kwh_factor = decimal.Decimal(template.kwh_per_m3_hot_water)
                        compare_water_m3 = compare_group_water[groupname]['sum'] / compare_group_water[groupname]['num']
                        new_compare = compare_water_m3 * kwh_factor
                        if hi.compare_hot_water_energy_kwh != new_compare:
                            hi.compare_hot_water_energy_kwh = new_compare
                            updated = True

                if updated:
                    hi.save()
                    logger.debug(f"  Vergleichswerte aktualisiert für {template.apartment}, {current_year}-{current_month:02d}")

            except HeatingInfo.DoesNotExist:
                continue

        # Einen Monat zurück
        current_month -= 1
        if current_month < 1:
            current_month = 12
            current_year -= 1


@login_required
def heating_info_task(request):
    """
    HTTP-Endpunkt für den Heizungsinfo-Task.
    """
    data = run_heating_info_task()
    return HttpResponse(json.dumps(data, indent=2), content_type='application/json')


def heating_info_pdf_by_token(request, token: str):
    """
    Generiert ein PDF der Heizungsinfo für einen Mieter basierend auf seinem Token.
    Kein Login erforderlich - Authentifizierung über Token.
    """
    try:
        renter = Renter.objects.get(token=token)
    except Renter.DoesNotExist:
        return HttpResponse("Ungültiger Token", status=404)

    template = loader.get_template('heating_info.html')
    context = get_heating_info_context(request=request, renter_id=renter.id)

    if context is None:
        return HttpResponse("Keine Heizungsinfo verfügbar", status=404)

    html = template.render(context, request)

    # Generiere das PDF mit WeasyPrint
    pdf = HTML(string=html).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = 'inline; filename="heating_info.pdf"'

    return response


def heating_info_unsubscribe(request, token: str):
    """
    Ermöglicht einem Mieter, die monatliche Heizungsinfo abzubestellen.
    Kein Login erforderlich - Authentifizierung über Token.
    """
    try:
        renter = Renter.objects.get(token=token)
    except Renter.DoesNotExist:
        return HttpResponse("Ungültiger Token", status=404)

    if request.method == 'POST':
        renter.wants_heating_info = False
        renter.save(update_fields=['wants_heating_info'])
        return render(request, 'heating_info_unsubscribe_success.html', {
            'renter': renter,
        })

    return render(request, 'heating_info_unsubscribe.html', {
        'renter': renter,
    })
