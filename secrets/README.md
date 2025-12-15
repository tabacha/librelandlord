# MariaDB Docker Secrets Setup

Diese Datei erklärt, wie die MariaDB-Passwörter sicher über Docker Secrets verwaltet werden.

## Secrets erstellen

```bash
# 1. MariaDB Root-Passwort setzen
echo "your-super-secure-root-password-here" > secrets/mariadb_root_password.txt

# 2. LibreLandlord DB-Benutzer-Passwort setzen
echo "your-secure-librelandlord-db-password" > secrets/mariadb_password.txt

# 3. Dateiberechtigungen sichern
chmod 600 secrets/*.txt
```

## Sicherheit

- Passwort-Dateien werden **NICHT** in Git committed (siehe .gitignore)
- Nur der Docker-Container kann die Secrets lesen
- Passwörter werden in `/run/secrets/` im Container gemountet
- Keine Passwörter in Umgebungsvariablen oder Logs sichtbar

## Deployment

```bash
# .env konfigurieren (ohne Passwörter)
cp .env.production .env

# Secrets erstellen (siehe oben)
# ...

# Container starten
docker-compose -f docker-compose.ghcr.yml up -d
```

## Produktionsumgebung

Für Kubernetes oder Docker Swarm verwenden Sie die nativen Secret-Mechanismen:

### Kubernetes

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: mariadb-secrets
data:
  root-password: <base64-encoded-password>
  user-password: <base64-encoded-password>
```

### Docker Swarm

```bash
echo "password" | docker secret create mariadb_root_password -
echo "password" | docker secret create mariadb_password -
```
