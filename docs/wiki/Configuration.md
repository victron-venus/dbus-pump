# Configuration

[Wiki home](Home.md) · [Calibration](Calibration.md)

Keep credentials in `local_config.py`, outside version control. Use
[the configuration example](../../local_config.example.py) and
[full reference](../operator/configuration.md).

```python
HA_WATER_LEVEL_ENTITY = "sensor.water_level_2_water_level"
HA_WATER_LEVEL_UNIT = "cm"
HA_PUMP_SWITCH_ENTITY = "switch.pump_power_enable"
HA_VALVE_SWITCH_ENTITY = "switch.shutoff_valve"
TANK_CAPACITY_LITERS = 387.0
TANK_OFFSET_CM = 18.0
TANK_RADIUS_CM = 35.56
LANGUAGE = "en"
ENABLE_CONTROL = False
```

These entity names and measurements describe the configured installation, not
universal defaults. Add your own `HA_URL` and private `HA_TOKEN`. `cm` mode uses
the primary sensor for both percent and remaining volume. `%` mode derives volume
from capacity and the same normalized percentage. The optional raw-cm entity is
diagnostic only. A nonempty HA unit must match the configured unit.

Default services are `tank.ha_tank21`, `pump.startstop1` and `pump.startstop2`
under `com.victronenergy`. `/Level` is %, volume paths are m³. `/Mode` is
`0` AUTO, `1` ON, `2` OFF. Translation changes display text, not these identities
or values. Choose unique instances and verify command ownership separately.
