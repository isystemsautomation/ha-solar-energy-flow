DOMAIN = "solar_energy_flow"

CONF_PROCESS_VALUE_ENTITY = "process_value_entity"
CONF_SETPOINT_ENTITY = "setpoint_entity"
CONF_OUTPUT_ENTITY = "output_entity"
CONF_NAME = "name"
DEFAULT_NAME = "Solar Energy Flow Controller"

# Options (PID tuning)
CONF_KP = "kp"
CONF_KI = "ki"
CONF_KD = "kd"
CONF_MIN_OUTPUT = "min_output"
CONF_MAX_OUTPUT = "max_output"
CONF_UPDATE_INTERVAL = "update_interval"
CONF_ENABLED = "enabled"

DEFAULT_KP = 1.0
DEFAULT_KI = 0.0
DEFAULT_KD = 0.0
DEFAULT_MIN_OUTPUT = 0.0
DEFAULT_MAX_OUTPUT = 11000.0
DEFAULT_UPDATE_INTERVAL = 10
DEFAULT_ENABLED = True

PLATFORMS = ["sensor"]
