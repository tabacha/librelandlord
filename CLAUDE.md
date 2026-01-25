# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

LibreLandlord is a German-language property management system (Verwaltungssystem für Vermieter) built with Django 5.2. It handles rental billing, utility cost allocation, meter readings, and heating cost calculations with optional OIDC/Keycloak authentication.

## Development Commands

```bash
# Install virtual environment
./install-venv.sh

# Start development server (activates venv, runs migrations, starts server at http://127.0.0.1:8000)
./start-demo.sh

# Manual Django commands (from librelandlord/ subdirectory with venv activated)
cd librelandlord
source .venv/bin/activate
python manage.py runserver
python manage.py makemigrations
python manage.py migrate
python manage.py test

# Build FontAwesome static assets
npm run build
```

## Project Structure

```
librelandlord/              # Root directory
├── librelandlord/          # Django project directory
│   ├── .venv/              # Python Venv
│   ├── manage.py
│   ├── db.sqlite3          # Development database
│   ├── librelandlord/      # Django settings module
│   │   ├── settings.py
│   │   └── urls.py
│   └── bill/               # Main Django app
│       ├── models/         # Domain models (see below)
│       ├── views.py        # View functions
│       ├── admin.py        # Django admin customizations
│       ├── admin_csv_import.py
│       ├── services/       # Business logic
│       └── templates/      # HTML templates
└── requirements.txt        # Python dependencies
```

## Domain Model Architecture

The billing system centers on these key relationships:

- **Bill** (Rechnung): An invoice that can apply to multiple billing periods
- **AccountPeriod** (Abrechnungszeitraum): A billing period with start/end dates and topic (rent, heating, etc.)
- **CostCenter** (Kostenstelle): Defines how costs are distributed using distribution keys (e.g., square meters, apartment count, consumption)
- **CostCenterContribution**: Links cost centers to apartments with allocation amounts
- **Apartment** (Wohnung): Rental units with associated meters and renters
- **Renter** (Mieter): Tenants with rental periods
- **Meter/MeterPlace/MeterReading**: Utility meter hierarchy and readings
- **ConsumptionCalc**: Calculates consumption-based cost allocations
- **HeatingInfo**: Generates heating cost information documents

Distribution types (in CostCenter):

- TIME: Proportional to rental duration
- AREA: Proportional to apartment size (m²)
- DIRECT: Direct assignment to apartments
- Various consumption-based types for utilities

## Code Style

- Python: 4 spaces indent, max 120 chars line length
- HTML/Django templates: 4 spaces indent, no automatic line wrapping
- Language: German for domain terms and user-facing content, English for code structure
- All text uses LF line endings with final newline

## Environment Configuration

Key environment variables (see `.env.example` and `.env.production`):

- `DEBUG`: Enable debug mode (default: True)
- `USE_OIDC_ONLY`: Disable local authentication, require OIDC (default: False)
- `DATABASE_ENGINE`: `django.db.backends.sqlite3` or `django.db.backends.mysql`
- `KEYCLOAK_SERVER`, `KEYCLOAK_REALM`, `OIDC_CLIENT_*`: OIDC configuration
