"""Sensor platform for Ontime integration."""
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ontime sensor based on a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors = [
        OntimeTimerSensor(coordinator, entry),
        OntimeStateSensor(coordinator, entry),
        OntimeCurrentEventSensor(coordinator, entry),
        OntimeOvertimeSensor(coordinator, entry),
        OntimeElapsedSensor(coordinator, entry),
        OntimeExpectedEndSensor(coordinator, entry),
    ]
    
    async_add_entities(sensors)


class OntimeBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Ontime sensors."""
    
    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Ontime {entry.data['host']}",
            manufacturer="Ontime",
            model="Timer System",
        )


class OntimeTimerSensor(OntimeBaseSensor):
    """Sensor for current timer value."""
    
    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_timer"
        self._attr_name = "Ontime Timer"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = "ms"
        self._attr_state_class = SensorStateClass.MEASUREMENT
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and "timer" in self.coordinator.data:
            return self.coordinator.data["timer"].get("current")
        return None
    
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        if self.coordinator.data and "timer" in self.coordinator.data:
            timer_data = self.coordinator.data["timer"]
            return {
                "duration": timer_data.get("duration"),
                "elapsed": timer_data.get("elapsed"),
                "expected_end": timer_data.get("expectedEnd"),
                "started_at": timer_data.get("startedAt"),
                "finished_at": timer_data.get("finishedAt"),
                "seconds_till_end": timer_data.get("secondsToEnd"),
            }
        return {}


class OntimeStateSensor(OntimeBaseSensor):
    """Sensor for playback state."""
    
    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_state"
        self._attr_name = "Ontime Playback State"
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and "runtime" in self.coordinator.data:
            return self.coordinator.data["runtime"].get("playback")
        return "unknown"
    
    @property
    def icon(self):
        """Return the icon based on state."""
        state = self.native_value
        if state == "play":
            return "mdi:play"
        elif state == "pause":
            return "mdi:pause"
        elif state == "stop":
            return "mdi:stop"
        return "mdi:timer"


class OntimeCurrentEventSensor(OntimeBaseSensor):
    """Sensor for current event information."""
    
    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_current_event"
        self._attr_name = "Ontime Current Event"
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data and "current_event" in self.coordinator.data:
            event = self.coordinator.data["current_event"]
            return event.get("title", "Unknown Event")
        return "No Event"
    
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        if self.coordinator.data and "current_event" in self.coordinator.data:
            event = self.coordinator.data["current_event"]
            return {
                "event_id": event.get("id"),
                "cue": event.get("cue"),
                "note": event.get("note"),
                "colour": event.get("colour"),
                "is_public": event.get("isPublic"),
                "skip": event.get("skip"),
                "time_start": event.get("timeStart"),
                "time_end": event.get("timeEnd"),
                "duration": event.get("duration"),
            }
        return {}


class OntimeOvertimeSensor(OntimeBaseSensor):
    """Sensor for overtime detection."""
    
    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_overtime"
        self._attr_name = "Ontime Overtime"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = "s"
        self._attr_state_class = SensorStateClass.MEASUREMENT
    
    @property
    def native_value(self):
        """Return the overtime in seconds."""
        if self.coordinator.data:
            return self.coordinator.data.get("overtime_seconds", 0)
        return 0
    
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            "is_overtime": self.coordinator.data.get("is_overtime", False) if self.coordinator.data else False
        }
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        super()._handle_coordinator_update()
        
        # Fire event when timer goes into overtime
        if self.coordinator.data and self.coordinator.data.get("is_overtime"):
            if not hasattr(self, "_was_overtime") or not self._was_overtime:
                self.hass.bus.async_fire(
                    f"{DOMAIN}_overtime_started",
                    {
                        "entity_id": self.entity_id,
                        "event_title": self.coordinator.data.get("current_event", {}).get("title"),
                        "overtime_seconds": self.coordinator.data.get("overtime_seconds", 0),
                    }
                )
                self._was_overtime = True
        else:
            self._was_overtime = False


class OntimeElapsedSensor(OntimeBaseSensor):
    """Sensor for elapsed time."""
    
    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_elapsed"
        self._attr_name = "Ontime Elapsed Time"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = "ms"
        self._attr_state_class = SensorStateClass.MEASUREMENT
    
    @property
    def native_value(self):
        """Return the elapsed time."""
        if self.coordinator.data and "timer" in self.coordinator.data:
            return self.coordinator.data["timer"].get("elapsed")
        return None


class OntimeExpectedEndSensor(OntimeBaseSensor):
    """Sensor for expected end time."""
    
    def __init__(self, coordinator, entry):
        """Initialize the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_expected_end"
        self._attr_name = "Ontime Expected End"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
    
    @property
    def native_value(self):
        """Return the expected end time."""
        if self.coordinator.data and "timer" in self.coordinator.data:
            expected_end = self.coordinator.data["timer"].get("expectedEnd")
            if expected_end:
                from datetime import datetime
                try:
                    return datetime.fromtimestamp(expected_end / 1000)
                except:
                    pass
        return None