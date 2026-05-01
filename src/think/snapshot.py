import exceptions
from dataclasses import dataclass, feild
from datetime import datetime
from sense import SensorSnapshot
from see import VisionSnapshot

@dataclass
class ThinkSnapshot():
    # system variables
    timestamp: datetime

    # system snapshots
    sensor_snapshot: SensorSnapshot
    vision_snapshot: VisionSnapshot

    # think derived
    growth_rate: float      # derived through weighted calculation of the rate of all inputs
    escelation_trend: str   # labeled by xgboost
    danger_level: int
    danger_label: str       # may be redundant if danger levels are enums
    recommended_action: str # based on danger level and available hardware

    # all vector points needed to be inputted to xgboost
    # they are derived from db walkback of all saved sensor snapshots and vision snapshots saved
    # calculations are never saved in the db bcz its faster to recompute, we can max cache them for speed
    growth_rates: dict      # key = sensor name, value = velocity or growth rate
    growth_trend: dict      # key = sensor name, value = acceleration or growth trend

