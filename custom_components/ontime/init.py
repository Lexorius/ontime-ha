"""The Ontime integration."""
import asyncio
import logging
from datetime import timedelta
from typing import Any

import aiohttp
import async_timeout
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
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
        await coordinator.api_request("POST", "/playback/start")
    
    async def handle_pause(call: ServiceCall) -> None:
        """Handle pause service."""
        await coordinator.api_request("POST", "/playback/pause")
    
    async def handle_stop(call: ServiceCall) -> None:
        """Handle stop service."""
        await coordinator.api_request("POST", "/playback/stop")
    
    async def handle_reload(call: ServiceCall) -> None:
        """Handle reload service."""
        await coordinator.api_request("POST", "/playback/reload")
    
    async def handle_roll(call: ServiceCall) -> None:
        """Handle roll service."""
        await coordinator.api_request("POST", "/playback/roll")
    
    async def handle_load_event(call: ServiceCall) -> None:
        """Handle load event service."""
        event_id = call.data.get(ATTR_EVENT_ID)
        await coordinator.api_request("POST", f"/playback/load/{event_id}")
    
    async def handle_start_event(call: ServiceCall) -> None:
        """Handle start event service."""
        event_id = call.data.get(ATTR_EVENT_ID)
        await coordinator.api_request("POST", f"/playback/start/{event_id}")
    
    async def handle_add_time(call: ServiceCall) -> None:
        """Handle add time service."""
        time = call.data.get(ATTR_TIME)
        direction = call.data.get(ATTR_DIRECTION, "both")
        await coordinator.api_request("POST", f"/playback/addtime/{direction}/{time}")
    
    async def handle_load_event_index(call: ServiceCall) -> None:
        """Handle load event by index service."""
        index = call.data.get(ATTR_EVENT_INDEX)
        await coordinator.api_request("POST", f"/playback/loadindex/{index}")
    
    async def handle_load_event_cue(call: ServiceCall) -> None:
        """Handle load event by cue service."""
        cue = call.data.get(ATTR_EVENT_CUE)
        await coordinator.api_request("POST", f"/playback/loadcue/{cue}")
    
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
            vol.Optional(ATTR_DIRECTION): vol.In(["both", "start", "duration", "end"]),
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
        self.host = entry.data["host"]
        self.port = entry.data["port"]
        self.base_url = f"http://{self.host}:{self.port}/api/v1"
        self.session = async_get_clientsession(hass)
        
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
    
    async def _fetch_data(self):
        """Fetch all relevant data from Ontime API."""
        data = {}
        
        # Get runtime state
        runtime_response = await self.session.get(f"{self.base_url}/runtime")
        runtime_data = await runtime_response.json()
        data["runtime"] = runtime_data
        
        # Get timer data
        timer_response = await self.session.get(f"{self.base_url}/timer")
        timer_data = await timer_response.json()
        data["timer"] = timer_data
        
        # Get current event
        if runtime_data.get("selectedEventId"):
            event_response = await self.session.get(
                f"{self.base_url}/events/{runtime_data['selectedEventId']}"
            )
            if event_response.status == 200:
                data["current_event"] = await event_response.json()
        
        # Check for negative timer (overtime)
        if timer_data.get("current") is not None:
            current_time = timer_data["current"]
            data["is_overtime"] = current_time < 0
            data["overtime_seconds"] = abs(current_time) if current_time < 0 else 0
        
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
                
                response.raise_for_status()
                return await response.json() if response.content_length else None
                
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Error making API request: {err}")
            raise