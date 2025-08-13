from __future__ import annotations

import logging
from typing import Any
import json

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_NAME

_LOGGER = logging.getLogger(__name__)

# Schema für die Benutzereingabe
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class OntimeHub:
    """Placeholder class to test connection to Ontime."""

    def __init__(self, host: str, port: int, session: aiohttp.ClientSession) -> None:
        """Initialize."""
        self.host = host
        self.port = port
        self.session = session
        self.base_url = f"http://{host}:{port}"
        self.info = {}

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        return await self._test_connection()

    async def _test_connection(self) -> bool:
        """Test connection to Ontime API."""
        # Teste die Ontime API endpoints
        test_endpoints = [
            "/api/version",
            "/api/poll",
        ]
        
        for endpoint in test_endpoints:
            full_url = f"{self.base_url}{endpoint}"
            
            try:
                async with self.session.get(
                    full_url,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    # Akzeptiere sowohl 200 als auch 202 Status
                    if response.status in [200, 202]:
                        try:
                            text = await response.text()
                            data = json.loads(text)
                            
                            # Ontime API returns data in payload wrapper
                            if "payload" in data:
                                if "version" in endpoint:
                                    # Version ist direkt im payload als String
                                    self.info = {"version": data["payload"]}
                                else:
                                    # Poll endpoint hat ein komplexes Objekt
                                    self.info = {"version": "Connected"}
                                
                                _LOGGER.info(f"Successfully connected to Ontime via {endpoint}")
                                return True
                                
                        except json.JSONDecodeError as e:
                            _LOGGER.error(f"JSON decode error: {e}")
                        except Exception as e:
                            _LOGGER.error(f"Error processing response: {e}")
                            
            except aiohttp.ClientError as e:
                _LOGGER.debug(f"Connection attempt failed for {full_url}: {e}")
            except Exception as e:
                _LOGGER.error(f"Unexpected error for {full_url}: {e}")
        
        return False

    async def get_info(self) -> dict:
        """Get Ontime server information."""
        if self.info:
            return self.info
            
        try:
            url = f"{self.base_url}/api/version"
            
            async with self.session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                # Akzeptiere sowohl 200 als auch 202
                if response.status in [200, 202]:
                    text = await response.text()
                    data = json.loads(text)
                    version = data.get("payload", "Unknown")
                    return {"version": version}
                else:
                    return {"version": "Unknown"}
        except Exception as err:
            _LOGGER.error(f"Error getting info: {err}")
            return {"version": "Unknown"}


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    session = async_get_clientsession(hass)
    hub = OntimeHub(data[CONF_HOST], data[CONF_PORT], session)

    if not await hub.authenticate():
        raise CannotConnect

    # Get server info for the title
    info = await hub.get_info()
    
    return {
        "title": f"Ontime {info.get('version', 'Server')}",
        "info": info
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ontime."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self):
        """Initialize the config flow."""
        self._errors = {}
        self._data = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=self._errors
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Ensure we're not adding the same server twice
            unique_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Create the config entry
            return self.async_create_entry(
                title=info["title"],
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        return await self.async_step_user(user_input)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
