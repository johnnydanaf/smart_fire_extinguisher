# src/sense/sensor_base.py

from abc import ABC, abstractmethod
from exceptions import SensorFaultError


class Sensor(ABC):

    def __init__():
        # BE CAREFUL TO HAVE THE SAME CALL FROM THE SENSOR PARSER 
        # INIT SHOULD ONLY TAKE THE CONFIFG DICT SECTION
        pass

    @property
    def name(self) -> str:
        return self._name

    @property
    def faulted(self) -> bool:
        return self._faulted

    @abstractmethod
    def read(self) -> float:
        """Return the TRANSFORMED PHYCIAL VALUE THAT A HUMAN CAN UNDERSTAND sensor value."""
        # READ SHOULD HANDLE FALSE READINGS AND RETRY MAX TRETRIES INTERNALLY, SO NO NEED TO HANDLE RETRIES IN POLL() FUNCTION, JUST CALL READ() AND RETURN THE RESULTS AS A TUPLE
        # MAX RETRIES SHOULD BE HANDLED INTERNALLY IN THE READ FUNCTION, SO IF A READING IS OUTSIDE THE VALID RANGE, IT SHOULD RETRY UP TO MAX_RETRIES TIMES BEFORE RAISING AN EXCEPTION
        # MAX RETRIES IS FROM THE SENSOR CONFIG AS WELL AND CAN BE DIFFERENT FOR EACH SENSOR, SO IT SHOULD BE HANDLED INTERNALLY IN THE READ FUNCTION AND NOT IN THE POLL FUNCTION
        pass

    # IF YOU CANNOT FULLY SUPPORT THIS AND EXPLAIN IT AS I HAVE NEVER HEARD OF A BUILT IN PING FIND AN IMPLEMENTATIOHN YOU CAN SUPPORT
    @abstractmethod
    def _ping(self) -> None:
        """
        Test that the hardware is reachable and correctly configured.
        Must raise on any failure — exception is caught by ping().
        """
        pass

    def ping(self) -> bool:
        """
        Validate sensor hardware at startup.
        Calls _ping(); sets _faulted=True and returns False on any exception.
        """
        try:
            self._ping()
            return True
        except Exception:
            self._faulted = True
            return False

    def poll(self) -> tuple[float, float, bool]:
        """
        Read the sensor up to max_retries times.
        Returns (physical_value, normalized_value, threshold_hit).
        A reading outside [valid_min, valid_max] counts as a failed attempt.
        Sets _faulted=True and raises SensorFaultError after all retries fail.
        """
        
        #poll should call read() and to_normalized() and threshold_hit() and return the results as a tuple
        # the read() function is updated to return the pysical human interpreted vaue and not raw value, so the poll() function should call read() and then to_normalized() and threshold_hit() and return the results as a tuple
        # read should handle false readings and retry max tretries internally, so no need to handle retries in poll() function, just call read() and return the results as a tuple
        pass

    def to_normalized(self, physical: float) -> float:
        # Convert a physical value to a normalized value in RANGE [0, 1].
        span = self._physical_max - self._physical_min
        if span == 0:
            return 0.0
        return max(0.0, min(1.0, (physical - self._physical_min) / span))

    def threshold_hit(self, physical: float) -> bool:
        return physical >= self._threshold_physical