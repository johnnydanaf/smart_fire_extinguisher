# src/sense/sensors/sensor_base.py

from abc import ABC, abstractmethod
import time


class SensorFaultError(Exception):
    """Custom exception raised when a sensor fails after all retries"""
    pass


class Sensor(ABC):
    """
    Abstract base class for all sensor types.
    
    Every sensor (I2C, UART, GPIO) inherits from this class.
    Provides common functionality: conversion, validation, threshold checking.
    Each subclass only needs to implement read() and _ping().
    """

    def __init__(self, name: str, config: dict):
        """
        Initialize sensor with configuration from config.json
        
        Args:
            name: Sensor identifier (from config key)
            config: Sensor configuration dict section
        """
        # Identity
        self.name = name
        self.enabled = config.get('enabled', True)
        self.interface = config['interface']
        
        # Raw value range (child classes need this for conversion)
        self.raw_min = float(config['raw_min'])
        self.raw_max = float(config['raw_max'])
        
        # Physical value range (also used for validation)
        self.physical_min = float(config['physical_min'])
        self.physical_max = float(config['physical_max'])
        self.threshold_physical = float(config['threshold_physical'])
        self.unit = config['unit']
        
        # Retry configuration
        self._max_retries = config.get('max_retries', 3)
        
        # Runtime state (accessed by SensorFuser)
        self._faulted = False
        self._fault_count = 0
    
    # ============================================
    # ABSTRACT METHODS (child must implement)
    # ============================================
    
    @abstractmethod
    def read(self) -> float:
        """
        Read from hardware and return PHYSICAL value.
        
        Child class must:
        1. Read raw value from hardware
        2. Convert to physical units
        3. Return physical value
        
        Returns:
            float: Physical value in sensor's units (ppm, °C, etc.)
        """
        pass
    
    @abstractmethod
    def _ping(self) -> None:
        """
        Test that the hardware is reachable and correctly configured.
        
        Child class implements hardware-specific validation:
        - I2C: Scan bus for device address
        - UART: Test serial port connection
        - GPIO: Verify pin is accessible
        
        Raises:
            Exception: On any hardware failure
        """
        pass
    
    # ============================================
    # HARDWARE VALIDATION
    # ============================================
    
    def ping(self) -> bool:
        """
        Validate sensor hardware at startup.
        
        Calls child's _ping() method and handles exceptions.
        Used by SensorFuser to verify hardware before polling.
        
        Returns:
            bool: True if hardware responding, False if faulted
        """
        try:
            self._ping()
            return True
        except Exception:
            self._faulted = True
            return False
    
    # ============================================
    # CONVERSION METHOD
    # ============================================
    
    def to_normalized(self, physical_value: float) -> float:
        """
        Convert physical value to normalized 0.0-1.0 scale for ML.
        
        Args:
            physical_value: Physical value in sensor's units
            
        Returns:
            float: Normalized value in range [0.0, 1.0]
        """
        physical_range = self.physical_max - self.physical_min
        
        if physical_range == 0:
            return 0.0
        
        normalized_value = (physical_value - self.physical_min) / physical_range
        
        # Clamp to [0, 1]
        return max(0.0, min(1.0, normalized_value))
    
    # ============================================
    # VALIDATION & THRESHOLD
    # ============================================
    
    def is_valid(self, physical_value: float) -> bool:
        """
        Check if physical value is within expected range.
        
        Uses physical_min and physical_max from config.
        
        Args:
            physical_value: Physical value to validate
            
        Returns:
            bool: True if valid, False if out of range
        """
        return self.physical_min <= physical_value <= self.physical_max
    
    def threshold_hit(self, physical_value: float) -> bool:
        """
        Check if physical value has crossed the alert threshold.
        
        Args:
            physical_value: Physical value to check
            
        Returns:
            bool: True if threshold crossed, False otherwise
        """
        return physical_value >= self.threshold_physical
    
    # ============================================
    # POLLING METHOD (orchestrates everything)
    # ============================================
    
    def poll(self) -> tuple[float, float, bool]:
        """
        Complete sensor reading cycle with retry logic.
        
        This is the main method called by SensorFuser.
        Handles retries, validation, and threshold checking.
        
        Returns:
            tuple: (physical_value, normalized_value, threshold_hit)
            
        Raises:
            SensorFaultError: If sensor fails after all retries
        """
        for attempt in range(self._max_retries):
            try:
                # Step 1: Read physical value from hardware (child handles conversion)
                physical_value = self.read()
                
                # Step 2: Validate against physical range
                if not self.is_valid(physical_value):
                    # Invalid reading - retry
                    if attempt < self._max_retries - 1:
                        time.sleep(0.1)
                        continue
                    else:
                        raise ValueError(
                            f"{self.name}: Invalid reading {physical_value}{self.unit} "
                            f"(valid range: {self.physical_min}-{self.physical_max})"
                        )
                
                # Step 3: Reading is valid - calculate normalized and check threshold
                normalized_value = self.to_normalized(physical_value)
                threshold_crossed = self.threshold_hit(physical_value)
                
                # Step 4: Reset fault counter on success
                self._fault_count = 0
                
                # Step 5: Return tuple for SensorFuser
                return (physical_value, normalized_value, threshold_crossed)
                
            except Exception as e:
                # Reading failed - increment fault counter
                self._fault_count += 1
                
                if attempt < self._max_retries - 1:
                    # Not last attempt - retry
                    time.sleep(0.1)
                    continue
                else:
                    # All retries exhausted - raise fault
                    raise SensorFaultError(
                        f"{self.name} failed after {self._max_retries} retries: {str(e)}"
                    )
        
        # Should never reach here
        raise SensorFaultError(f"{self.name} polling failed")