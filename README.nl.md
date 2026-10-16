# dbus-pump

[English](README.md) · [Русский](README.ru.md) · [Deutsch](README.de.md) · [Nederlands](README.nl.md)

**Versie:** expliciete eenheden, de diagnostische tweede sensor, lokalisatie en
strengere opdrachtvalidatie zijn **nog niet uitgebrachte wijzigingen**. Gebruik
deze bronversie of een latere release die ze bevat; oudere versies kunnen anders
werken. Zie [CHANGELOG.md](CHANGELOG.md).

Een koppeling tussen Home Assistant en **Victron Venus OS** voor watertank,
pomp en klep. De toepassing draait op de Cerbo GX, leest HA-entiteiten en
publiceert native D-Bus-diensten voor GX-schermen en Cerbo-MQTT-clients.
Klepautomatisering is optioneel; de pomp heeft handmatige bediening.

![HA-metingen worden op de Cerbo omgerekend en via D-Bus en MQTT gepubliceerd; optionele opdrachten gaan terug naar HA.](docs/assets/architecture.svg)

## Installatie

Gebruik systeem-Python **3.12.x**, `requests`, D-Bus en GI/GLib die bij de
Venus-OS-firmware horen. Vervang systeem-Python niet. De ontwikkelomgeving
gebruikt Python 3.12.13.

1. Plaats het pakket in `/data/dbus-pump`.
2. Kopieer `local_config.example.py` naar `local_config.py` en vul HA-URL, token,
   entiteiten, eenheden en tankafmetingen in. Houd het token privé.
3. Laat `ENABLE_CONTROL = False` staan totdat metingen en bediening zijn gecontroleerd.
4. Controleer afhankelijkheden en installeer:

```sh
python3 --version
python3 -c "import requests, dbus; from gi.repository import GLib"
/data/dbus-pump/setup install
svstat /service/dbus-pump-ha /service/dbus-pump-ha/log
readlink /service/dbus-pump-ha
tail -n 40 /var/log/dbus-pump-ha/current
```

De koppeling `/service/dbus-pump-ha` moet verwijzen naar
`/data/dbus-pump/service/dbus-pump`. `/service/dbus-pump` is de afzonderlijke
firmwaredienst; verwijder die map of het bijbehorende `down`-bestand niet.

Met ingestelde SSH-toegang kan installatie vanaf een computer via `./deploy.sh Cerbo`.
Een aanwezige lokale `local_config.py` **vervangt daarbij de apparaatconfiguratie**.
Gewone pakketupdates behouden de configuratie op het apparaat. Vergelijk na
installatie verse D-Bus-waarden met HA; alleen processtatus `up` is onvoldoende.
[Installatie en herstel — EN](docs/operator/installation.md).

## Configuratie en eenheden

Dit voorbeeld hoort bij de geconfigureerde installatie; controleer de entiteiten
en maten van uw eigen tank voordat u ze overneemt:

```python
HA_URL = "http://homeassistant.local:8123"
HA_TOKEN = "replace_with_private_long_lived_token"
HA_WATER_LEVEL_ENTITY = "sensor.water_level_2_water_level"
HA_WATER_LEVEL_UNIT = "cm"
HA_PUMP_SWITCH_ENTITY = "switch.pump_power_enable"
HA_VALVE_SWITCH_ENTITY = "switch.shutoff_valve"
TANK_CAPACITY_LITERS = 387.0
TANK_WATER_CM_ENTITY = "sensor.water_cm"  # alleen diagnose
TANK_OFFSET_CM = 18.0
TANK_RADIUS_CM = 35.56
LANGUAGE = "nl"
ENABLE_CONTROL = False
```

**93 cm is geen 93%.** Kies `HA_WATER_LEVEL_UNIT="cm"` voor waterhoogte of
`"%"` voor een al berekend percentage. De standaard blijft `"%"`.
Een niet-lege eenheid uit HA moet overeenkomen met de configuratie. De cm-modus
vereist een eindige positieve inhoud en straal en een eindige offset;
ongeldige geometrie verhindert het starten.

Voor een verticale cilinder is het volume in liters:
`max(0, cm − offset) × π × straal² / 1000`, begrensd op de tankinhoud.
Met deze afmetingen betekent 93 cm ongeveer **297,94 L en 76,99%**.
D-Bus `/Level` gebruikt altijd procenten; `/Capacity` en `/Remaining` gebruiken
**m³**: `0.298 m³` staat na afronding voor ongeveer 298 L.

In de procentmodus is het restvolume de inhoud maal hetzelfde percentage.
`TANK_WATER_CM_ENTITY` is nu alleen diagnostisch en overschrijft het volume niet
meer met een tweede sensor. Dit wijzigt het eerdere gedrag. De formule geldt
niet voor horizontale cilinders of onregelmatige tanks. Afstand tot het
wateroppervlak moet eerst worden omgerekend naar waterhoogte.

![Berekende curve voor een tank van 387 L, een lege offset van 18 cm en een straal van 35,56 cm: 93 cm is ongeveer 77 procent.](docs/assets/calibration.svg)

[Volledige configuratie — EN](docs/operator/configuration.md) ·
[Kalibratie en beperkingen — EN](docs/operator/calibration.md)

## Bediening en veiligheid

In de geconfigureerde installatie bedienen actieve HA-automatiseringen de pomp
en klep. Behoud `ENABLE_CONTROL=False` totdat een operator die verantwoordelijkheid
bewust overdraagt. Er is geen vergrendeling of afstemming tussen meerdere programma's.

Deze instelling schakelt **alleen automatische beslissingen** uit. Handmatige
`/Mode`-opdrachten en het sluiten van de klep bij normaal afsluiten blijven actief.
Een herstart kan de klep sluiten en is dus geen passieve gezondheidscontrole.

Klep-AUTO opent standaard bij ≤30% en sluit bij ≥85%, met minstens 60 seconden
tussen normale omschakelingen. Zonder verse gegevens wordt na 120 seconden
sluiten aangevraagd. Na zo'n sluiting opent de klep niet vanzelf door een waarde
midden in het bereik. `/Mode`: `0` AUTO, `1` AAN, `2` UIT. Handmatig AAN omzeilt
de automatische regel voor verouderde meetgegevens. De pomp heeft geen
automatische regeling op basis van tankniveau.

![Klephysterese: openen tot 30 procent, sluiten vanaf 85 procent; daartussen blijft de vorige beslissing behouden.](docs/assets/hysteresis.svg)

Een bevestiging van HA bewijst niet dat de klep fysiek dicht is. Stroomuitval,
onbereikbaar HA of defecte apparatuur kunnen sluiten verhinderen. Passende
fysieke beveiliging blijft nodig. [Besturing en fouten — EN](docs/operator/control.md).

## Talen en interfaces

`LANGUAGE` ondersteunt `en`, `ru`, `de`, `nl`. Localevarianten worden genormaliseerd;
onbekende talen vallen terug op Engels. Apparaatnamen en D-Bus-weergaveteksten
voor status en modus worden vertaald. Logberichten blijven Engels. Entiteitsnamen,
numerieke waarden, paden en identificaties veranderen niet:

- Tank: `com.victronenergy.tank.ha_tank21`.
- Pomp: `com.victronenergy.pump.startstop1`.
- Klep: `com.victronenergy.pump.startstop2`.
- MQTT: `N/<portal>/tank/21/Level`, `N/<portal>/pump/1/State`,
  `N/<portal>/pump/2/State`.

[Vertalingen aanvullen — EN](docs/operator/localization.md).
De uitgebreide handleidingen, wiki en teksten binnen SVG's zijn voorlopig Engels.

## Problemen oplossen en ontwikkelen

- Verkeerd percentage: controleer HA-eenheid, geconfigureerde eenheid, inhoud,
  straal en offset. Compenseer een eenhedenfout niet met andere schakeldrempels.
- Ontbrekende metingen: controleer HA, token en entiteiten. Ongeldige data verlengt
  de versheidstermijn niet; onbekend volume is geen gemeten lege tank.
- Dienst start niet: controleer `dbus-pump-ha`, afhankelijkheden en logboek.
- Onverwacht schakelen: controleer `/Mode` en alle HA-automatiseringen.

[Probleemoplossing — EN](docs/operator/troubleshooting.md) · [Wiki](docs/wiki/Home.md) ·
[Architectuur](docs/architecture.md) · [SVG-bronnen](docs/assets/README.md)

Verplichte controles: [CONTRIBUTING.md](CONTRIBUTING.md). Voor de toepassing:

```sh
.venv/bin/python -m pytest tests/
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
python3 docs/assets/generate.py --check
```

Tests met mocks bewijzen geen fysieke sluiting of volledige herstart van de GX.
[Wijzigingen](CHANGELOG.md) · [Releases](RELEASING.md) · [Beveiliging](SECURITY.md) ·
[Testbewijs](docs/quality-evidence.md). Licentie: [MIT](LICENSE).
