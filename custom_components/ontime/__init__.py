"""The Ontime integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DOMAIN,
    DEFAULT_SCAN_INTERVAL,
    SERVICE_START,
    SERVICE_PAUSE,
    SERVICE_STOP,
    SERVICE_RELOAD,
    SERVICE_ROLL,
    SERVICE_LOAD_EVENT,
    SERVICE_START_EVENT,
    SERVICE_ADD_TIME,
    SERVICE_LOAD_EVENT_INDEX,
    SERVICE_LOAD_EVENT_CUE,
    ATTR_EVENT_ID,
    ATTR_EVENT_INDEX,
    ATTR_EVENT_CUE,
    ATTR_TIME,
    ATTR_DIRECTION,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ontime from a config entry."""
    coordinator = OntimeDataUpdateCoordinator(hass, entry)
    
    await coordinator.async_config_entry_first_refresh()
    
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await _async_register_services(hass, coordinator)
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok


async def _async_register_services(hass: HomeAssistant, coordinator) -> None:
    """Register Ontime services."""
    
    async def handle_start(call: ServiceCall) -> None:
        """Handle start service."""
        await coordinator.api_request("GET", "/start")
    
    async def handle_pause(call: ServiceCall) -> None:
        """Handle pause service."""
        await coordinator.api_request("GET", "/pause")
    
    async def handle_stop(call: ServiceCall) -> None:
        """Handle stop service."""
        await coordinator.api_request("GET", "/stop")
    
    async def handle_reload(call: ServiceCall) -> None:
        """Handle reload service."""
        await coordinator.api_request("GET", "/reload")
    
    async def handle_roll(call: ServiceCall) -> None:
        """Handle roll service."""
        await coordinator.api_request("GET", "/roll")
    
    async def handle_load_event(call: ServiceCall) -> None:
        """Handle load event service."""
        event_id = call.data.get(ATTR_EVENT_ID)
        await coordinator.api_request("GET", f"/load/id/{event_id}")
    
    async def handle_start_event(call: ServiceCall) -> None:
        """Handle start event service."""
        event_id = call.data.get(ATTR_EVENT_ID)
        await coordinator.api_request("GET", f"/start/id/{event_id}")
    
    async def handle_add_time(call: ServiceCall) -> None:
        """Handle add time service."""
        time = call.data.get(ATTR_TIME)
        direction = call.data.get(ATTR_DIRECTION, "add")
        # Convert milliseconds to seconds for the API
        time_seconds = time // 1000
        if direction in ["remove", "subtract"]:
            await coordinator.api_request("GET", f"/addtime/remove/{time_seconds}")
        else:
            await coordinator.api_request("GET", f"/addtime/add/{time_seconds}")
    
    async def handle_load_event_index(call: ServiceCall) -> None:
        """Handle load event by index service."""
        index = call.data.get(ATTR_EVENT_INDEX)
        await coordinator.api_request("GET", f"/load/index/{index}")
    
    async def handle_load_event_cue(call: ServiceCall) -> None:
        """Handle load event by cue service."""
        cue = call.data.get(ATTR_EVENT_CUE)
        await coordinator.api_request("GET", f"/load/cue/{cue}")
    
    # Check if services are already registered
    if not hass.services.has_service(DOMAIN, SERVICE_START):
        hass.services.async_register(DOMAIN, SERVICE_START, handle_start)
        hass.services.async_register(DOMAIN, SERVICE_PAUSE, handle_pause)
        hass.services.async_register(DOMAIN, SERVICE_STOP, handle_stop)
        hass.services.async_register(DOMAIN, SERVICE_RELOAD, handle_reload)
        hass.services.async_register(DOMAIN, SERVICE_ROLL, handle_roll)
        
        hass.services.async_register(
            DOMAIN, 
            SERVICE_LOAD_EVENT, 
            handle_load_event,
            schema=vol.Schema({
                vol.Required(ATTR_EVENT_ID): cv.string,
            })
        )
        
        hass.services.async_register(
            DOMAIN,
            SERVICE_START_EVENT,
            handle_start_event,
            schema=vol.Schema({
                vol.Required(ATTR_EVENT_ID): cv.string,
            })
        )
        
        hass.services.async_register(
            DOMAIN,
            SERVICE_ADD_TIME,
            handle_add_time,
            schema=vol.Schema({
                vol.Required(ATTR_TIME): cv.positive_int,
                vol.Optional(ATTR_DIRECTION): vol.In(["add", "remove", "subtract"]),
            })
        )
        
        hass.services.async_register(
            DOMAIN,
            SERVICE_LOAD_EVENT_INDEX,
            handle_load_event_index,
            schema=vol.Schema({
                vol.Required(ATTR_EVENT_INDEX): cv.positive_int,
            })
        )
        
        hass.services.async_register(
            DOMAIN,
            SERVICE_LOAD_EVENT_CUE,
            handle_load_event_cue,
            schema=vol.Schema({
                vol.Required(ATTR_EVENT_CUE): cv.string,
            })
        )


class OntimeDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching Ontime data from API."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize."""
        self.entry = entry
        self.host = entry.data[CONF_HOST]
        self.port = entry.data[CONF_PORT]
        # Verwende /api als Standard-Prefix (NICHT /api/v1)
        self.base_url = f"http://{self.host}:{self.port}/api"
        self.session = async_get_clientsession(hass)
        _LOGGER.info(f"Ontime coordinator initialized with base_url: {self.base_url}")
        
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
    
    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            async with async_timeout.timeout(10):
                return await self._fetch_data()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}")
    
    async def _fetch_data(self):
        """Fetch all relevant data from Ontime API."""
        data = {}
        
        try:
            # Get runtime state using /api/poll endpoint
            poll_response = await self.session.get(f"{self.base_url}/poll")
            
            # Akzeptiere sowohl 200 als auch 202 Status
            if poll_response.status in [200, 202]:
                poll_data = await poll_response.json()
                
                # Extract runtime data from payload
                if "payload" in poll_data:
                    runtime_data = poll_data["payload"]
                    data["runtime"] = runtime_data
                    
                    # Extract timer information
                    if "timer" in runtime_data:
                        data["timer"] = runtime_data["timer"]
                    
                    # Extract current event information
                    if "eventNow" in runtime_data:
                        data["current_event"] = runtime_data["eventNow"]
                    elif "currentEvent" in runtime_data:
                        data["current_event"] = runtime_data["currentEvent"]
                    
                    # Extract next event information
                    if "eventNext" in runtime_data:
                        data["next_event"] = runtime_data["eventNext"]
                    elif "nextEvent" in runtime_data:
                        data["next_event"] = runtime_data["nextEvent"]
                    
                    # Extract public next event (if different)
                    if "publicEventNext" in runtime_data:
                        data["public_next_event"] = runtime_data["publicEventNext"]
                    
                    # Check for negative timer (overtime)
                    if "timer" in runtime_data and runtime_data["timer"]:
                        timer_data = runtime_data["timer"]
                        current_time = timer_data.get("current", 0)
                        data["is_overtime"] = current_time < 0 if current_time is not None else False
                        data["overtime_seconds"] = abs(current_time) // 1000 if current_time and current_time < 0 else 0
                    
                    # Extract playback state
                    if "playback" in runtime_data:
                        data["playback"] = runtime_data["playback"]
                    elif "timer" in runtime_data and "playback" in runtime_data["timer"]:
                        data["playback"] = runtime_data["timer"]["playback"]
            else:
                _LOGGER.warning(f"Unexpected status code from poll endpoint: {poll_response.status}")
            
            # Try to get additional data - rundown for more event details
            try:
                rundown_response = await self.session.get(f"{self.base_url}/data/rundown")
                if rundown_response.status in [200, 202]:
                    rundown_data = await rundown_response.json()
                    if "payload" in rundown_data:
                        data["rundown"] = rundown_data["payload"]
                        
                        # Find next events in rundown if not already found
                        if "rundown" in data and isinstance(data["rundown"], list):
                            events = data["rundown"]
                            current_id = None
                            
                            # Get current event ID
                            if data.get("current_event") and data["current_event"]:
                                current_id = data["current_event"].get("id")
                            elif data.get("runtime", {}).get("selectedEventId"):
                                current_id = data["runtime"]["selectedEventId"]
                            
                            # Find current and next events
                            if current_id:
                                found_current = False
                                for event in events:
                                    if event.get("type") == "event":  # Skip non-events like blocks
                                        if found_current and not event.get("skip", False):
                                            # This is the next non-skipped event
                                            if "next_event" not in data:
                                                data["next_event"] = event
                                            break
                                        if event.get("id") == current_id:
                                            found_current = True
            except Exception as e:
                _LOGGER.debug(f"Could not fetch rundown data: {e}")
                pass  # Optional data
                
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error fetching data: {err}")
            raise UpdateFailed(f"Error fetching data: {err}")
        
        return data
    
    async def api_request(self, method: str, endpoint: str, data: dict = None):
        """Make API request to Ontime."""
        url = f"{self.base_url}{endpoint}"
        
        try:
            async with async_timeout.timeout(10):
                if method == "GET":
                    response = await self.session.get(url)
                elif method == "POST":
                    response = await self.session.post(url, json=data)
                elif method == "PUT":
                    response = await self.session.put(url, json=data)
                elif method == "DELETE":
                    response = await self.session.delete(url)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                # Akzeptiere sowohl 200 als auch 202 Status codes
                if response.status not in [200, 202]:
                    _LOGGER.error(f"API request failed with status {response.status}")
                    raise aiohttp.ClientError(f"Status {response.status}")
                
                # Ontime API returns JSON with payload wrapper
                if response.content_length and response.content_length > 0:
                    result = await response.json()
                    return result.get("payload", result)
                return None
                
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error making API request to {endpoint}: {err}")
            raise
        except Exception as err:
            _LOGGER.error(f"Unexpected error in API request: {err}")
            raise
