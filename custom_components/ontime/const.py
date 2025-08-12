from datetime import timedelta

DOMAIN = "ontime"
DEFAULT_NAME = "Ontime"
DEFAULT_PORT = 4001
DEFAULT_SCAN_INTERVAL = timedelta(seconds=1)

CONF_HOST = "host"
CONF_PORT = "port"

# Services
SERVICE_START = "start"
SERVICE_PAUSE = "pause"
SERVICE_STOP = "stop"
SERVICE_RELOAD = "reload"
SERVICE_ROLL = "roll"
SERVICE_LOAD_EVENT = "load_event"
SERVICE_START_EVENT = "start_event"
SERVICE_ADD_TIME = "add_time"
SERVICE_LOAD_EVENT_INDEX = "load_event_index"
SERVICE_LOAD_EVENT_CUE = "load_event_cue"

# Attributes
ATTR_EVENT_ID = "event_id"
ATTR_EVENT_INDEX = "event_index"
ATTR_EVENT_CUE = "event_cue"
ATTR_TIME = "time"
ATTR_DIRECTION = "direction"