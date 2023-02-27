"""The Vaillant vSMART climate platform."""
from __future__ import annotations
from datetime import datetime

import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, ENERGY_WATT_HOUR
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import VaillantCoordinator, VaillantEntity

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback
):
    """Set up Vaillant vSMART from a config entry."""

    coordinator: VaillantCoordinator = hass.data[DOMAIN][entry.entry_id]

    new_devices = [
        VaillantBatterySensor(coordinator, device.id, module.id)
        for device in coordinator.data.devices.values()
        for module in device.modules
    ]
    new_devices += [
        VaillantGasWaterSensor(coordinator, device.id, module.id)
        for device in coordinator.data.devices.values()
        for module in device.modules
    ]
    new_devices += [
        VaillantGasHeatingSensor(coordinator, device.id, module.id)
        for device in coordinator.data.devices.values()
        for module in device.modules
    ]

    async_add_devices(new_devices)


class VaillantBatterySensor(VaillantEntity, SensorEntity):
    """Vaillant vSMART Sensor."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this entity."""

        return self._module.id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""

        return f"{self._module.module_name} Battery"

    @property
    def entity_category(self) -> EntityCategory:
        """Return entity category for this sensor."""

        return EntityCategory.DIAGNOSTIC

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return device class for this sensor."""

        return SensorDeviceClass.BATTERY

    @property
    def state_class(self) -> SensorStateClass:
        """Return state class for this sensor."""

        return SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> str:
        """Return current value of battery level."""

        return str(self._module.battery_percent)

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of measurement for the battery level."""

        return PERCENTAGE


class VaillantGasWaterSensor(VaillantEntity, SensorEntity):
    """Vaillant vSMART Sensor."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this entity."""

        return f"{self._module.id}_gas_water"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""

        return f"{self._module.module_name} Water Gas usage"

    @property
    def entity_category(self) -> EntityCategory:
        """Return entity category for this sensor."""

        return EntityCategory.DIAGNOSTIC

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return device class for this sensor."""

        return SensorDeviceClass.ENERGY

    @property
    def state_class(self) -> SensorStateClass:
        """Return state class for this sensor."""

        return SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> str:
        """Return current value of gas water usage."""

        return str(
            self._module.measured.gas_water_usage[
                self._module.measured.gas_water_usage.__len__() - 1
            ]
        )

    @property
    def extra_state_attributes(self):
        return {"historical_values": str(self._module.measured.gas_water_usage)}

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of measurement for gas water usage"""

        return ENERGY_WATT_HOUR


class VaillantGasHeatingSensor(VaillantEntity, SensorEntity):
    """Vaillant vSMART Sensor."""

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this entity."""

        return f"{self._module.id}_gas_heating"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""

        return f"{self._module.module_name} Heating Gas usage"

    @property
    def entity_category(self) -> EntityCategory:
        """Return entity category for this sensor."""

        return EntityCategory.DIAGNOSTIC

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return device class for this sensor."""

        return SensorDeviceClass.ENERGY

    @property
    def state_class(self) -> SensorStateClass:
        """Return state class for this sensor."""

        return SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> str:
        """Return current value of gas heating usage."""

        return str(
            self._module.measured.gas_heating_usage[
                self._module.measured.gas_heating_usage.__len__() - 1
            ]
        )

    @property
    def extra_state_attributes(self):
        return {"historical_values": str(self._module.measured.gas_heating_usage)}

    @property
    def native_unit_of_measurement(self) -> str:
        """Return unit of measurement for gas heating usage."""

        return ENERGY_WATT_HOUR
