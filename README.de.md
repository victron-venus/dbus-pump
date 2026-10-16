# dbus-pump

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Nederlands](README.nl.md)

**Versionshinweis:** Einheitenvertrag, diagnostischer Zweitsensor, Lokalisierung
und strengere Befehlsprüfung sind **noch nicht veröffentlichte Änderungen**.
Diese Quellrevision oder ein späteres Release mit diesen Änderungen verwenden;
ältere Versionen können abweichen. Siehe [CHANGELOG.md](CHANGELOG.md).

Eine Brücke zwischen Home Assistant und **Victron Venus OS** für Wassertank,
Pumpe und Ventil. Sie läuft auf dem Cerbo GX, liest HA-Entitäten und stellt
native D-Bus-Dienste für GX-Anzeigen und Cerbo-MQTT-Verbraucher bereit.
Die Ventilautomatik ist optional; die Pumpe wird manuell gesteuert.

![HA-Messwerte werden auf dem Cerbo umgerechnet und über D-Bus und MQTT veröffentlicht; optionale Befehle gehen an HA zurück.](docs/assets/architecture.svg)

## Installation

Erforderlich sind System-Python **3.12.x**, `requests`, D-Bus und GI/GLib passend
zur Venus-OS-Firmware. System-Python nicht ersetzen. Die Entwicklungsumgebung
verwendet Python 3.12.13.

1. Das Paket unter `/data/dbus-pump` ablegen.
2. `local_config.example.py` nach `local_config.py` kopieren und HA-URL, Token,
   Entitäten, Maßeinheit und Tankgeometrie eintragen. Den Token geheim halten.
3. `ENABLE_CONTROL = False` beibehalten, bis Messwerte und Zuständigkeit geprüft sind.
4. Abhängigkeiten prüfen und installieren:

```sh
python3 --version
python3 -c "import requests, dbus; from gi.repository import GLib"
/data/dbus-pump/setup install
svstat /service/dbus-pump-ha /service/dbus-pump-ha/log
readlink /service/dbus-pump-ha
tail -n 40 /var/log/dbus-pump-ha/current
```

Der Link `/service/dbus-pump-ha` muss auf
`/data/dbus-pump/service/dbus-pump` zeigen. `/service/dbus-pump` gehört zum
separaten Firmware-Dienst; diesen und seine `down`-Datei nicht entfernen.

Mit eingerichtetem SSH ist die Installation vom Rechner über `./deploy.sh Cerbo`
möglich. Dabei **ersetzt eine lokale `local_config.py` die Gerätekonfiguration**.
Normale Paketupdates erhalten die Gerätekonfiguration. Danach frische D-Bus-Werte
mit HA vergleichen; ein laufender Prozess allein belegt keine korrekte Messung.
[Installation und Wiederherstellung — EN](docs/operator/installation.md).

## Konfiguration und Maßeinheiten

Beispiel für die konfigurierte Anlage; Entitäten und Tankmaße vor Übernahme prüfen:

```python
HA_URL = "http://homeassistant.local:8123"
HA_TOKEN = "replace_with_private_long_lived_token"
HA_WATER_LEVEL_ENTITY = "sensor.water_level_2_water_level"
HA_WATER_LEVEL_UNIT = "cm"
HA_PUMP_SWITCH_ENTITY = "switch.pump_power_enable"
HA_VALVE_SWITCH_ENTITY = "switch.shutoff_valve"
TANK_CAPACITY_LITERS = 387.0
TANK_WATER_CM_ENTITY = "sensor.water_cm"  # nur Diagnose
TANK_OFFSET_CM = 18.0
TANK_RADIUS_CM = 35.56
LANGUAGE = "de"
ENABLE_CONTROL = False
```

**93 cm sind nicht 93%.** `HA_WATER_LEVEL_UNIT="cm"` bezeichnet Wasserhöhe;
`"%"` bezeichnet einen bereits normierten Prozentwert und bleibt der Standard.
Eine von HA gemeldete, nicht leere Einheit muss zur Konfiguration passen.
Im cm-Modus müssen Kapazität und Radius endlich und positiv sowie der Offset
endlich sein; ungültige Geometrie verhindert den Start.

Für einen senkrechten Zylinder gilt in Litern:
`max(0, cm − Offset) × π × Radius² / 1000`, begrenzt auf die Tankkapazität.
Mit obigen Werten ergeben 93 cm etwa **297,94 L und 76,99%**.
D-Bus `/Level` verwendet immer Prozent, `/Capacity` und `/Remaining` verwenden
**m³**: `0.298 m³` entspricht nach Rundung etwa 298 L.

Im Prozentmodus ergibt sich das Restvolumen aus Kapazität und demselben
Prozentwert. `TANK_WATER_CM_ENTITY` dient nur noch der Diagnose und überschreibt
das Volumen nicht mit einem zweiten Sensor. Dies ändert das frühere Verhalten.
Die Formel gilt nicht für liegende Zylinder oder unregelmäßige Tanks. Ein Sensor
für Abstand zur Wasseroberfläche muss zuerst in Wasserhöhe umgerechnet werden.

![Berechnete Kennlinie für 387 L, 18 cm Leerstandsoffset und 35,56 cm Radius: 93 cm entsprechen etwa 77 Prozent.](docs/assets/calibration.svg)

[Vollständige Konfiguration — EN](docs/operator/configuration.md) ·
[Kalibrierung und Grenzen — EN](docs/operator/calibration.md)

## Messablauf und aufgezeichnetes Ergebnis

Die Brücke liest den primären HA-Wert samt Einheit, prüft die Daten, rechnet die
nutzbare Wasserhöhe in Volumen und Prozent um und veröffentlicht beide aus
derselben Messung. Ein ungültiger Messwert verlängert die Gültigkeitsfrist nicht;
nach deren Ablauf wird die letzte gültige Messung als nicht verfügbar behandelt.
Das Diagramm zeigt den Ablauf; die berechnete Kurve ist kein Sensorverlauf.

![Messablauf: HA-Wert und Einheit werden geprüft und anhand der Zylindergeometrie in konsistente D-Bus-Prozent- und Volumenwerte umgerechnet.](docs/assets/measurement-process.svg)

Eine reine Leseprüfung am Cerbo vom **16. Oktober 2026, 03:13:49 UTC** ergab
**49 cm → berechnet 31,8217534% → 31,8% auf D-Bus**, dazu
`/Remaining=0.123 m³` (**123 L**). Gemeldet wurden Verbindung `1`, Pumpe `1`,
Ventil `0` und ein Heartbeat-Alter von `0,98 s`. Installiert war die
Entwicklungsversion `0.1.7+units.2c5045f` mit `ENABLE_CONTROL=False`
und `LANGUAGE="en"`.

![Aufgezeichnete Cerbo-Prüfung: 49 cm Eingang, 31,8 Prozent, 123 Liter, verbunden, Pumpenzustand 1 und Ventilzustand 0; datierte Momentaufnahme statt Live-Telemetrie.](docs/assets/measured-result.svg)

Dies belegt einen erfolgreichen Telemetrievergleich, keine physische Abnahme
oder ununterbrochene Verfügbarkeit. Die Logs enthielten auch vorübergehende
HA-Verbindungsfehler und Zeitüberschreitungen.
[Ablauf und Ergebnisse — EN](docs/operator/process-and-results.md) ·
[Prüfprotokoll](docs/evidence/cerbo-unit-verification-2026-10-16.json).

## Steuerung und Sicherheit

In der konfigurierten Anlage steuern aktive HA-Automationen Pumpe und Ventil.
`ENABLE_CONTROL=False` beibehalten, bis die Zuständigkeit bewusst übertragen
wird. Zwischen mehreren Schreibern gibt es weder Sperre noch Befehlsabstimmung.

Der Schalter deaktiviert **nur automatische Entscheidungen**. Manuelle
`/Mode`-Befehle und das Schließen beim geregelten Herunterfahren bleiben aktiv.
Ein Neustart kann das Ventil schließen und ist deshalb keine passive Zustandsprüfung.

Ventil-AUTO öffnet standardmäßig bei ≤30% und schließt bei ≥85%, mit mindestens
60 Sekunden zwischen normalen Wechseln. Nach 120 Sekunden ohne frische Daten
wird das Schließen angefordert. Nach diesem Schließen öffnet ein Messwert im
mittleren Bereich nicht von selbst wieder. `/Mode`: `0` AUTO, `1` EIN, `2` AUS.
Manuell EIN umgeht die automatische Regel für veraltete Messwerte.
Die Pumpe hat keine automatische Füllstandsregelung.

![Ventilhysterese: Öffnen bis 30 Prozent, Schließen ab 85 Prozent, dazwischen bleibt die vorherige Entscheidung bestehen.](docs/assets/hysteresis.svg)

Eine HA-Bestätigung belegt keine physische Ventilschließung. Stromausfall,
unzugängliches HA oder defekte Hardware können das Schließen verhindern.
Geeignete physische Schutzmaßnahmen bleiben erforderlich.
[Steuerungs- und Fehlermodell — EN](docs/operator/control.md).

## Sprachen und Schnittstellen

`LANGUAGE` unterstützt `en`, `ru`, `de`, `nl`. Gebietsschemavarianten werden
normalisiert; unbekannte Sprachen fallen auf Englisch zurück. Gerätenamen und
D-Bus-Anzeigetexte für Zustand/Modus werden übersetzt. Logs bleiben Englisch.
Entitätsnamen, numerische Werte, Pfade und Identitäten ändern sich nicht:

- Tank: `com.victronenergy.tank.ha_tank21`.
- Pumpe: `com.victronenergy.pump.startstop1`.
- Ventil: `com.victronenergy.pump.startstop2`.
- MQTT: `N/<portal>/tank/21/Level`, `N/<portal>/pump/1/State`,
  `N/<portal>/pump/2/State`.

[Übersetzungen ergänzen — EN](docs/operator/localization.md).
Die ausführlichen Handbücher, Wiki-Seiten und Texte innerhalb der SVGs sind Englisch.

## Fehlerbehebung und Entwicklung

- Falscher Prozentwert: HA-Einheit, konfigurierte Einheit, Kapazität, Radius und
  Offset prüfen. Fehler nicht durch geänderte Steuerschwellen ausgleichen.
- Messwerte fehlen: HA, Token und Entitäten prüfen. Ungültige Daten verlängern
  die Frist nicht; unbekanntes Volumen ist kein gemessener leerer Tank.
- Dienst startet nicht: `dbus-pump-ha`, Abhängigkeiten und Logs prüfen.
- Unerwartetes Schalten: `/Mode` und sämtliche HA-Automationen prüfen.

[Fehlerbehebung — EN](docs/operator/troubleshooting.md) · [Wiki](docs/wiki/Home.md) ·
[Architektur](docs/architecture.md) · [SVG-Quellen](docs/assets/README.md)

Verbindliche Prüfungen: [CONTRIBUTING.md](CONTRIBUTING.md). Für die Anwendung:

```sh
.venv/bin/python -m pytest tests/
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
python3 docs/assets/generate.py --check
```

Mock-Tests belegen weder physische Schließung noch einen vollständigen GX-Neustart.
[Änderungen](CHANGELOG.md) · [Releases](RELEASING.md) · [Sicherheit](SECURITY.md) ·
[Prüfnachweise](docs/quality-evidence.md). Lizenz: [MIT](LICENSE).
