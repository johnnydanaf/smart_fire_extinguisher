from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class VisionSnapshot:
    """
    Output contract of the SEE layer.
    Emitted to SystemState.see_queue after a threshold crossing.

    Built by VisionFuser from the latest readings across all active cameras.
    Labels are dynamic and set in config.json
    ThinkEngine extracts flat values from this to build ThinkSnapshot.
    """

    # all strings will be transformed to enums at the think layer
    # since xgboost works only with numeric data
    # all labels are defined in config.json so all models know what to expect

    timestamp: datetime = field(default_factory=datetime.now)

    # scene understanding
    scene_label: str
    scene_confidence: str

    # fire assesment:
    composite_label: str    # fire_smoke fire smoke none

    # scene analysis
    glimpsed_fire: bool     # true if any fire box got detected by yolo even if low accuracy
    human_near_fire: bool   # if human label and fire whatsoever co-exist

    