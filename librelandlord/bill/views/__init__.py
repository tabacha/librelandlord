"""
Views für die Bill-App.

Dieses Modul re-exportiert alle Views für Kompatibilität mit bestehenden Imports.
"""

# Auth Views
from .auth import custom_login, index

# Dashboard Views
from .dashboard import dashboard_stats_api

# Heating Info Views
from .heating_info import (
    heating_info,
    heating_info_pdf,
    heating_info_pdf_by_token,
    heating_info_task,
    heating_info_unsubscribe,
    run_heating_info_task,
)

# Meter Views
from .meter import (
    meter_place_consumption,
    meter_readings_input,
    meter_readings_save_single,
)

# Calculation Views
from .calculation import (
    yearly_calculation,
    tax_overview,
)

# API Views
from .api import (
    costcenter_distribution_type,
    mbus_readings_import,
    bill_paperless_id_update,
)

# Emergency Contacts Views
from .emergency_contacts import emergency_contacts

__all__ = [
    # Auth
    'custom_login',
    'index',
    # Dashboard
    'dashboard_stats_api',
    # Heating Info
    'heating_info',
    'heating_info_pdf',
    'heating_info_pdf_by_token',
    'heating_info_task',
    'heating_info_unsubscribe',
    'run_heating_info_task',
    # Meter
    'meter_place_consumption',
    'meter_readings_input',
    'meter_readings_save_single',
    # Calculation
    'yearly_calculation',
    'tax_overview',
    # API
    'costcenter_distribution_type',
    'mbus_readings_import',
    'bill_paperless_id_update',
    # Emergency Contacts
    'emergency_contacts',
]
