# LibreLandlord

Verwaltungssystem für Vermieter mit OIDC-Integration für Keycloak/UCS.

## 🚀 Schnellstart

### Demo-System (Lokale Entwicklung)

```shell
# Venv installieren
./install-venv.sh

# Demo-System starten (lokale User + optionales OIDC)
./start-demo.sh
```

URLs:

- Login: http://127.0.0.1:8000/bill/login/
- Admin: http://127.0.0.1:8000/admin/ (User: admin, Password: admin)

### Production-System (Docker mit MariaDB)

```shell
# .env Datei erstellen
cp .env.production .env
# -> KEYCLOAK_SERVER, OIDC_CLIENT_SECRET, ALLOWED_HOSTS anpassen

# MariaDB Passwörter sicher konfigurieren
echo "your-root-password" > secrets/mariadb_root_password.txt
echo "your-db-password" > secrets/mariadb_password.txt
chmod 600 secrets/*.txt

# Container aus GitHub Registry starten (mit MariaDB)
docker-compose -f docker-compose.ghcr.yml up -d
```

Die MariaDB-Datenbank wird automatisch initialisiert mit:

- Datenbank-Migrationen
- Demo-Superuser (nur wenn `USE_OIDC_ONLY=False`)
- Statische Dateien

### Eigenen Container bauen

```shell
# Lokaler Build
docker build -f Dockerfile.production -t librelandlord .

# Mit Docker Compose
docker-compose -f docker-compose.production.yml up -d
```

## 📦 Container Images

Automatisch gebaute Images sind verfügbar über GitHub Container Registry:

- `ghcr.io/tabacha/librelandlord:latest` - Neuester main branch
- `ghcr.io/tabacha/librelandlord:v1.0.0` - Spezifische Version (Tags)

## 🔐 Sicherheit

- **Docker Secrets**: MariaDB-Passwörter werden sicher über Docker Secrets verwaltet
- **OIDC Integration**: Single Sign-On mit Keycloak/UCS für Produktionsumgebungen
- **Environment-basierte Konfiguration**: Getrennte Settings für Demo und Production

# Modell

Eine Rechung kann für mehrere Abrechungen (z.B. Zeiträume) gelten, deshalb gibt es Buchungen.
Eine Buchung gilt nur für einen Abrechung wird abgrechnet nach einem Vereilerschlüssel, zB. qm oder Anzahl Wohnungen oder Anteiliger Stromverbrauch

Es gibt noch Informative Hauptzähler zu Zwischenzähler. z.B. Gas zu Wäremmengenzähler.

Eine Abrechung hat einen Start und einen Endpunkt und ein Thema: Mietabrechung, Heizungsabrechung.

Stromabrechung -> Wird aufgeteilt auf Hausstrom 7, Heizung7, WaMa7,...

Heizungabrechung hat wieder Stromrechung als Position.
