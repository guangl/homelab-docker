"""Advertise the local hostname expected by Xiaomi Home's OAuth callback."""

from contextlib import suppress
from ipaddress import IPv4Address
import logging

import voluptuous as vol
from zeroconf import NotRunningException
from zeroconf.asyncio import AsyncServiceInfo

from homeassistant.components.zeroconf import async_get_async_instance
from homeassistant.const import EVENT_HOMEASSISTANT_STOP

DOMAIN = "xiaomi_oauth_mdns"
LOGGER = logging.getLogger(__name__)
CONFIG_SCHEMA = vol.Schema(
    {vol.Required(DOMAIN): {vol.Required("address"): vol.Coerce(IPv4Address)}},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, config):
    address = config[DOMAIN]["address"]
    zeroconf = await async_get_async_instance(hass)
    service = AsyncServiceInfo(
        "_http._tcp.local.",
        "Home Assistant Xiaomi OAuth._http._tcp.local.",
        addresses=[address.packed],
        port=8123,
        properties={"path": "/"},
        server="homeassistant.local.",
    )
    await zeroconf.async_register_service(service, allow_name_change=False)
    LOGGER.warning("Published the Xiaomi OAuth alias homeassistant.local")

    async def unregister(_event):
        with suppress(NotRunningException):
            await zeroconf.async_unregister_service(service)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, unregister)
    return True
