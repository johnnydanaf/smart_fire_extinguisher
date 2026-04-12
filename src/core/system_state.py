from multiprocessing import Manager
from core.enums import SystemMode


class SystemState:
    def __init__(self, manager, system_mode: str):
        self._data = manager.dict()

        self.sense_queue = manager.Queue()
        self.see_queue   = manager.Queue()
        self.think_queue = manager.Queue()

        self.sensor_triggered    = False
        self.active_sensor_count = 0
        self.faulted_sensors     = []
        self.system_running      = False
        self.sense_running       = False
        self.see_running         = False
        self.think_running       = False
        self.act_running         = False
        self.system_mode         = system_mode


    #--- bool ---

    @property
    def system_running(self) -> bool:
        return self._data['system_running']

    @system_running.setter
    def system_running(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError(f"system_running must be bool, got {type(value)}")
        self._data['system_running'] = value

    @property
    def sensor_triggered(self) -> bool:
        return self._data['sensor_triggered']

    @sensor_triggered.setter
    def sensor_triggered(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError(f"sensor_triggered must be bool, got {type(value)}")
        self._data['sensor_triggered'] = value

    @property
    def sense_running(self) -> bool:
        return self._data['sense_running']

    @sense_running.setter
    def sense_running(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError(f"sense_running must be bool, got {type(value)}")
        self._data['sense_running'] = value

    @property
    def see_running(self) -> bool:
        return self._data['see_running']

    @see_running.setter
    def see_running(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError(f"see_running must be bool, got {type(value)}")
        self._data['see_running'] = value

    @property
    def think_running(self) -> bool:
        return self._data['think_running']

    @think_running.setter
    def think_running(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError(f"think_running must be bool, got {type(value)}")
        self._data['think_running'] = value

    @property
    def act_running(self) -> bool:
        return self._data['act_running']

    @act_running.setter
    def act_running(self, value: bool):
        if not isinstance(value, bool):
            raise TypeError(f"act_running must be bool, got {type(value)}")
        self._data['act_running'] = value

    # --- int ---

    @property
    def active_sensor_count(self) -> int:
        return self._data['active_sensor_count']

    @active_sensor_count.setter
    def active_sensor_count(self, value: int):
        if not isinstance(value, int):
            raise TypeError(f"active_sensor_count must be int, got {type(value)}")
        if value < 0:
            raise ValueError(f"active_sensor_count cannot be negative, got {value}")
        self._data['active_sensor_count'] = value

    # --- enum ---

    @property
    def system_mode(self) -> SystemMode:
        return self._data['system_mode']

    @system_mode.setter
    def system_mode(self, value: str):
        try:
            self._data['system_mode'] = SystemMode(value)
        except ValueError:
            raise ValueError(f"Invalid system_mode '{value}'. Must be one of {[m.value for m in SystemMode]}")

    # --- list of dicts (full reassignment only) ---

    @property
    def faulted_sensors(self) -> list:
        return self._data['faulted_sensors']

    @faulted_sensors.setter
    def faulted_sensors(self, value: list):
        if not isinstance(value, list):
            raise TypeError(f"faulted_sensors must be a list, got {type(value)}")
        for entry in value:
            if not isinstance(entry, dict) or 'name' not in entry or 'faulted_at' not in entry:
                raise ValueError(f"Each faulted sensor must have 'name' and 'faulted_at', got {entry}")
        self._data['faulted_sensors'] = value