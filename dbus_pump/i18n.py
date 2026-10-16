"""Small, dependency-free catalog for D-Bus display names and enum text.

Only presentation strings are translated. Protocol identifiers, numeric values,
configuration names and diagnostics remain stable across languages. Language is
selected explicitly in configuration, never from the host process's locale.
"""

DEFAULT_LANGUAGE = "en"

CATALOGS: dict[str, dict[str, str]] = {
    "en": {
        "tank.name": "Water tank",
        "tank.custom_name": "Water tank (HA)",
        "pump.name": "Water pump",
        "valve.name": "City water valve",
        "connected": "Connected",
        "disconnected": "Disconnected",
        "unknown": "Unknown",
        "tank.status.ok": "OK",
        "tank.status.unknown_sensor": "Unknown sensor",
        "on": "On",
        "off": "Off",
        "valve.open": "Open",
        "valve.closed": "Closed",
        "mode.auto": "Automatic",
    },
    "ru": {
        "tank.name": "Бак для воды",
        "tank.custom_name": "Бак для воды (HA)",
        "pump.name": "Водяной насос",
        "valve.name": "Клапан городской воды",
        "connected": "Подключено",
        "disconnected": "Отключено",
        "unknown": "Неизвестно",
        "tank.status.ok": "Норма",
        "tank.status.unknown_sensor": "Нет данных датчика",
        "on": "Включено",
        "off": "Выключено",
        "valve.open": "Открыт",
        "valve.closed": "Закрыт",
        "mode.auto": "Автоматически",
    },
    "de": {
        "tank.name": "Wassertank",
        "tank.custom_name": "Wassertank (HA)",
        "pump.name": "Wasserpumpe",
        "valve.name": "Stadtwasserventil",
        "connected": "Verbunden",
        "disconnected": "Getrennt",
        "unknown": "Unbekannt",
        "tank.status.ok": "OK",
        "tank.status.unknown_sensor": "Keine Sensordaten",
        "on": "Ein",
        "off": "Aus",
        "valve.open": "Offen",
        "valve.closed": "Geschlossen",
        "mode.auto": "Automatisch",
    },
    "nl": {
        "tank.name": "Watertank",
        "tank.custom_name": "Watertank (HA)",
        "pump.name": "Waterpomp",
        "valve.name": "Leidingwaterklep",
        "connected": "Verbonden",
        "disconnected": "Niet verbonden",
        "unknown": "Onbekend",
        "tank.status.ok": "OK",
        "tank.status.unknown_sensor": "Geen sensorgegevens",
        "on": "Aan",
        "off": "Uit",
        "valve.open": "Open",
        "valve.closed": "Gesloten",
        "mode.auto": "Automatisch",
    },
}

SUPPORTED_LANGUAGES = tuple(CATALOGS)


def normalize_language(language: str | None) -> str:
    """Accept locale variants such as ``ru-RU`` or ``de_DE.UTF-8@euro``.

    Unsupported, empty or non-string configuration values use English. This is
    intentionally independent of LANG/LC_ALL and the OS's installed locales.
    """
    if not isinstance(language, str):
        return DEFAULT_LANGUAGE
    base = language.strip().lower().replace("_", "-")
    base = base.split(".", 1)[0].split("@", 1)[0].split("-", 1)[0]
    return base if base in CATALOGS else DEFAULT_LANGUAGE


def translate(message_id: str, language: str | None = DEFAULT_LANGUAGE) -> str:
    """Resolve a message, falling back to English and then its stable key."""
    catalog = CATALOGS[normalize_language(language)]
    return catalog.get(message_id, CATALOGS[DEFAULT_LANGUAGE].get(message_id, message_id))
