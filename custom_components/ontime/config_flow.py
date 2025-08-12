"""Config flow for Ontime integration."""
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
        # WICHTIG: Kein /api/v1 Prefix - Ontime nutzt direkte Pfade!
        self.base_url = f"http://{host}:{port}"
        self.info = {}

    async def authenticate(self) -> bool:
        """Test if we can authenticate with the host."""
        return await self._test_connection()

    async def _test_connection(self) -> bool:
        """Test connection to Ontime API."""
        try:
            # Versuche verschiedene Endpoints
            test_endpoints = [
                "/api/info",           # Neuer API Pfad
                "/api/v1/info",        # Alter API Pfad
                "/info",               # Direkter Pfad
                "/api/runtime",        # Runtime endpoint
                "/api/v1/runtime"      # Alter runtime
            ]
            
            for endpoint in test_endpoints:
                try:
                    _LOGGER.debug(f"Testing endpoint: {self.base_url}{endpoint}")
                    async with self.session.get(
                        f"{self.base_url}{endpoint}",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as response:
                        if response.status == 200:
                            # Speichere welcher Endpoint funktioniert hat
                            if "v1" in endpoint:
                                self.api_prefix = "/api/v1"
                            elif "/api/" in endpoint:
                                self.api_prefix = "/api"
                            else:
                                self.api_prefix = ""
                            
                            _LOGGER.info(f"Successfully connected using endpoint: {endpoint}")
                            
                            # Versuche Info zu holen
                            if "info" in endpoint:
                                self.info = await response.json()
                            return True
                except Exception as e:
                    _LOGGER.debug(f"Endpoint {endpoint} failed: {e}")
                    continue
            
            return False
            
        except Exception as err:
            _LOGGER.error(f"Unexpected error testing connection: {err}")
            return False

    async def get_info(self) -> dict:
        """Get Ontime server information."""
        try:
            # Nutze den gefundenen API prefix
            api_prefix = getattr(self, 'api_prefix', '/api')
            info_endpoint = f"{api_prefix}/info" if api_prefix else "/info"
            
            async with self.session.get(
                f"{self.base_url}{info_endpoint}",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    return await response.json()
                return {}
        except Exception as err:
            _LOGGER.error(f"Error getting info: {err}")
            return {}


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    session = async_get_clientsession(hass)
    hub = OntimeHub(data[CONF_HOST], data[CONF_PORT], session)

    if not await hub.authenticate():
        raise CannotConnect

    # Get server info for the title
    info = await hub.get_info()
    
    # Speichere den API prefix in den Daten
    api_prefix = getattr(hub, 'api_prefix', '/api')
    
    # Return info that you want to store in the config entry.
    return {
        "title": f"Ontime {info.get('version', 'Server')}",
        "info": info,
        "api_prefix": api_prefix
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
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Ensure we're not adding the same server twice
            unique_id = f"{user_input[CONF_HOST]}:{user_input[CONF_PORT]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Füge den API prefix zu den config daten hinzu
            user_input["api_prefix"] = info.get("api_prefix", "/api")

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

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a reconfiguration flow initialized by the user."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        
        if user_input is None:
            return self.async_show_form(
                step_id="reconfigure",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_HOST, default=entry.data.get(CONF_HOST)): str,
                        vol.Required(CONF_PORT, default=entry.data.get(CONF_PORT, DEFAULT_PORT)): int,
                    }
                ),
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Füge den API prefix zu den config daten hinzu
            user_input["api_prefix"] = info.get("api_prefix", "/api")
            
            # Update the existing entry
            self.hass.config_entries.async_update_entry(
                entry, data=user_input, title=info["title"]
            )
            await self.hass.config_entries.async_reload(entry.entry_id)
            return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=user_input[CONF_HOST]): str,
                    vol.Required(CONF_PORT, default=user_input[CONF_PORT]): int,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
