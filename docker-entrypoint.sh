#!/bin/bash

# MySQL Setup Script für LibreLandlord
# Führt Migrationen aus und erstellt initialen Superuser

set -e

echo "=== LibreLandlord MySQL Setup ==="

# Warte auf MariaDB-Verbindung
echo "Warte auf MariaDB-Verbindung..."
echo "Database Host: $DATABASE_HOST"
echo "Database Port: $DATABASE_PORT"
echo "Database User: $DATABASE_USER"

# Teste MariaDB-Verbindung mit mysql-client
DB_PASSWORD=""
if [ -f "$DATABASE_PASSWORD_FILE" ]; then
    DB_PASSWORD=$(cat "$DATABASE_PASSWORD_FILE")
    echo "Passwort aus Secret-Datei gelesen"
else
    DB_PASSWORD="$DATABASE_PASSWORD"
    echo "Passwort aus Umgebungsvariable"
fi

counter=0
max_attempts=12  # 60 Sekunden total

while [ $counter -lt $max_attempts ]; do
    if mysql -h"$DATABASE_HOST" -P"$DATABASE_PORT" -u"$DATABASE_USER" -p"$DB_PASSWORD" -e "SELECT 1;" 2>/dev/null; then
        echo "✅ MariaDB-Verbindung erfolgreich!"
        break
    fi

    counter=$((counter + 1))
    echo "MariaDB noch nicht bereit, Versuch $counter/$max_attempts, warte 5 Sekunden..."
    sleep 5
done

if [ $counter -eq $max_attempts ]; then
    echo "❌ MariaDB-Verbindung fehlgeschlagen nach $max_attempts Versuchen"
    exit 1
fi

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

echo "✅ MariaDB Setup abgeschlossen!"
echo "🚀 Starte LibreLandlord..."

# Starte die Anwendung
exec "$@"
