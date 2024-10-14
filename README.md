# Install Python Venv

```shell
./install-venv.sh
```

# Start Django

```shell
cd librelandlord
./manage.sh runserver
```

http://127.0.0.1:8000/admin/

User: admin
Password: admin



# Modell

Eine Rechung kann für mehrere Abrechungen (z.B. Zeiträume) gelten, deshalb gibt es Buchungen.
Eine Buchung gilt nur für einen Abrechung wird abgrechnet nach einem Vereilerschlüssel, zB. qm oder Anzahl Wohnungen oder Anteiliger Stromverbrauch

Es gibt noch Informative Hauptzähler zu Zwischenzähler. z.B. Gas zu Wäremmengenzähler.


Eine Abrechung hat einen Start und einen Endpunkt und ein Thema: Mietabrechung, Heizungsabrechung.




Stromabrechung -> Wird aufgeteilt auf Hausstrom 7, Heizung7, WaMa7,...

Heizungabrechung hat wieder Stromrechung als Position.

