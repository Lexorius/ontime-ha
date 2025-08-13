from __future__ import annotations

import logging
import socket
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
        # Erst mal testen ob der Host überhaupt erreichbar ist
        _LOGGER.info(f"Testing network connectivity to {self.host}:{self.port}")
        
        try:
            # DNS Test
            ip = socket.gethostbyname(self.host)
            _LOGGER.info(f"DNS resolved {self.host} to {ip}")
        except socket.gaierror as e:
            _LOGGER.error(f"DNS resolution failed for {self.host}: {e}")
        except Exception as e:
            _LOGGER.error(f"Unexpected error in DNS resolution: {e}")
        
        # Socket Test
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            result = sock.connect_ex((self.host, self.port))
            if result == 0:
                _LOGGER.info(f"Socket connection successful to {self.host}:{self.port}")
            else:
                _LOGGER.error(f"Socket connection failed to {self.host}:{self.port} with error code: {result}")
        except Exception as e:
            _LOGGER.error(f"Socket test failed: {e}")
        finally:
            sock.close()
        
        return await self._test_connection()

    async def _test_connection(self) -> bool:
        """Test connection to Ontime API."""
        _LOGGER.info(f"Starting HTTP connection test to {self.base_url}")
        
        # Teste verschiedene Endpoints und Methoden
        test_configs = [
            {"endpoint": "/api/version", "headers": {}},
            {"endpoint": "/api/poll", "headers": {}},
            {"endpoint": "/api/version", "headers": {"User-Agent": "Home-Assistant"}},
            {"endpoint": "/api/version", "headers": {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}},
        ]
        
        for config in test_configs:
            endpoint = config["endpoint"]
            headers = config["headers"]
            full_url = f"{self.base_url}{endpoint}"
            _LOGGER.info(f"Testing: {full_url} with headers: {headers}")
            
            try:
                # Verschiedene Timeout-Werte probieren
                timeout = aiohttp.ClientTimeout(
                    total=30,
                    connect=10,
                    sock_connect=10,
                    sock_read=10
                )
                
                async with self.session.get(
                    full_url,
                    timeout=timeout,
                    headers=headers,
                    ssl=False,  # SSL deaktivieren falls das ein Problem ist
                    allow_redirects=True
                ) as response:
                    _LOGGER.info(f"Response status from {endpoint}: {response.status}")
                    _LOGGER.info(f"Response headers: {response.headers}")
                    
                    if response.status == 200:
                        try:
                            # Versuche verschiedene Parsing-Methoden
                            content_type = response.headers.get('Content-Type', '')
                            _LOGGER.info(f"Content-Type: {content_type}")
                            
                            text = await response.text()
                            _LOGGER.info(f"Response text (first 500 chars): {text[:500]}")
                            
                            # Versuche JSON zu parsen
                            try:
                                import json
                                data = json.loads(text)
                                _LOGGER.info(f"Parsed JSON successfully: {data}")
                                
                                # Ontime API returns data in payload wrapper
                                if "payload" in data:
                                    if "version" in endpoint:
                                        self.info = {"version": data["payload"]}
                                    _LOGGER.info(f"Successfully connected to Ontime!")
                                    return True
                                elif isinstance(data, str):
                                    # Manchmal ist die Response direkt ein String
                                    self.info = {"version": data}
                                    _LOGGER.info(f"Successfully connected to Ontime (direct string response)!")
                                    return True
                            except json.JSONDecodeError as e:
                                _LOGGER.error(f"JSON decode error: {e}")
                                # Vielleicht ist es plain text?
                                if text and len(text) < 20:  # Kurzer Text könnte Version sein
                                    self.info = {"version": text.strip()}
                                    _LOGGER.info(f"Using plain text response as version: {text.strip()}")
                                    return True
                                
                        except Exception as e:
                            _LOGGER.error(f"Error processing response: {e}")
                    else:
                        text = await response.text()
                        _LOGGER.warning(f"Non-200 response: Status={response.status}, Text={text[:200]}")
                        
            except aiohttp.ClientConnectorError as e:
                _LOGGER.error(f"ClientConnectorError for {full_url}: {e}")
                _LOGGER.error(f"  Error type: {type(e).__name__}")
                _LOGGER.error(f"  OS Error: {e.os_error if hasattr(e, 'os_error') else 'N/A'}")
            except aiohttp.ServerTimeoutError as e:
                _LOGGER.error(f"ServerTimeoutError for {full_url}: {e}")
            except aiohttp.ClientError as e:
                _LOGGER.error(f"ClientError for {full_url}: {e}")
            except asyncio.TimeoutError as e:
                _LOGGER.error(f"AsyncIO TimeoutError for {full_url}: {e}")
            except Exception as e:
                _LOGGER.error(f"Unexpected error for {full_url}: {type(e).__name__}: {e}")
                import traceback
                _LOGGER.error(f"Traceback: {traceback.format_exc()}")
        
        _LOGGER.error(f"All connection attempts failed for {self.base_url}")
        return False

    async def get_info(self) -> dict:
        """Get Ontime server information."""
        if self.info:
            return self.info
            
        try:
            url = f"{self.base_url}/api/version"
            _LOGGER.info(f"Getting version info from: {url}")
            
            async with self.session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    text = await response.text()
                    try:
                        import json
                        data = json.loads(text)
                        version = data.get("payload", data) if isinstance(data, dict) else data
                    except:
                        version = text.strip()
                    
                    _LOGGER.info(f"Got version: {version}")
                    return {"version": version}
                else:
                    _LOGGER.error(f"Failed to get version, status: {response.status}")
                    return {"version": "Unknown"}
        except Exception as err:
            _LOGGER.error(f"Error getting info: {err}")
            return {"version": "Unknown"}


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    import asyncio
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
