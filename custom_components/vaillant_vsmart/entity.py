"""Vaillant vSMART entity classes."""
import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)
from vaillant_netatmo_api import (
    ApiException,
    Device,
    Module,
    Program,
    ThermostatClient,
    MeasurementItem,
    MeasurementType,
    MeasurementScale,
    RequestUnauthorizedException,
)

from .const import DOMAIN


UPDATE_INTERVAL = timedelta(minutes=5)

_LOGGER: logging.Logger = logging.getLogger(__package__)


class VaillantData:
    """Class holding data which coordinator provides to the entity."""

    def __init__(self, client: ThermostatClient, devices: list[Device]) -> None:
        """Initialize."""

        self.client = client
        self.devices = {device.id: device for device in devices}
        self.modules = {
            module.id: module for device in devices for module in device.modules
        }
        self.programs = {
            program.id: program
            for device in devices
            for module in device.modules
            for program in module.therm_program_list
        }


class VaillantCoordinator(DataUpdateCoordinator[VaillantData]):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, client: ThermostatClient) -> None:
        """Initialize."""

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_method=self._update_method,
            update_interval=UPDATE_INTERVAL,
        )

        self._client = client

    async def _update_method(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """

        try:
            devices = await self._client.async_get_thermostats_data()

            measurements = await self._get_temperature_measurements_for_all_devices(
                devices
            )

            energy_usage = await self._get_energy_usage_measurements_for_all_devices(
                devices
            )

            self._debug_log(devices)
            self._update_measured_data(devices, measurements, energy_usage)
            self._debug_log(devices)

            return VaillantData(self._client, devices)
        except RequestUnauthorizedException as ex:
            raise ConfigEntryAuthFailed from ex
        except ApiException as ex:
            _LOGGER.exception(ex)
            raise UpdateFailed(f"Error communicating with API: {ex}") from ex

    async def _get_temperature_measurements_for_all_devices(
        self, devices: list[Device]
    ) -> list[list[MeasurementItem]]:
        temperature_tasks = []

        start_time = datetime.now() - timedelta(hours=1)

        for device in devices:
            for module in device.modules:
                current_temp_task = self._client.async_get_measure(
                    device.id,
                    module.id,
                    MeasurementType.TEMPERATURE,
                    MeasurementScale.MAX,
                    start_time,
                )
                temperature_tasks.append(current_temp_task)

                setpoint_temp_task = self._client.async_get_measure(
                    device.id,
                    module.id,
                    MeasurementType.SETPOINT_TEMPERATURE,
                    MeasurementScale.MAX,
                    start_time,
                )
                temperature_tasks.append(setpoint_temp_task)

        return await asyncio.gather(*temperature_tasks)

    async def _get_energy_usage_measurements_for_all_devices(
        self, devices: list[Device]
    ) -> list[list[MeasurementItem]]:
        gas_usage_tasks = []

        start_time = datetime.now() - timedelta(days=7)

        for device in devices:
            for module in device.modules:
                gas_heating_task = self._client.async_get_measure(
                    device.id,
                    module.id,
                    MeasurementType.SUM_ENERGY_GAS_HEATING,
                    MeasurementScale.DAY,
                    start_time,
                )
                gas_usage_tasks.append(gas_heating_task)

                gas_water_task = self._client.async_get_measure(
                    device.id,
                    module.id,
                    MeasurementType.SUM_ENERGY_GAS_WATER,
                    MeasurementScale.DAY,
                    start_time,
                )
                gas_usage_tasks.append(gas_water_task)

        return await asyncio.gather(*gas_usage_tasks)

    def _debug_log(self, devices: list[Device]) -> None:
        for device in devices:
            for module in device.modules:
                _LOGGER.debug(f"_temperature_: {module.measured.temperature}")
                _LOGGER.debug(f"setpoint_temp: {module.measured.setpoint_temp}")
                _LOGGER.debug(f"gas_heating_usage: {module.measured.gas_heating_usage}")
                _LOGGER.debug(f"gas_water_usage: {module.measured.gas_water_usage}")

    def _update_measured_data(
        self,
        devices: list[Device],
        measurements: list[list[MeasurementItem]],
        energy_usage: list[list[MeasurementItem]],
    ) -> None:
        i = 0

        for device in devices:
            for module in device.modules:
                module.measured.temperature = self._get_measurement_value(
                    measurements[i], module.measured.temperature
                )
                module.measured.setpoint_temp = self._get_measurement_value(
                    measurements[i + 1], module.measured.setpoint_temp
                )

                module.measured.gas_heating_usage = self._get_energy_measurement_value(
                    energy_usage[i], module.measured.gas_heating_usage
                )

                module.measured.gas_water_usage = self._get_energy_measurement_value(
                    energy_usage[i + 1], module.measured.gas_water_usage
                )

                i += 2

    def _get_measurement_value(
        self,
        measurements: list[MeasurementItem],
        default_value: float,
    ) -> float:
        measure = measurements[-1] if measurements else None

        return measure.value[-1] if measure and measure.value else default_value

    def _get_energy_measurement_value(
        self,
        measurements: list[MeasurementItem],
        default_value: list[float],
    ) -> list[float]:
        measure = measurements[-1] if measurements else None

        return measure.value if measure and measure.value else default_value


class VaillantEntity(CoordinatorEntity[VaillantData]):
    """Base class for Vaillant entities."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[VaillantData],
        device_id: str,
        module_id: str,
        program_id: str = None,
    ):
        """Initialize."""

        super().__init__(coordinator)

        self._device_id = device_id
        self._module_id = module_id
        self._program_id = program_id

    @property
    def _client(self) -> ThermostatClient:
        """Retrun the instance of the client which enables HTTP communication with the API."""

        return self.coordinator.data.client

    @property
    def _device(self) -> Device:
        """Return the device which this entity represents."""

        return self.coordinator.data.devices[self._device_id]

    @property
    def _module(self) -> Module:
        """Return the module which this entity represents."""

        return self.coordinator.data.modules[self._module_id]

    @property
    def _program(self) -> Program:
        """Return the program which this entity represents."""

        if self._program_id is None:
            return None

        return self.coordinator.data.programs[self._program_id]

    @property
    def device_info(self) -> dict[str, Any]:
        """Return all device info available for this entity."""

        return {
            "identifiers": {(DOMAIN, self._module.id)},
            "name": self._module.module_name,
            "sw_version": self._module.firmware,
            "manufacturer": self._device.type,
            "via_device": (DOMAIN, self._device.id),
        }
