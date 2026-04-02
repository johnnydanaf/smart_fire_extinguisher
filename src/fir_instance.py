import csv
import os
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional
import numpy as np

# do actual wrappers why not

# Weights for danger_level computation — tune these after testing
ALPHA = 0.5   # frame_area_ratio weight
BETA  = 0.3   # smoke_level weight
GAMMA = 0.2   # max heat matrix weight


@dataclass
class FireInstance:
    """
    One snapshot of a fire detection event.
    Built from YOLO output + IoT sensor data.
    Saved periodically to CSV which acts as the live database
    for the ML prediction model.

    Sampling rate:
        IDLE   → 1 event / min  (camera off, infrared watching)
        LOCKED → 1 event / sec  (fire confirmed, full pipeline on)
    """

    # ai cam
    # images

    
    # --- YOLO outputs ---
    bbox_x: float               # bounding box centre x [0–1]
    bbox_y: float               # bounding box centre y [0–1]
    bbox_w: float               # bounding box width  [0–1]
    bbox_h: float               # bounding box height [0–1]
    fire_label: str             # e.g. "wildfire", "domestic", "electric"
    yolo_confidence: float      # YOLO detection confidence [0–1]

    # --- IoT sensor data ---
    heat_matrix: list           # 2D list of floats from heat matrix sensor
    smoke_level: float          # optical smoke sensor reading (ppm)
    lidar_z: float              # depth estimate in metres from LiDAR4

    # --- Normalised ratios ---

    # --- Computed on creation ---
    timestamp: datetime = field(default_factory=datetime.now)
    frame_area_ratio: float = field(init=False)   # bbox_w * bbox_h [0–1]
    danger_level: float = field(init=False)       # weighted composite [0–1]

    # --- Set after comparing with previous event ---
    growth_rate: float = 0.0          # Δdanger_level / Δt
    predicted_action: str = ""        # output from ML model

    def __post_init__(self):
        self.frame_area_ratio = self._compute_area_ratio()
        self.danger_level = self.compute_danger_level()

    # ------------------------------------------------------------------
    # Core computations
    # ------------------------------------------------------------------

    def _compute_area_ratio(self) -> float:
        """
        How much of the visible frame is occupied by fire.
        YOLO already normalises bbox to [0–1] so this is trivially [0–1].
        """
        pass
        # return float(np.clip(self.bbox_w * self.bbox_h, 0.0, 1.0))

    def compute_danger_level(self) -> float:
        """
        Weighted composite danger score [0.0 – 1.0].

            danger = α·frame_area_ratio + β·smoke_norm + γ·heat_norm

        smoke_norm  : smoke_level normalised to [0–1] (tune MAX_SMOKE)
        heat_norm   : max cell in heat_matrix normalised to [0–1] (tune MAX_HEAT)
        """
        # MAX_SMOKE = 1000.0   # ppm — adjust to sensor range
        # MAX_HEAT  = 150.0    # °C  — adjust to sensor range

        # smoke_norm = float(np.clip(self.smoke_level / MAX_SMOKE, 0.0, 1.0))
        # heat_norm  = float(np.clip(np.max(self.heat_matrix) / MAX_HEAT, 0.0, 1.0))

        # danger = ALPHA * self.frame_area_ratio + BETA * smoke_norm + GAMMA * heat_norm
        # return float(np.clip(danger, 0.0, 1.0))
        pass

    def compute_growth_rate(self, prev: "FireEvent") -> float:
        """
        Rate of change of danger_level between this event and the previous one.

            growth_rate = (danger_level[t] − danger_level[t−1]) / Δt

        Positive  → fire is growing
        Negative  → fire is shrinking / suppression working
        Zero      → stable

        Sets self.growth_rate and returns it.
        """
        # delta_t = (self.timestamp - prev.timestamp).total_seconds()
        # if delta_t <= 0:
        #     self.growth_rate = 0.0
        # else:
        #     self.growth_rate = (self.danger_level - prev.danger_level) / delta_t
        # return self.growth_rate
        pass

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """
        Flat dict representation for CSV row, API response, and email payload.
        heat_matrix is flattened to a string to fit in one CSV cell.
        """
        return {
            "timestamp":        self.timestamp.isoformat(),
            "bbox_x":           round(self.bbox_x, 4),
            "bbox_y":           round(self.bbox_y, 4),
            "bbox_w":           round(self.bbox_w, 4),
            "bbox_h":           round(self.bbox_h, 4),
            "fire_label":       self.fire_label,
            "yolo_confidence":  round(self.yolo_confidence, 4),
            "frame_area_ratio": round(self.frame_area_ratio, 4),
            "smoke_level":      round(self.smoke_level, 4),
            "lidar_z":          round(self.lidar_z, 4),
            "max_heat":         round(float(np.max(self.heat_matrix)), 4),
            "danger_level":     round(self.danger_level, 4),
            "growth_rate":      round(self.growth_rate, 4),
            "predicted_action": self.predicted_action,
        }

    CSV_COLUMNS = [
        "timestamp", "bbox_x", "bbox_y", "bbox_w", "bbox_h",
        "fire_label", "yolo_confidence", "frame_area_ratio",
        "smoke_level", "lidar_z", "max_heat",
        "danger_level", "growth_rate", "predicted_action",
    ]

    def save_to_csv(self, path: str = "fire_log.csv") -> None:
        """
        Append this event as one row to the CSV database.
        Creates the file with headers if it does not exist yet.
        """
        file_exists = os.path.isfile(path)
        with open(path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.CSV_COLUMNS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(self.to_dict())

    @classmethod
    def load_history(cls, path: str = "fire_log.csv") -> list[dict]:
        """
        Load all saved rows from the CSV as a list of dicts.
        Returns raw dicts — feed directly to pandas or the ML model.

        Usage:
            history = FireEvent.load_history("fire_log.csv")
            df = pd.DataFrame(history)
        """
        if not os.path.isfile(path):
            return []
        with open(path, "r") as f:
            reader = csv.DictReader(f)
            return list(reader)

    # ------------------------------------------------------------------
    # ML interface
    # ------------------------------------------------------------------

    def to_feature_vector(self) -> list[float]:
        """
        Flat numeric feature vector for ML model input.
        Feed a window of N of these to XGBoost or LSTM.

        Features: [frame_area_ratio, danger_level, growth_rate,
                   smoke_level, max_heat, lidar_z, yolo_confidence]
        """
        return [
            self.frame_area_ratio,
            self.danger_level,
            self.growth_rate,
            self.smoke_level,
            float(np.max(self.heat_matrix)),
            self.lidar_z,
            self.yolo_confidence,
        ]

    def predict_action(self, model) -> str:
        """
        Run the trained ML model on this event's feature vector.
        Sets self.predicted_action and returns it.

        model: any object with a .predict() method (XGBoost, sklearn, etc.)

        Action classes (expand as needed):
            "monitor"          — danger low, keep watching
            "alert"            — danger rising, notify
            "activate_pump"    — danger high, deploy water
            "cut_circuit"      — electric fire detected
            "evacuate"         — danger critical
        """
        features = [self.to_feature_vector()]   # model expects 2D input
        result = model.predict(features)
        self.predicted_action = str(result[0])
        return self.predicted_action

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"FireEvent("
            f"label={self.fire_label!r}, "
            f"danger={self.danger_level:.3f}, "
            f"growth={self.growth_rate:.4f}/s, "
            f"ratio={self.frame_area_ratio:.3f}, "
            f"action={self.predicted_action!r}, "
            f"t={self.timestamp.strftime('%H:%M:%S')})"
        )

