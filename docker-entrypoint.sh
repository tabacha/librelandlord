#!/bin/bash

# MySQL Setup Script für LibreLandlord
# Führt Migrationen aus und erstellt initialen Superuser

set -e

echo "=== LibreLandlord MySQL Setup ==="

# Warte auf MariaDB-Verbindung
echo "Warte auf MariaDB-Verbindung..."
while ! python manage.py dbshell --command="SELECT 1;" 2>/dev/null; do
    echo "MariaDB noch nicht bereit, warte 5 Sekunden..."
    sleep 5
done

echo "✅ MariaDB-Verbindung erfolgreich!"

# Führe Migrationen aus
echo "Führe Datenbank-Migrationen aus..."
python manage.py migrate

# Erstelle Superuser falls nicht vorhanden (nur für Demo)
if [ "$USE_OIDC_ONLY" != "True" ]; then
    echo "Erstelle Demo-Superuser (admin/admin)..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin')
    print('Demo-Superuser erstellt: admin/admin')
else:
    print('Superuser bereits vorhanden')
"
else
    echo "OIDC-only Modus: Keine lokalen Benutzer erstellt"
fi

# Sammle statische Dateien
echo "Sammle statische Dateien..."
python manage.py collectstatic --noinput

echo "✅ MariaDB Setup abgeschlossen!"
echo "🚀 Starte LibreLandlord..."

# Starte die Anwendung
exec "$@"
