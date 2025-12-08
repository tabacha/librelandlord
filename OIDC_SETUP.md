# OIDC Setup für LibreLandlord

## Übersicht

LibreLandlord unterstützt nun flexible Authentifizierung:

- **Demo/Entwicklung**: Lokale Django-User + optionales OIDC
- **Production**: Nur OIDC über Keycloak auf UCS

## Umgebungskonfiguration

### Demo-System (Standard)

```bash
export DEBUG=True
export USE_OIDC_ONLY=False
export ALLOWED_HOSTS=localhost,127.0.0.1
```

### Live-System (Docker)

```bash
export DEBUG=False
export USE_OIDC_ONLY=True
export ALLOWED_HOSTS=your-domain.com
export KEYCLOAK_SERVER=https://your-ucs-server.com
export KEYCLOAK_REALM=librelandlord
export OIDC_CLIENT_ID=librelandlord-django
export OIDC_CLIENT_SECRET=your-secret
```

## Keycloak Setup auf UCS

### 1. Keycloak Installation

```bash
# Auf UCS Server
univention-app install keycloak
```

### 2. Realm erstellen

1. Gehe zu: `https://your-ucs-server/keycloak/`
2. Administration Console → Add realm
3. Name: `librelandlord`

### 3. Client konfigurieren

1. Clients → Create
2. Client ID: `librelandlord-django`
3. Client Protocol: `openid-connect`
4. Access Type: `confidential`
5. Valid Redirect URIs: `https://your-librelandlord-domain/oidc/callback/`
6. Web Origins: `https://your-librelandlord-domain`

### 4. Client Secret kopieren

Credentials Tab → Secret → Kopieren für `OIDC_CLIENT_SECRET`

## Installation

### 1. Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

### 2. Umgebung konfigurieren

```bash
# Für Demo
cp .env.example .env
# Bearbeite .env mit deinen Werten

# Für Docker/Production
# Setze Umgebungsvariablen im Container
```

### 3. Migration (falls nötig)

```bash
python manage.py migrate
```

## Login-URLs

- **Custom Login**: `/bill/login/` - Zeigt verfügbare Optionen
- **OIDC Login**: `/oidc/authenticate/` - Direkt zu Keycloak
- **Admin Login**: `/admin/login/` - Django Admin (nur wenn USE_OIDC_ONLY=False)

## User-Mapping

Benutzer aus Keycloak werden automatisch erstellt mit:

- Username: Teil vor @ der E-Mail-Adresse
- E-Mail: Aus OIDC Claim
- Vorname/Nachname: Aus OIDC Profile

## Troubleshooting

### OIDC funktioniert nicht

1. Prüfe Keycloak Client-Konfiguration
2. Validiere OIDC_CLIENT_SECRET
3. Stelle sicher, dass Redirect URIs korrekt sind
4. Prüfe Keycloak Logs: `journalctl -u keycloak`

### Lokale User funktionieren nicht

1. Prüfe `USE_OIDC_ONLY=False`
2. Erstelle Superuser: `python manage.py createsuperuser`

### Docker Deployment

```dockerfile
# Im Dockerfile
ENV USE_OIDC_ONLY=True
ENV DEBUG=False
ENV KEYCLOAK_SERVER=https://your-ucs-server.com
ENV KEYCLOAK_REALM=librelandlord
# Secrets über Docker Secrets oder Kubernetes ConfigMaps
```
