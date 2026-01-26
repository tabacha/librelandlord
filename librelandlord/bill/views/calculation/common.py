"""
Gemeinsame Hilfsfunktionen für Abrechnungs-Views.
"""
from django.shortcuts import render
from django.conf import settings
import traceback
import logging

logger = logging.getLogger(__name__)


def render_calculation_error(request, billing_year: int, error: Exception, status: int = 500):
    """
    Rendert eine Fehlerseite für Abrechnungsfehler.

    Args:
        request: Django Request-Objekt
        billing_year: Das Abrechnungsjahr
        error: Die aufgetretene Exception
        status: HTTP-Statuscode (default: 500)

    Returns:
        HttpResponse mit gerenderter Fehlerseite
    """
    logger.exception(
        "Error calculating for year %s: %s",
        billing_year,
        str(error)
    )

    traceback_str = traceback.format_exc()

    error_context = {
        'error_message': str(error),
        'error_type': type(error).__name__,
        'billing_year': billing_year,
        'traceback': traceback_str,
        'debug': settings.DEBUG
    }
    return render(request, 'yearly_calculation_error.html', error_context, status=status)


def render_not_found_error(request, billing_year: int, message: str = None):
    """
    Rendert eine Fehlerseite für nicht gefundene Abrechnungsperioden.

    Args:
        request: Django Request-Objekt
        billing_year: Das Abrechnungsjahr
        message: Optionale Fehlermeldung

    Returns:
        HttpResponse mit gerenderter Fehlerseite
    """
    if message is None:
        message = f'Keine Abrechnungsperioden für das Jahr {billing_year} gefunden.'

    error_context = {
        'error_message': message,
        'error_type': 'NotFound',
        'billing_year': billing_year,
        'debug': settings.DEBUG
    }
    return render(request, 'yearly_calculation_error.html', error_context, status=404)
