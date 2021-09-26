"""Support for tracking which astronomical or meteorological season it is."""
from datetime import datetime, timedelta
import logging

import ephem
import voluptuous as vol

from homeassistant import util
from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import CONF_NAME, CONF_TYPE, TIME_DAYS
from homeassistant.helpers import config_validation as cv
from homeassistant.util import Throttle
from homeassistant.util.dt import utcnow

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Season"

DEVICE_CLASS_SEASON = "season__season"

EQUATOR = "equator"
NORTHERN = "northern"
SOUTHERN = "southern"

STATE_NONE = None
STATE_AUTUMN = "autumn"
STATE_SPRING = "spring"
STATE_SUMMER = "summer"
STATE_WINTER = "winter"

TYPE_ASTRONOMICAL = "astronomical"
TYPE_METEOROLOGICAL = "meteorological"

ENTITY_SEASON = "season"
ENTITY_DAYS_LEFT = "days_left"
ENTITY_DAYS_IN = "days_in"
ENTITY_NEXT_SEASON_UTC = "next_season_utc"

VALID_TYPES = [
    TYPE_ASTRONOMICAL,
    TYPE_METEOROLOGICAL,
]

HEMISPHERE_SEASON_SWAP = {
    STATE_WINTER: STATE_SUMMER,
    STATE_SPRING: STATE_AUTUMN,
    STATE_AUTUMN: STATE_SPRING,
    STATE_SUMMER: STATE_WINTER,
}

SEASON_ICONS = {
    STATE_NONE: "mdi:cloud",
    STATE_SPRING: "mdi:flower",
    STATE_SUMMER: "mdi:sunglasses",
    STATE_AUTUMN: "mdi:leaf",
    STATE_WINTER: "mdi:snowflake",
    ENTITY_DAYS_LEFT: "mdi:calendar-arrow-right",
    ENTITY_DAYS_IN: "mdi:calendar-arrow-left",
    ENTITY_NEXT_SEASON_UTC: "mdi:calendar-arrow-left",
}

MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=30)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ENTITY_SEASON,
        name="Season",
        icon=SEASON_ICONS[STATE_NONE],
    ),
    SensorEntityDescription(
        key=ENTITY_DAYS_LEFT,
        name="Days Left",
        icon=SEASON_ICONS[ENTITY_DAYS_LEFT],
    ),
    SensorEntityDescription(
        key=ENTITY_DAYS_IN,
        name="Days In",
        icon=SEASON_ICONS[ENTITY_DAYS_IN],
    ),
    SensorEntityDescription(
        key=ENTITY_NEXT_SEASON_UTC,
        name="Next Season Start Date",
        icon=SEASON_ICONS[ENTITY_NEXT_SEASON_UTC],
    ),
)


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_TYPE, default=TYPE_ASTRONOMICAL): vol.In(VALID_TYPES),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Display the current season."""
    if None in (hass.config.latitude, hass.config.longitude):
        _LOGGER.error("Latitude or longitude not set in Home Assistant config")
        return False

    latitude = util.convert(hass.config.latitude, float)
    _type = config.get(CONF_TYPE)
    name = config.get(CONF_NAME)

    if latitude < 0:
        hemisphere = SOUTHERN
    elif latitude > 0:
        hemisphere = NORTHERN
    else:
        hemisphere = EQUATOR

    if EQUATOR in hemisphere:
        _LOGGER.warning(
            "Season cannot be determined for equator, 'unknown' state will be shown"
        )

    _LOGGER.debug(_type)

    season_data = SeasonData(hemisphere, _type)

    entities = []
    for description in SENSOR_TYPES:
        if description.key in ENTITY_SEASON:
            entities.append(Season(season_data, description, name))
        elif hemisphere not in EQUATOR:
            entities.append(Season(season_data, description, name))

    async_add_entities(entities, True)


class Season(SensorEntity):
    """Representation of the current season."""

    def __init__(
        self,
        season_data,
        description: SensorEntityDescription,
        name,
    ):
        """Initialize the sensor."""
        self.entity_description = description
        if name in DEFAULT_NAME and description.key != ENTITY_SEASON:
            self._attr_name = f"{name} {description.name}"
        else:
            self._attr_name = f"{description.name}"
        self.season_data = season_data

    async def async_update(self):
        """Get the latest data from Season and update the state."""
        await self.season_data.async_update()
        if self.entity_description.key in self.season_data.data:
            self._attr_native_value = self.season_data.data[self.entity_description.key]
            if self.entity_description.key in ENTITY_SEASON:
                self._attr_icon = SEASON_ICONS[
                    self.season_data.data[self.entity_description.key]
                ]
                self._attr_device_class = DEVICE_CLASS_SEASON
            if  self.entity_description.key in (ENTITY_DAYS_LEFT, ENTITY_DAYS_IN):
                self._attr_native_unit_of_measurement  = TIME_DAYS

class SeasonData:
    """Calculate the current season."""

    def __init__(self, hemisphere, _type):
        """Initialize the data object."""

        self.hemisphere = hemisphere
        self.datetime = None
        self.type = _type
        self._data = {}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from season."""
        # Update data
        self.datetime = utcnow().replace(tzinfo=None)
        self._data = get_season(self)


def get_season(self):
    """Calculate the current season."""

    date = self.datetime
    hemisphere = self.hemisphere
    season_tracking_type = self.type
    data = {}

    if season_tracking_type == TYPE_ASTRONOMICAL:
        spring_start = ephem.next_equinox(str(date.year)).datetime()
        summer_start = ephem.next_solstice(str(date.year)).datetime()
        autumn_start = ephem.next_equinox(spring_start).datetime()
        winter_start = ephem.next_solstice(summer_start).datetime()
    else:
        spring_start = datetime(2017, 3, 1).replace(year=date.year)
        summer_start = spring_start.replace(month=6)
        autumn_start = spring_start.replace(month=9)
        winter_start = spring_start.replace(month=12)

    if hemisphere != EQUATOR:
        if date < spring_start or date >= winter_start:
            season = STATE_WINTER
            if date.month >= 12:
                spring_start = ephem.next_equinox(str(date.year + 1)).datetime()
            else:
                winter_start = ephem.next_solstice(
                    summer_start.replace(year=date.year - 1)
                ).datetime()
            days_left = spring_start.date() - date.date()
            days_in = date.date() - winter_start.date()
            next_date = spring_start
        elif date < summer_start:
            season = STATE_SPRING
            days_left = summer_start.date() - date.date()
            days_in = date.date() - spring_start.date()
            next_date = summer_start
        elif date < autumn_start:
            season = STATE_SUMMER
            days_left = autumn_start.date() - date.date()
            days_in = date.date() - summer_start.date()
            next_date = autumn_start
        elif date < winter_start:
            season = STATE_AUTUMN
            days_left = winter_start.date() - date.date()
            days_in = date.date() - autumn_start.date()
            next_date = winter_start
    else:
        season = STATE_NONE
        days_left = STATE_NONE
        days_in = STATE_NONE
        next_date = STATE_NONE

    # If user is located in the southern hemisphere swap the season
    if hemisphere == SOUTHERN:
        season = HEMISPHERE_SEASON_SWAP.get(season)

    if hemisphere == EQUATOR:
        self.data = {
            ENTITY_SEASON: season,
            ENTITY_DAYS_LEFT: days_left,
            ENTITY_DAYS_IN: days_in,
            ENTITY_NEXT_SEASON_UTC: next_date,
        }
    else:
        self.data = {
            ENTITY_SEASON: season,
            ENTITY_DAYS_LEFT: days_left.days,
            ENTITY_DAYS_IN: abs(days_in.days) + 1,
            ENTITY_NEXT_SEASON_UTC: next_date.strftime("%Y %b %d %H:%M:%S"),
        }

    return data
