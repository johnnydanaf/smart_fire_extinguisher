from multiprocessing import Manager, Queue


class SystemState:
    def __init__(self, manager, system_mode: str):

        self._data = manager.dict()

        # queues — sense → see → think
        self.sense_queue = manager.Queue()
        self.see_queue = manager.Queue()
        self.think_queue = manager.Queue()

        # wake-up signal from SensorFuser to VisionFuser
        self._data['sensor_triggered'] = False

        # sensor health — written by SensorFuser, read by NotificationService
        self._data['active_sensor_count'] = 0
        self._data['faulted_sensors'] = []

        # process control — each process writes its own, orchestrator watches all
        self._data['system_running'] = False
        self._data['sense_running'] = False
        self._data['see_running'] = False
        self._data['think_running'] = False
        self._data['act_running'] = False

        # system config
        self._data['system_mode'] = system_mode