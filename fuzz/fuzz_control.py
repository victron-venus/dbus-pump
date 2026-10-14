"""Fuzz the real valve state machine with an explicit monotonic clock."""

import math
import struct
import sys
from pathlib import Path

import atheris

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
with atheris.instrument_imports():
    from dbus_pump.control import MODE_AUTO, MODE_OFF, MODE_ON, ValveController


def test_one_input(data: bytes) -> None:
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
