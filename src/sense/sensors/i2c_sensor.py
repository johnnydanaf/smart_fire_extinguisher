# src/sense/sensors/i2c_sensor.py

from sense.sensors.sensor_base import Sensor, SensorFaultError
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
import adafruit_amg88xx


class I2CSensor(Sensor):
    _DEVICE_HANDLERS = {
        "ads1115": {
            "setup": "_setup_ads1115",
            "read": "_read_ads1115"
        },
        "amg8833": {
            "setup": "_setup_amg8833",
            "read": "_read_amg8833"
        }
    }

    def __init__(self, config: dict, i2c_buses: dict):
        super().__init__(config)
        
        # Get bus
        bus_name = config['bus']
        if bus_name not in i2c_buses:
            raise ValueError(f"Bus '{bus_name}' not found")
        self.bus = i2c_buses[bus_name]
        
        self.device_type = config['device_type']
        self.address = int(config['address'], 16)
        
        # Validate and setup
        if self.device_type not in self._DEVICE_HANDLERS:
            raise ValueError(f"Unsupported device: {self.device_type}")
        
        setup_method = getattr(self, self._DEVICE_HANDLERS[self.device_type]["setup"])
        setup_method(config)
    
    def _setup_ads1115(self, config: dict):
        self.channel = config['channel']
        self.gain = config.get('gain', 1)
        
        self._ads = ADS.ADS1115(self.bus, address=self.address)
        self._ads.gain = self.gain
        
        channel_map = {0: ADS.P0, 1: ADS.P1, 2: ADS.P2, 3: ADS.P3}
        if self.channel not in channel_map:
            raise ValueError(f"Invalid channel: {self.channel}")
        
        self._channel = AnalogIn(self._ads, channel_map[self.channel])
    
    def _setup_amg8833(self, config: dict):
        self._amg = adafruit_amg88xx.AMG88XX(self.bus, addr=self.address)
    
    def _ping(self) -> None:
        while not self.bus.try_lock():
            pass
        try:
            devices = self.bus.scan()
            if self.address not in devices:
                raise IOError(f"Device not found at {hex(self.address)}")
        finally:
            self.bus.unlock()
    
    def read(self) -> float:
        """Read RAW value from hardware"""
        read_method = getattr(self, self._DEVICE_HANDLERS[self.device_type]["read"])
        return read_method()
    
    def _read_ads1115(self) -> float:
        """Return RAW ADC value (base class converts to physical)"""
        return float(self._channel.value)
    
    def _read_amg8833(self) -> float:
        """Return RAW max temperature (base class converts to physical)"""
        temperature_grid = self._amg.pixels
        max_temp = float('-inf')
        for row in temperature_grid:
            for pixel_temp in row:
                if pixel_temp > max_temp:
                    max_temp = pixel_temp
        return max_temp