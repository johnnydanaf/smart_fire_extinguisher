# src/sense/sensor_fuser.py

import time
import threading
from datetime import datetime
from typing import Any

import board
import busio

from core.system_state import SystemState
from sense.sensor_parser import SensorParser
from sense.snapshot import SensorSnapshot


class SensorFuser:
    """
    Owns all sensors, runs polling threads, builds SensorSnapshots,
    and writes them to SystemState.sense_queue when thresholds are crossed.
    """

    def __init__(self, config: dict, state: SystemState):
        system_cfg = config.get("system", {})
        self._polling_idle_ms   = system_cfg.get("polling_interval_idle_ms",   10000) / 1000.0
        self._polling_active_ms = system_cfg.get("polling_interval_active_ms", 1000)  / 1000.0

        # Init I2C buses from config before building sensors
        i2c_buses = self._init_i2c_buses(system_cfg.get("i2c_buses", {}))

        # Build sensors — config no longer needed after this
        self._sensors = SensorParser.build_sensors(config, i2c_buses)

        self._state   = state
        self._running = False
        self._threads = []
        self._lock    = threading.Lock()

        self._latest_readings:   dict[str, Any]   = {}  # sensor_name -> physical value (float or grid)
        self._latest_normalized: dict[str, float] = {}  # sensor_name -> normalized float
        self._threshold_flags:   dict[str, bool]  = {}  # sensor_name -> threshold crossed
        self._faulted_sensors:   list[dict]        = []  # [{"name": ..., "faulted_at": ...}]

    # ------------------------------------------------------------------
    # Bus initialisation
    # ------------------------------------------------------------------

    def _init_i2c_buses(self, buses_cfg: dict) -> dict:
        """
        Build busio.I2C objects from the system.i2c_buses config section.

        Each entry: { "scl": "SCL", "sda": "SDA" }
        Pin names map to board attributes (board.SCL, board.D3, etc.)

        Returns:
            dict of bus_name -> busio.I2C
        """
        buses = {}
        for bus_name, bus_cfg in buses_cfg.items():
            scl_pin = getattr(board, bus_cfg["scl"])
            sda_pin = getattr(board, bus_cfg["sda"])
            buses[bus_name] = busio.I2C(scl_pin, sda_pin)
        return buses

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        self._running = True
        self._state.sense_running = True
        self._update_state_sensor_counts()
        self._spawn_sensor_threads()
        self._main_loop()

    def stop(self):
        self._running = False

    # ------------------------------------------------------------------
    # Thread management
    # ------------------------------------------------------------------

    def _spawn_sensor_threads(self):
        for sensor in self._sensors:
            if sensor.enabled:
                thread = threading.Thread(
                    target=self._sensor_loop,
                    args=(sensor,),
                    name=f"Sensor-{sensor.name}",
                    daemon=True,
                )
                thread.start()
                self._threads.append(thread)

    def _main_loop(self):
        while self._running and self._state.system_running:
            time.sleep(0.5)

        self._running = False
        for thread in self._threads:
            thread.join(timeout=1)
        self._state.sense_running = False

    # ------------------------------------------------------------------
    # Per-sensor thread loop
    # ------------------------------------------------------------------

    def _sensor_loop(self, sensor):
        while self._running and self._state.system_running:
            try:
                physical, normalized, threshold_hit = sensor.poll()

                with self._lock:
                    self._latest_readings[sensor.name]   = physical
                    self._latest_normalized[sensor.name] = normalized
                    self._threshold_flags[sensor.name]   = threshold_hit

                if threshold_hit:
                    self._on_threshold_triggered()

                interval = (
                    self._polling_active_ms
                    if self._state.sensor_triggered
                    else self._polling_idle_ms
                )
                time.sleep(interval)

            except Exception:
                sensor._fault_count += 1
                if sensor._fault_count >= sensor._max_retries:
                    self._mark_sensor_faulted(sensor)
                time.sleep(self._polling_active_ms)

    # ------------------------------------------------------------------
    # Threshold handling
    # ------------------------------------------------------------------

    def _on_threshold_triggered(self):
        self._state.sensor_triggered = True
        self._push_snapshot()

    def _push_snapshot(self):
        with self._lock:
            # Use stored threshold flags — set by poll(), based on per-sensor threshold_physical
            triggered_names = [
                name for name, hit in self._threshold_flags.items() if hit
            ]

            snapshot = SensorSnapshot(
                timestamp=datetime.now(),
                sensor_readings=dict(self._latest_readings),
                sensor_normalized=dict(self._latest_normalized),
                enabled_sensors=[s.name for s in self._sensors if s.enabled and not s.faulted],
                triggered_sensors=triggered_names,
                faulty_sensors=[f["name"] for f in self._faulted_sensors],
            )

        self._state.sense_queue.put(snapshot)

    # ------------------------------------------------------------------
    # Fault handling
    # ------------------------------------------------------------------

    def _mark_sensor_faulted(self, sensor):
        sensor._faulted = True
        with self._lock:
            self._faulted_sensors.append({
                "name": sensor.name,
                "faulted_at": datetime.now().isoformat(),
            })
        self._state.faulted_sensors = list(self._faulted_sensors)
        self._update_state_sensor_counts()

    def _update_state_sensor_counts(self):
        active_count = sum(
            1 for s in self._sensors
            if s.enabled and not s.faulted
        )
        self._state.active_sensor_count = active_count