# src/sense/sensor_parser.py

import logging
from sense.sensors.sensor_base import Sensor
from sense.sensors.i2c_sensor import I2CSensor

logger = logging.getLogger(__name__)


class SensorParser:
    """
    Reads the 'sensors' section of config.json and builds the correct
    Sensor subclass for each entry.

    This is the ONLY place in the codebase where sensor types are branched on.
    Once the list is returned, SensorFuser treats every sensor as a generic Sensor.
    """

    _INTERFACE_MAP = {
        "i2c": I2CSensor,
        # "gpio":  GPIOSensor,   — not implemented yet
        # "uart":  UARTSensor,   — not implemented yet
    }

    @classmethod
    def build_sensors(cls, config: dict, i2c_buses: dict) -> list[Sensor]:
        """
        Parse the sensors section of config.json and return a list of
        Sensor objects ready for SensorFuser.

        Injects 'name' and resolved '_bus_object' into sensor_cfg before
        construction — sensors only need their own cfg dict, nothing else.

        Args:
            config:     Full config dict from orchestrator.
            i2c_buses:  Dict of bus_name -> busio.I2C, built by SensorFuser.

        Returns:
            List of Sensor objects (may be empty if no sensors enabled).
        """
        sensors = []
        sensor_configs = config.get("sensors", {})

        for sensor_name, sensor_cfg in sensor_configs.items():
            if not sensor_cfg.get("enabled", True):
                continue

            interface = sensor_cfg.get("interface", "").lower()
            if interface not in cls._INTERFACE_MAP:
                logger.warning(
                    f"Unknown interface '{interface}' for sensor '{sensor_name}'. Skipping."
                )
                continue

            # Always inject name
            sensor_cfg = {**sensor_cfg, "name": sensor_name}

            # Inject resolved bus object only for I2C
            if interface == "i2c":
                bus_name = sensor_cfg.get("bus")
                sensor_cfg["_bus_object"] = i2c_buses.get(bus_name) if bus_name else None

            sensor_class = cls._INTERFACE_MAP[interface]
            sensors.append(sensor_class(sensor_cfg))

        return sensors