"""Locale selection, catalog fallback, and wire-compatible display text."""

import pytest

from dbus_pump.i18n import CATALOGS, SUPPORTED_LANGUAGES, normalize_language, translate
from dbus_pump.service import NullDbusService, WaterSystemServices


@pytest.mark.parametrize(
    "requested,expected",
    [
        ("en", "en"),
        ("en_US.UTF-8", "en"),
        ("ru-RU", "ru"),
        (" RU_ru.utf8 ", "ru"),
        ("de_DE.UTF-8@euro", "de"),
        ("nl-NL", "nl"),
        ("nl_BE@euro", "nl"),
        ("fr_FR", "en"),
        ("C", "en"),
        ("POSIX", "en"),
        ("", "en"),
        (" \t ", "en"),
        (None, "en"),
        (False, "en"),
        (23, "en"),
        (["ru"], "en"),
    ],
)
def test_normalize_language(requested, expected):
    assert normalize_language(requested) == expected


def test_all_supported_catalogs_are_complete():
    assert set(SUPPORTED_LANGUAGES) == {"en", "ru", "de", "nl"}
    for language in SUPPORTED_LANGUAGES:
        assert CATALOGS[language].keys() == CATALOGS["en"].keys()
        assert all(
            isinstance(value, str) and value.strip() for value in CATALOGS[language].values()
        )


def test_missing_translation_falls_back_to_english(monkeypatch):
    monkeypatch.delitem(CATALOGS["ru"], "pump.name")
    assert translate("pump.name", "ru") == "Water pump"


def test_unknown_key_is_safe_to_display():
    assert translate("future.message", "de") == "future.message"


def test_unknown_language_uses_english():
    assert translate("valve.name", "xx_YY") == "City water valve"


def test_host_environment_does_not_change_default_language(monkeypatch):
    monkeypatch.setenv("LANG", "ru_RU.UTF-8")
    monkeypatch.setenv("LC_ALL", "de_DE.UTF-8")
    monkeypatch.setenv("LANGUAGE", "nl")
    assert translate("pump.name") == "Water pump"
    assert WaterSystemServices(21, 1, 2, "test").pump["/ProductName"] == "Water pump"


def test_app_builder_uses_explicit_language_config(monkeypatch):
    from dbus_pump import main

    monkeypatch.setattr(main.config, "LANGUAGE", "ru_RU.UTF-8")
    app = main.build_app()
    try:
        assert app.services.language == "ru"
        assert app.services.pump["/ProductName"] == "Водяной насос"
        assert app.services.valve.get_text("/Connected") == "Отключено"
    finally:
        app.client.close()


@pytest.mark.parametrize("language", SUPPORTED_LANGUAGES)
def test_translation_preserves_wire_values_and_service_identifiers(language):
    english = WaterSystemServices(21, 1, 2, "test", capacity_m3=0.5)
    translated = WaterSystemServices(21, 1, 2, "test", capacity_m3=0.5, language=language)
    for group in (english, translated):
        group.update_tank_level(60.0, remaining_m3=0.3)
        group.update_device_state("pump", True)
        group.update_device_state("valve", False)
        group.set_mode_quietly("valve", 2)
        group.set_connected(False)
    for name in ("tank", "pump", "valve"):
        original = getattr(english, name)
        localized = getattr(translated, name)
        assert original.service_name == localized.service_name
        assert original.items.keys() == localized.items.keys()
        for path, value in original.items.items():
            if path not in ("/ProductName", "/CustomName"):
                assert localized[path] == value
                assert type(localized[path]) is type(value)


@pytest.mark.parametrize(
    "language,name,on,closed,auto,missing,disconnected",
    [
        ("en", "Water pump", "On", "Closed", "Automatic", "Unknown sensor", "Disconnected"),
        (
            "ru-RU",
            "Водяной насос",
            "Включено",
            "Закрыт",
            "Автоматически",
            "Нет данных датчика",
            "Отключено",
        ),
        ("de", "Wasserpumpe", "Ein", "Geschlossen", "Automatisch", "Keine Sensordaten", "Getrennt"),
        (
            "nl",
            "Waterpomp",
            "Aan",
            "Gesloten",
            "Automatisch",
            "Geen sensorgegevens",
            "Niet verbonden",
        ),
    ],
)
def test_live_display_text_tracks_value_changes(
    language, name, on, closed, auto, missing, disconnected
):
    group = WaterSystemServices(21, 1, 2, "test", language=language)
    assert group.pump["/ProductName"] == name
    assert group.pump["/CustomName"] == name
    assert group.pump.get_text("/Mode") == auto
    assert group.pump.get_text("/State") == "---"
    group.update_device_state("pump", True)
    group.update_device_state("valve", False)
    group.update_tank_level(None)
    group.set_connected(False)
    assert group.pump.get_text("/State") == on
    assert group.valve.get_text("/State") == closed
    assert group.tank.get_text("/Status") == missing
    assert group.tank.get_text("/Level") == "---"
    for service in (group.tank, group.pump, group.valve):
        assert service.get_text("/Connected") == disconnected
    group.set_mode_quietly("valve", 1)
    assert group.valve.get_text("/Mode") == on
    group.update_device_state("pump", None)
    assert group.pump.get_text("/State") == "---"


def test_unknown_enum_value_does_not_raise_or_change_wire_value():
    group = WaterSystemServices(21, 1, 2, "test", language="ru")
    group.tank["/Status"] = 99
    assert group.tank.get_text("/Status") == "Неизвестно"
    assert group.tank["/Status"] == 99


@pytest.mark.parametrize("value", [[], {}, {1}])
def test_malformed_enum_values_have_safe_text(value):
    group = WaterSystemServices(21, 1, 2, "test", language="ru")
    group.tank["/Status"] = value
    assert group.tank.get_text("/Status") == "Неизвестно"
    assert group.tank["/Status"] == value


def test_null_service_text_matches_native_defaults_and_callback_signature():
    service = NullDbusService("test")
    calls = []
    service.add_path("/Level", 42.5)
    service.add_path("/ProductId", 0xFFFF)
    service.add_path("/Name", "Тест")
    service.add_path("/Empty", None, gettextcallback=lambda *_: pytest.fail("invalid callback"))
    service.add_path("/State", 1, gettextcallback=lambda p, v: calls.append((p, v)) or "On")
    assert service.get_text("/Level") == "42.5"
    assert service.get_text("/ProductId") == "0xFFFF"
    assert service.get_text("/Name") == "Тест"
    assert service.get_text("/Empty") == "---"
    assert service.get_text("/State") == "On"
    assert calls == [("/State", 1)]
    del service["/State"]
    service.add_path("/State", 5)
    assert service.get_text("/State") == "5"
