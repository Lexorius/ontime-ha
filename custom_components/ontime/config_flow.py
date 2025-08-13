from __future__ import annotations

import logging
from typing import Any

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
        _LOGGER.info(f"OntimeHub initialized with base_url: {self.base_url}")

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        return await self._test_connection()

    async def _test_connection(self) -> bool:
        """Test connection to Ontime API."""
        _LOGGER.info(f"Starting connection test to {self.base_url}")
        
        # Teste die korrekte Ontime API
        test_endpoints = [
            "/api/version",
            "/api/poll",
        ]
        
        for endpoint in test_endpoints:
            full_url = f"{self.base_url}{endpoint}"
            _LOGGER.info(f"Testing endpoint: {full_url}")
            
            try:
                async with self.session.get(
                    full_url,
                    timeout=aiohttp.ClientTimeout(total=10),
                    headers={"Accept": "application/json"}
                ) as response:
                    _LOGGER.info(f"Response status from {endpoint}: {response.status}")
                    
                    if response.status == 200:
                        try:
                            data = await response.json()
                            _LOGGER.info(f"Response data from {endpoint}: {data}")
                            
                            # Ontime API returns data in payload wrapper
                            if "payload" in data:
                                if "version" in endpoint:
                                    self.info = {"version": data["payload"]}
                                _LOGGER.info(f"Successfully connected to Ontime! Version: {data.get('payload', 'unknown')}")
                                return True
                            else:
                                _LOGGER.warning(f"No 'payload' in response from {endpoint}")
                        except Exception as json_err:
                            _LOGGER.error(f"Error parsing JSON from {endpoint}: {json_err}")
                            text = await response.text()
                            _LOGGER.error(f"Response text: {text}")
                    else:
                        text = await response.text()
                        _LOGGER.warning(f"Non-200 response from {endpoint}: {response.status}, text: {text}")
                        
            except aiohttp.ClientConnectorError as conn_err:
                _LOGGER.error(f"Connection error to {full_url}: {conn_err}")
            except aiohttp.ClientError as client_err:
                _LOGGER.error(f"Client error for {full_url}: {client_err}")
            except Exception as e:
                _LOGGER.error(f"Unexpected error for {full_url}: {type(e).__name__}: {e}")
        
        _LOGGER.error(f"All connection attempts failed for {self.base_url}")
        return False

    async def get_info(self) -> dict:
        """Get Ontime server information."""
        try:
            # Get version info
            url = f"{self.base_url}/api/version"
            _LOGGER.info(f"Getting version info from: {url}")
            
            async with self.session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    version = data.get("payload", "Unknown")
                    _LOGGER.info(f"Got version: {version}")
                    return {"version": version}
                else:
                    _LOGGER.error(f"Failed to get version, status: {response.status}")
                    return {}
        except Exception as err:
            _LOGGER.error(f"Error getting info: {err}")
            return {}


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    _LOGGER.info(f"Validating input - Host: {data[CONF_HOST]}, Port: {data[CONF_PORT]}")
    
    session = async_get_clientsession(hass)
    hub = OntimeHub(data[CONF_HOST], data[CONF_PORT], session)

    if not await hub.authenticate():
        _LOGGER.error(f"Authentication failed for {data[CONF_HOST]}:{data[CONF_PORT]}")
        raise CannotConnect

    # Get server info for the title
    info = await hub.get_info()
    _LOGGER.info(f"Validation successful. Info: {info}")
    
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
        _LOGGER.info("ConfigFlow initialized")

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        _LOGGER.info(f"async_step_user called with input: {user_input}")
        
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                errors=self._errors
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
            _LOGGER.info(f"Validation successful: {info}")
        except CannotConnect:
            _LOGGER.error("Cannot connect error")
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            _LOGGER.error("Invalid auth error")
            errors["base"] = "invalid_auth"
        except Exception as ex:
            _LOGGER.exception(f"Unexpected exception in config flow: {ex}")
            errors["base"] = "unknown"
        else:
            # Ensure we're not adding the same server twice
            unique_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Create the config entry
            _LOGGER.info(f"Creating entry with title: {info['title']}")
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
