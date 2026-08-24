"""Home Assistant REST client.

Reads water entities through one batched /api/template call and actuates
switches via /api/services. Serves last-known values while HA is unreachable,
guarded by a circuit breaker (pattern copied from inverter-control).
"""

import json
import logging
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

# Jinja template sent to /api/template. Tokens are replaced literally
# (str.format would fight the Jinja braces). @VOLUME@ is optional; when no
# volume entity is configured a placeholder id is used so states() renders
# 'unknown' instead of erroring on an empty entity_id.
TEMPLATE_BODY = """{{ {
  'level': states('@LEVEL@') | string,
  'pump': states('@PUMP@'),
  'valve': states('@VALVE@'),
  'volume': states('@VOLUME@') | string
} | to_json }}"""


class HomeAssistantError(Exception):
    """Base class for HA client errors."""


class HomeAssistantAPIError(HomeAssistantError):
    pass


class CircuitBreaker:
    """Opens after `threshold` consecutive failures; retries after reset_timeout s."""

    def __init__(self, threshold: int = 5, reset_timeout: float = 60.0) -> None:
        self.threshold = threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at >= self.reset_timeout:
            # Half-open: allow one attempt through.
            logger.info("Circuit breaker half-open, allowing retry")
            self._opened_at = None
            self._failures = self.threshold - 1  # one more failure re-opens
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._opened_at is None and self._failures >= self.threshold:
            self._opened_at = time.monotonic()
            logger.warning("Circuit breaker OPEN after %i consecutive failures", self._failures)


def build_template(
    level_entity: str, pump_entity: str, valve_entity: str, volume_entity: str = ""
) -> str:
    return (
        TEMPLATE_BODY.replace("@LEVEL@", level_entity)
        .replace("@PUMP@", pump_entity)
        .replace("@VALVE@", valve_entity)
        .replace("@VOLUME@", volume_entity or "__no_volume_sensor__")
    )


def state_is_on(state: Any) -> bool | None:
    """Map an HA state string to on/off. unavailable/unknown -> None."""
    s = str(state).strip().lower() if state is not None else ""
    if s in ("unavailable", "unknown", "", "none"):
        return None
    return s in ("on", "running", "open")


class HaClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        level_entity: str,
        pump_entity: str,
        valve_entity: str,
        timeout: float = 3.0,
        breaker: CircuitBreaker | None = None,
        volume_entity: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.level_entity = level_entity
        self.pump_entity = pump_entity
        self.valve_entity = valve_entity
        self.volume_entity = volume_entity  # optional liters sensor
        self.timeout = timeout
        self.breaker = breaker or CircuitBreaker()
        # Last-known-good snapshot, served while HA is unreachable.
        self.last_known: dict[str, Any] = {
            "level": None,
            "pump": None,
            "valve": None,
            "volume": None,
        }
        self._template = build_template(level_entity, pump_entity, valve_entity, volume_entity)
        self._configured = all((base_url, token, level_entity, pump_entity, valve_entity))
        self._session = requests.Session()
        if token:
            self._session.headers.update(
                {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
            )
        self._last_error_log = 0.0

    def _log_error_throttled(self, msg: str) -> None:
        now = time.monotonic()
        if now - self._last_error_log >= 60.0:
            self._last_error_log = now
            logger.error(msg)

    def poll(self) -> dict[str, Any]:
        """Fetch level/pump/valve states.

        Returns {'level': float|None, 'volume': float|None (liters),
        'pump': bool|None, 'valve': bool|None,
        'ok': bool} where ok=True means the values were fetched live on this
        call. On failure the last-known snapshot is returned with ok=False.
        """
        result = dict(self.last_known)
        result["ok"] = False
        if not self._configured:
            self._log_error_throttled("HA client not configured (local_config.py missing?)")
            return result
        if self.breaker.is_open:
            return result
        try:
            resp = self._session.post(
                f"{self.base_url}/api/template",
                json={"template": self._template},
                timeout=self.timeout,
            )
            if resp.status_code != 200:
                raise HomeAssistantAPIError(f"/api/template HTTP {resp.status_code}")
            data = json.loads(resp.text)
            level_raw = str(data.get("level", "")).strip()
            try:
                level: float | None = float(level_raw)
            except ValueError:
                level = None
            volume_raw = str(data.get("volume", "")).strip()
            try:
                volume: float | None = float(volume_raw)
            except ValueError:
                volume = None
            result.update(
                level=level,
                volume=volume,  # liters from HA (None when sensor unset/unavailable)
                pump=state_is_on(data.get("pump")),
                valve=state_is_on(data.get("valve")),
                ok=level is not None,
            )
            self.last_known = {k: result[k] for k in ("level", "pump", "valve", "volume")}
            self.breaker.record_success()
        except requests.exceptions.Timeout as exc:
            self.breaker.record_failure()
            self._log_error_throttled(f"HA timeout: {exc}")
        except requests.exceptions.RequestException as exc:
            self.breaker.record_failure()
            self._log_error_throttled(f"HA connection error: {exc}")
        except HomeAssistantError as exc:
            self.breaker.record_failure()
            self._log_error_throttled(str(exc))
        except ValueError as exc:
            self.breaker.record_failure()
            self._log_error_throttled(f"HA template returned invalid JSON: {exc}")
        return result

    def call_service(self, domain: str, action: str, entity_id: str) -> bool:
        """Call an HA service (e.g. switch/turn_on). Returns True on success."""
        if self.breaker.is_open:
            logger.warning("Circuit open, skipping %s/%s %s", domain, action, entity_id)
            return False
        try:
            resp = self._session.post(
                f"{self.base_url}/api/services/{domain}/{action}",
                json={"entity_id": entity_id},
                timeout=self.timeout,
            )
            if resp.status_code == 200:
                self.breaker.record_success()
                return True
            raise HomeAssistantAPIError(f"{domain}/{action} HTTP {resp.status_code}")
        except requests.exceptions.Timeout as exc:
            self.breaker.record_failure()
            self._log_error_throttled(f"HA timeout on {domain}/{action}: {exc}")
        except requests.exceptions.RequestException as exc:
            self.breaker.record_failure()
            self._log_error_throttled(f"HA error on {domain}/{action}: {exc}")
        except HomeAssistantError as exc:
            self.breaker.record_failure()
            self._log_error_throttled(str(exc))
        return False
