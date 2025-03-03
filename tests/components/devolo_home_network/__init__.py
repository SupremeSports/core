"""Tests for the devolo Home Network integration."""
from homeassistant.components.devolo_home_network.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from .const import IP

from tests.common import MockConfigEntry


def configure_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Configure the integration."""
    config = {
        CONF_IP_ADDRESS: IP,
    }
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)

    return entry
