# Copy to local_config.py and fill in real values. NEVER commit local_config.py.

# Home Assistant
HA_URL = "http://192.168.1.50:8123"
HA_TOKEN = "your_long_lived_access_token_here"

# HA entities
HA_WATER_LEVEL_ENTITY = "sensor.water_level_2_water_level"  # tank level in %
HA_PUMP_SWITCH_ENTITY = "switch.pump_switch"
HA_VALVE_SWITCH_ENTITY = "switch.shutoff_valve"

# Tank: /Capacity + remaining liters computed HERE from the raw water-column
# height (no HA-side template sensor needed):
#   liters = (cm - TANK_OFFSET_CM) * pi * TANK_RADIUS_CM^2 / 1000
TANK_CAPACITY_LITERS = 387.0
TANK_WATER_CM_ENTITY = "sensor.water_cm"  # raw height in cm from HA
TANK_OFFSET_CM = 18.0  # sensor reading at empty tank (dead zone below)
TANK_RADIUS_CM = 35.56  # cylinder radius

# D-Bus instances (verify no collision on the GX: see TODO 4.1)
DEVICE_INSTANCE_TANK = 21  # com.victronenergy.tank.<N>
PUMP_STARTSTOP_INSTANCE = 1  # com.victronenergy.pump.startstop<N> (pump)
VALVE_STARTSTOP_INSTANCE = 2  # com.victronenergy.pump.startstop<N> (valve)

# Control logic
ENABLE_CONTROL = False  # master switch for automated actuation - enable after site tuning!
VALVE_START_VALUE = 30.0  # open valve when level <= this %
VALVE_STOP_VALUE = 85.0  # close valve when level >= this %
SENSOR_STALE_TIMEOUT = 120.0  # s without fresh level -> force valve CLOSED
MIN_SWITCH_INTERVAL = 60.0  # min seconds between valve transitions (anti-chatter)
POLL_INTERVAL = 2.0  # s between HA polls
