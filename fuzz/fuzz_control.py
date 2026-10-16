"""Fuzz tank normalization and valve transitions with an explicit clock."""

import math
import struct
import sys
from pathlib import Path

import atheris

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with atheris.instrument_imports():
    from dbus_pump.control import MODE_AUTO, MODE_OFF, MODE_ON, ValveController
    from dbus_pump.tank import normalize_level


def check_level_normalization(data: bytes) -> None:
    value, capacity, offset, radius = struct.unpack("<4d", data[:32].ljust(32, b"\0"))
    percent = normalize_level(value, "%", 387.0, 18.0, 35.56, "%")
    if math.isfinite(value):
        assert percent == max(0.0, min(100.0, value))  # nosec B101 - test oracle
    else:
        assert percent is None  # nosec B101 - test oracle
    for unit in ("%", "cm"):
        result = normalize_level(value, unit, capacity, offset, radius, unit)
        invalid_geometry = not math.isfinite(capacity) or capacity < 0
        if unit == "cm":
            invalid_geometry = invalid_geometry or (
                capacity <= 0
                or not math.isfinite(offset)
                or not math.isfinite(radius)
                or radius <= 0
            )
        if invalid_geometry:
            assert result is None  # nosec B101 - invalid geometry must fail closed
        assert result is None or (math.isfinite(result) and 0 <= result <= 100)  # nosec B101 - test oracle
        assert normalize_level(value, unit, capacity, offset, radius, "mm") is None  # nosec B101 - test oracle
    assert normalize_level(True, "%", 387.0, 18.0, 35.56) is None  # nosec B101 - test oracle
    if (
        -1000 <= value <= 1000
        and 1 <= capacity <= 1000
        and -1000 <= offset <= 1000
        and 1 <= radius <= 100
    ):
        expected = max(
            0.0, min(100.0, (value - offset) * math.pi * radius * radius / 10 / capacity)
        )
        actual = normalize_level(value, "cm", capacity, offset, radius, "cm")
        assert actual is not None and math.isclose(actual, expected, abs_tol=1e-10)  # nosec B101 - test oracle


def test_one_input(data: bytes) -> None:
    check_level_normalization(data)
    now = 100.0
    control = ValveController(30.0, 80.0, 10.0, 2.0, clock=lambda: now)
    for offset in range(0, min(len(data), 4096) - 11, 12):
        record = data[offset : offset + 12]
        now += record[0] / 8
        requested_mode = record[1] % 5
        previous_mode = control.mode
        control.set_mode(requested_mode)
        if requested_mode not in (MODE_AUTO, MODE_ON, MODE_OFF):
            assert control.mode == previous_mode  # nosec B101 - intentional test oracle
        level = struct.unpack("<d", record[4:])[0]
        fresh = bool(record[2] & 1)
        previous_sample_time = control.last_level_time
        result, reason = control.update(level, fresh, sampled_at=now - record[3])
        assert isinstance(result, bool)  # nosec B101 - intentional test oracle
        if control.mode == MODE_OFF:
            assert result is False and reason == "manual-off"  # nosec B101 - intentional test oracle
        elif control.mode == MODE_ON:
            assert result is True and reason == "manual-on"  # nosec B101 - intentional test oracle
        elif control.last_level_time is None or now - control.last_level_time >= 10:
            assert result is False and reason == "stale-close"  # nosec B101 - intentional test oracle
        if not math.isfinite(level):
            assert control.last_level_time == previous_sample_time  # nosec B101 - intentional test oracle
    # Every state sequence must close after the existing sensor deadline expires.
    control.set_mode(MODE_AUTO)
    now += 11
    assert control.update(None, False) == (False, "stale-close")  # nosec B101 - intentional test oracle


if __name__ == "__main__":
    atheris.Setup(sys.argv, atheris.instrument_func(test_one_input))
    atheris.Fuzz()
