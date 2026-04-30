import exceptions
from dataclasses import dataclass, feild
from datetime import datetime

@dataclass
class ThinkSnapshot():
    # system variables
    timestamp: datetime

    # system snapshots
    sensor_snapshot: