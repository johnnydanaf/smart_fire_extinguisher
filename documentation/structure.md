# Fire Extinguisher AI - Project Structure
Overview
This document outlines the architecture for a self-improving fire detection system that combines YOLO computer vision with sensor data to assess fire danger and train its own decision-making model over time.

## Core Components
Component	Purpose	Location
YOLO Model	Detects fire types, smoke, humans in camera feed	Trained offline, deployed to Pi
FireInstance	Data object capturing one moment of observation	Runs on Pi
CSV Logger	Stores FireInstance data for training	SD card / cloud
Danger Model	ML model that learns from CSV data	Trained offline, deployed to Pi

### Diagram 1: FireInstance Class Structure

┌─────────────────────────────────────────────────────────────┐
│                     FireInstance                            │
├─────────────────────────────────────────────────────────────┤
│  Properties                                                 │
│  ├── timestamp: datetime                                    │
│  ├── fire_type: str (candle, kitchen, electrical, etc.)    │
│  ├── bounding_box: (x, y, width, height)                    │
│  ├── bounding_box_area: float                               │
│  ├── growth_rate: float                                     │
│  ├── heat_matrix: list[int] (4x4 = 16 values)              │
│  ├── smoke_detected: bool                                   │
│  ├── human_present: bool                                    │
│  ├── danger_score: float (0.0 - 1.0)                       │
│  └── verified: bool (for future feedback)                  │
├─────────────────────────────────────────────────────────────┤
│  Methods                                                    │
│  ├── calculate_danger_score() → float                       │
│  ├── append_to_csv(filepath) → None                         │
│  └── to_dict() → dict                                       │
└─────────────────────────────────────────────────────────────┘

## Code Snippet:

python
class FireInstance:
    def __init__(self, fire_type, bbox, heat_matrix, smoke, human):
        self.timestamp = datetime.now()
        self.fire_type = fire_type
        self.bounding_box = bbox
        self.bounding_box_area = bbox[2] * bbox[3]
        self.heat_matrix = heat_matrix
        self.smoke_detected = smoke
        self.human_present = human
        self.danger_score = self.calculate_danger_score()
    
    def calculate_danger_score(self):
        # Simple formula: fire type weight + area factor + human presence
        type_weights = {"candle": 0.1, "kitchen": 0.7, "electrical": 0.9}
        area_factor = min(1.0, self.bounding_box_area / 10000)
        human_penalty = 0.5 if self.human_present else 0
        return min(1.0, type_weights.get(self.fire_type, 0.5) + area_factor + human_penalty)
    
    def append_to_csv(self, filepath):
        import csv
        with open(filepath, 'a') as f:
            writer = csv.DictWriter(f, fieldnames=self.to_dict().keys())
            writer.writerow(self.to_dict())
### Diagram 2: Training & Deployment Workflow

┌─────────────────────────────────────────────────────────────────────────────┐
│                         PHASE 1: INITIAL TRAINING                          │
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │  Fire Images │    │  YOLO CLI    │    │  fire_model │                  │
│  │  (datasets)  │───▶│  model.train │───▶│    .pt      │                  │
│  └──────────────┘    └──────────────┘    └──────────────┘                  │
│                              │                                             │
│                              ▼                                             │
│                    ┌─────────────────────┐                                 │
│                    │ Export to .rpk for  │                                 │
│                    │    AI Pi Camera     │                                 │
│                    └─────────────────────┘                                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ Copy to Pi
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PHASE 2: DEPLOYMENT & COLLECTION                      │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        RASPBERRY PI                                  │  │
│  │                                                                       │  │
│  │  ┌─────────┐    ┌─────────┐    ┌─────────────┐    ┌──────────────┐  │  │
│  │  │AI Pi Cam│───▶│  YOLO   │───▶│ FireInstance│───▶│   fire_data  │  │  │
│  │  │         │    │ Model   │    │   Object    │    │    .csv      │  │  │
│  │  └─────────┘    └─────────┘    └─────────────┘    └──────────────┘  │  │
│  │       │              │               │                   │           │  │
│  │       │              │               │                   │           │  │
│  │  ┌────▼────┐    ┌────▼────┐    ┌────▼────┐              │           │  │
│  │  │ Heat    │    │ Smoke   │    │ Danger  │              │           │  │
│  │  │ Matrix  │    │ Sensor  │    │ Formula │              │           │  │
│  │  └─────────┘    └─────────┘    └─────────┘              │           │  │
│  │                                                          │           │  │
│  └──────────────────────────────────────────────────────────┼───────────┘  │
│                                                            │              │
│                                                            ▼              │
│                                          ┌─────────────────────────────┐  │
│                                          │   CSV file grows over time │  │
│                                          │   (training data for       │  │
│                                          │    danger model)           │  │
│                                          └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        │ Upload periodically
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PHASE 3: MODEL IMPROVEMENT (OFFLINE)                    │
│                                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                  │
│  │  fire_data   │    │   Danger     │    │  danger_     │                  │
│  │    .csv      │───▶│   Model      │───▶│  model.pkl   │                  │
│  │ (thousands   │    │  (scikit-    │    │              │                  │
│  │  of rows)    │    │   learn)     │    └──────────────┘                  │
│  └──────────────┘    └──────────────┘           │                          │
│                                                  │                          │
│                                                  ▼                          │
│                                        ┌─────────────────────┐             │
│                                        │ Deploy back to Pi   │             │
│                                        │ to replace simple   │             │
│                                        │ danger formula      │             │
│                                        └─────────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────┘

## Code Snippet: YOLO Training (Offline)
python
from ultralytics import YOLO

Load pretrained model
---
model = YOLO("yolo26n.pt")

Train on your fire dataset
---
model.train(
    data="fire_dataset.yaml",  # points to your images and labels
    epochs=100,
    imgsz=640,
    batch=16
)

Export for AI Camera
---
model.export(format="imx")  # creates .rpk file for Pi
Code Snippet: Detection Pipeline (On Pi)
python
from ultralytics import YOLO
from fire_instance import FireInstance
import csv

Load model
---
model = YOLO("fire_model.pt")

Capture frame
---
frame = camera.capture()

Run inference
---
results = model(frame)

For each detection
---
for detection in results[0].boxes:
    fire_type = results[0].names[int(detection.cls)]
    bbox = detection.xyxy[0].tolist()
    
    # Read sensors
    heat_matrix = heat_sensor.read()
    smoke = smoke_sensor.read()
    human = (fire_type == "person")  # YOLO also detects humans
    
    # Create FireInstance
    incident = FireInstance(fire_type, bbox, heat_matrix, smoke, human)
    
    # Log to CSV
    incident.append_to_csv("fire_data.csv")
    
    # Take action based on danger score
    if incident.danger_score > 0.8:
        activate_extinguisher()
Training Danger Model (Offline)
python
import pandas as pd
from sklearn.linear_model import LogisticRegression

Load collected data
---
df = pd.read_csv("fire_data.csv")

Features: fire_type_encoded, bbox_area, heat_avg, smoke, human
X = df[["fire_type_encoded", "bbox_area", "heat_avg", "smoke", "human"]]
y = df["was_dangerous"]  # manually labeled

Train
model = LogisticRegression()
model.fit(X, y)

## Save
import pickle
with open("danger_model.pkl", "wb") as f:
    pickle.dump(model, f)


## Project File Structure
text
fire_robot/
├── .github/workflows/lint.yml
├── documentation/
│   ├── automation.md
│   └── structure.md          ← this file
├── src/
│   ├── fire_detector/
│   │   ├── __init__.py
│   │   ├── camera.py
│   │   ├── detector.py
│   │   ├── fire_instance.py
│   │   └── models/
│   │       ├── fire_model.pt
│   │       └── danger_model.pkl
│   └── main.py
├── data/
│   └── fire_data.csv          ← collected training data
├── training/                   ← separate repo or folder
│   ├── datasets/
│   ├── train.py
│   └── export.py
├── Makefile
├── requirements.txt
└── Readme.md

## Summary Timeline
Phase	Task	Time
1	Train YOLO on fire datasets	2-5 hours
2	Build FireInstance class + CSV logging	1 day
3	Deploy to Pi, collect data	Ongoing
4	Train danger model from CSV	1 hour
5	Deploy danger model to Pi	30 min
Next Steps
Find/download fire datasets (candles, kitchen fires, smoke)

Train YOLO on your laptop or Google Colab

Export model to .pt format

Build FireInstance class with CSV logging

Test with webcam before deploying to Pi

