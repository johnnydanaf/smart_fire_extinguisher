# Fire Detection and Response System — Architecture

**Version:** 0.1 (research prototype)  
**Status:** Architecture phase — implementation pending  
**Author:** Maya Fakih  
**Database:** PostgreSQL (preferred) or MySQL — decision pending based on deployment constraints

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [System Pipeline](#2-system-pipeline)
3. [SystemOrchestrator and SystemState](#3-systemorchestrator-and-systemstate)
4. [SENSE Layer](#4-sense-layer)
5. [SEE Layer](#5-see-layer)
6. [THINK Layer](#6-think-layer)
7. [ACT Layer](#7-act-layer)
8. [Database Schema](#8-database-schema)
9. [Configuration Reference](#9-configuration-reference)
10. [Integration Contracts](#10-integration-contracts)

---

## 1. System Overview

This system is a multi-layer intelligent fire detection and response platform designed for embedded deployment on a Raspberry Pi with attached sensors, camera module, and a 2-DOF robotic arm. It is capable of detecting fire using both physical sensors and computer vision, reasoning about the severity and growth rate of a detected event, and dispatching appropriate responses ranging from notification to physical suppression — all while continuously learning from human feedback to improve its decision-making over time.

The system is designed to be context-aware. Thresholds, actuator mappings, action spaces, and operating modes are all configurable through a single `config.json` file, allowing the same codebase to be deployed in a data centre (where any heat anomaly is critical) or a wildfire monitoring site (where much higher tolerances apply) without code changes.

The architecture is divided into four logical processing layers that run as independent operating system processes, coordinated through a shared state object managed by a `SystemOrchestrator`.

---

## 2. System Pipeline

The four layers form a left-to-right pipeline. Each layer produces a well-defined output that the next layer consumes. No layer reaches across layer boundaries except through these agreed contracts.

```
SENSE  ──►  SEE  ──►  THINK  ──►  ACT
```

| Layer | Color convention | Primary output |
|-------|-----------------|----------------|
| SENSE | Green | `SensorSnapshot` |
| SEE | Yellow | `VisionSnapshot` |
| THINK | Blue | `ThinkSnapshot` |
| ACT | Purple | DB row update + physical actuator commands |

### Top-level pipeline flowchart

![Top-level pipeline — SENSE to ACT](assets/flowchart_pipeline_overview.png)

> Note: This diagram shows the sequential boot order and hand-off points between layers. At runtime, all four layers operate concurrently as separate processes. The hand-offs happen through queues and shared state, not direct function calls.

---

## 3. SystemOrchestrator and SystemState

### 3.1 Role of the Orchestrator

The `SystemOrchestrator` is the entry point of the entire system. It is responsible for:

- Building the `SystemState` shared object at boot
- Instantiating all four layer components and passing them a reference to `SystemState`
- Calling `start()` on each component, which causes each to spawn its own operating system process
- Accepting mode change requests from the website and writing them to `SystemState`
- Shutting down all processes gracefully on system exit

The orchestrator does not manage the internal logic of any layer. It is a boot manager and a mode switcher. Each layer is self-managing: it reads `SystemState` in its own loop and decides independently whether to activate or deactivate based on the fields it watches.

### 3.2 SystemState — the shared blackboard

`SystemState` is a managed shared object (using `multiprocessing.Manager().dict()`) that all processes can read and write. It is not a message queue — it is a live snapshot of the world as each layer currently sees it.

A strict ownership rule applies: each field in `SystemState` has exactly one writer. No two processes write to the same field. This eliminates the need for mutexes and makes the concurrency model simple and deadlock-free.

| Field | Type | Written by | Read by |
|-------|------|-----------|---------|
| `sensor_triggered` | bool | SensorFuser | VisionFuser, ArmController, ThinkEngine |
| `sensor_readings` | Dict[str, float] | SensorFuser | ThinkEngine |
| `active_faults` | List[str] | SensorFuser | NotificationService |
| `heat_matrix_hotspot` | Tuple[float, float] | SensorFuser | ArmController |
| `fire_detected` | bool | VisionFuser | ThinkEngine, ActEngine |
| `fire_area_ratio` | float | VisionFuser | ThinkEngine |
| `camera_active` | bool | VisionFuser | SystemOrchestrator |
| `arm_angles` | List[float] | ArmController | ActEngine |
| `arm_locked` | bool | ActEngine | ArmController |
| `danger_level` | int | ThinkEngine | ActEngine |
| `recommended_action` | str | ThinkEngine | ActEngine |
| `latest_think_snapshot_id` | int | ThinkEngine | ActEngine |
| `system_mode` | str | SystemOrchestrator | ActEngine, all ActMode subclasses |
| `suppression_active` | bool | ActEngine | ArmController |
| `alarm_active` | bool | ActEngine | NotificationService |
| `system_running` | bool | SystemOrchestrator | all layers |

### 3.3 Process activation rules

Each layer watches its own relevant `SystemState` fields and activates or deactivates its internal work accordingly. The orchestrator does not need to tell them what to do.

| Process | Activates when | Deactivates when |
|---------|---------------|-----------------|
| SensorFuser | always on from boot | system shutdown |
| VisionFuser | `sensor_triggered = True` | `sensor_triggered = False` |
| ArmController | `sensor_triggered = True` | `sensor_triggered = False` |
| ThinkEngine | `fire_detected = True` | `fire_detected = False` |
| ActEngine | `danger_level >= config.threshold` | `danger_level < threshold` for `clear_delay_s` |

### 3.4 Orchestrator flowchart

![SystemOrchestrator — boot and process lifecycle](assets/flowchart_orchestrator.png)

> This diagram is pending — will be added once the orchestrator design is finalised.

### 3.5 SystemOrchestrator class

```
SystemOrchestrator
  fields:
    state: SystemState
    sensor_fuser: SensorFuser
    vision_fuser: VisionFuser
    think_engine: ThinkEngine
    act_engine: ActEngine
    notification_service: NotificationService
    _processes: List[Process]

  methods:
    __init__(config_path: str) → None
    start() → None
    stop() → None
    set_mode(mode: str) → None
```

---

## 4. SENSE Layer

The SENSE layer is responsible for reading all physical sensors, validating their readings, detecting threshold crossings, and emitting `SensorSnapshot` objects to a queue for downstream consumption. It runs continuously from system boot and is the first layer to detect any environmental anomaly.

### 4.1 Flowchart

![SENSE layer — process flowchart](assets/flowchart_sense.png)

### 4.2 UML class diagram

![SENSE layer — UML class diagram](assets/uml_sense.png)

### 4.3 Design principles

Every sensor type (ADC, I2C, UART, GPIO) inherits from a common abstract base class `Sensor`. This means the `SensorFuser` never needs to know what kind of sensor it is working with — it calls `poll()` on each one and they all behave identically from the outside.

`SensorParser` reads `config.json` at startup and constructs the correct concrete sensor subclass for each entry. This is the only place in the codebase where sensor types are branched on. After construction, all sensors are treated polymorphically.

Each sensor runs in its own operating system process, polling at the configured interval. The `SensorFuser` collects readings across all sensors and evaluates whether any threshold has been crossed. If one has, it assembles a `SensorSnapshot` and writes `sensor_triggered = True` to `SystemState`, which wakes the SEE layer.

### 4.4 Fault handling

When a sensor produces an invalid reading (outside its configured `valid_min` / `valid_max` range, or a hardware read failure), the following sequence executes:

1. The sensor retries up to `max_retries` times (configured per sensor in `config.json`)
2. On each retry failure, the fault counter increments
3. If retries are exhausted, the sensor sets `fault = True` and removes itself from the active pool
4. `NotificationService` is called immediately — email to admin, popup notification on website, persistent entry in the notification tab
5. `SensorFuser` continues operating with the remaining healthy sensors
6. The admin can re-enable the sensor from the website once the hardware issue is resolved

The system is designed to be tolerant of individual sensor failures because multiple sensor types are used in combination. The fire detection logic still functions correctly with a subset of sensors active.

### 4.5 Class definitions

**Sensor (ABC)**
```
fields:
  name: str
  id: int
  unit: str
  interface: str
  raw_min: float
  raw_max: float
  physical_min: float
  physical_max: float
  threshold_physical: float
  threshold_normalized: float
  enabled: bool
  active: bool
  latest_raw: float
  latest_physical: float
  triggered: bool
  retry_count: int
  max_retries: int
  valid_min: float
  valid_max: float
  fault: bool

methods:
  read() → float                       [abstract]
  to_physical() → float
  to_normalized() → float
  threshold_hit() → bool
  is_valid(value: float) → bool
  handle_fault() → None
  poll() → None
  run_thread(interval: int) → None
  stop() → None
```

**ADCSensor(Sensor)**
```
fields:  pin: int, ads_gain: int
methods: read() → float
         reads ADS1115 on self.pin, returns raw ADC value
```

**I2CSensor(Sensor)**
```
fields:  address: str, i2c_bus: int
methods: read() → float
         reads I2C device at self.address
```

**UARTSensor(Sensor)**
```
fields:  path: str, baudrate: int
methods: read() → float
         reads serial device at self.path
```

**GPIOSensor(Sensor)**
```
fields:  pin: int, pull: str
methods: read() → float
         reads GPIO pin state, returns 0.0 or 1.0
```

**SensorFuser**
```
fields:
  sensors: List[Sensor]
  interval_idle_ms: int
  interval_active_ms: int
  _threads: List[Thread]
  _monitor_thread: Thread
  _running: bool

methods:
  __init__(config_path: str) → None
  start() → None
  stop() → None
  evaluate() → Tuple[bool, List[Sensor]]
  snapshot() → SensorSnapshot
  _monitor_loop() → None
  emit_trigger(snapshot: SensorSnapshot) → None
  wake_see() → None
```

**SensorSnapshot (dataclass)**
```
fields:
  timestamp: float
  readings: Dict[str, float]
  normalized: Dict[str, float]
  triggered_sensors: List[str]
  disabled_sensors: List[str]
```

**SensorParser**
```
fields:  config_path: str
methods:
  load() → List[Sensor]
  save(sensors: List[Sensor]) → None
  disable(name: str) → None
  _build_sensor(entry: dict) → Sensor
```

### 4.6 Relationships

```
SensorParser     ── uses once at init ──►  Sensor objects (factory)
SensorFuser      ──◆ owns ──────────────►  List[Sensor]
SensorFuser      ──◆ uses ──────────────►  SensorParser (at init only)
SensorFuser      ── creates ────────────►  SensorSnapshot
ADCSensor        ── inherits ───────────►  Sensor (ABC)
I2CSensor        ── inherits ───────────►  Sensor (ABC)
UARTSensor       ── inherits ───────────►  Sensor (ABC)
GPIOSensor       ── inherits ───────────►  Sensor (ABC)
```

### 4.7 Config reference (SENSE section)

```json
"sensors": {
  "smoke": {
    "enabled": true,
    "active": true,
    "interface": "adc",
    "pin": 0,
    "raw_min": 0,
    "raw_max": 4095,
    "physical_min": -20,
    "physical_max": 150,
    "threshold_physical": 300,
    "unit": "ppm",
    "valid_min": 0,
    "valid_max": 1000,
    "max_retries": 3
  }
},
"system": {
  "polling_interval_idle_ms": 10000,
  "polling_interval_active_ms": 1000,
  "max_gap_seconds": 20,
  "max_gap_seconds_fallback": 60,
  "rolling_window_n": 5
}
```

---

## 5. SEE Layer

The SEE layer is responsible for all computer vision processing. It is powered off when sensors are below threshold and activates explicitly when `SensorFuser` writes `sensor_triggered = True` to `SystemState`. The camera and all vision models are loaded only when needed, which reduces power consumption and extends hardware lifespan.

The IMX500 camera module performs inference on-chip using pre-loaded `.rpk` model packages. Two models run in parallel on each captured frame: a YOLO-based fire detector and a scene classifier for background awareness.

### 5.1 Flowchart

![SEE layer — process flowchart](assets/flowchart_see.png)

### 5.2 UML class diagram

![SEE layer — UML class diagram](assets/uml_see.png)

### 5.3 Design principles

`FireDetector` and `SceneClassifier` both inherit from `VisionModel(ABC)`, which defines the `load()` interface. This means both models are interchangeable as far as `VisionFuser` is concerned — new model types can be introduced without changing the fuser.

`VisionFuser` owns the camera, both models, and the output queue. It runs a continuous capture loop while active, feeding each frame through both models in parallel, and assembling the results into a `VisionSnapshot`.

The `human_near_fire` field on `VisionSnapshot` is derived, not directly from a model. It is computed by checking whether any detection in `raw_detections` has a label in the configured `human_labels` list while `fire_detected` is also true.

### 5.4 Class definitions

**VisionModel (ABC)**
```
fields:  model_rpk: str, conf_threshold: float
methods: load() → None  [abstract]
```

**FireDetector(VisionModel)**
```
methods:
  load() → None
  parse_detections() → List[Detection]
```

**SceneClassifier(VisionModel)**
```
fields:
  _labels: dict
  _embeddings: dict

methods:
  load() → None
  parse_scene() → Tuple[str, float]
  _build_embeddings(scene_labels: List[str]) → dict
    runs once at startup, never at inference time
```

**IMX500Camera**
```
fields:
  enabled: bool
  active: bool
  resolution: Tuple[int, int]
  fps: int
  _stream: Any

methods:
  start() → None      powers on, loads .rpk packages to chip
  stop() → None       powers off completely
  parse_fire_detections() → List[Detection]
  parse_scene_result() → Tuple[str, float]
```

**Detection (dataclass)**
```
fields:
  label: str
  confidence: float
  bbox: Tuple[int, int, int, int]    x, y, w, h
  area_ratio: float
```

**VisionSnapshot (dataclass)**
```
fields:
  timestamp: float
  fire_detected: bool
  fire_count: int
  fire_area_ratio: float
  fire_confidence: float
  scene_label: str
  scene_confidence: float
  human_near_fire: bool              derived field
  raw_detections: List[Detection]
```

**VisionFuser**
```
fields:
  _camera: IMX500Camera
  _fire_detector: FireDetector
  _scene_classifier: SceneClassifier
  _labels: dict
  _running: bool
  _queue: Queue[VisionSnapshot]

methods:
  __init__(config_path: str) → None
  start() → None
  stop() → None
  snapshot() → VisionSnapshot
  _capture_loop() → None
  emit_trigger(snapshot: VisionSnapshot) → None
```

### 5.5 Relationships

```
VisionModel (ABC)  ◄── inherits ──  FireDetector
VisionModel (ABC)  ◄── inherits ──  SceneClassifier
VisionFuser        ──◆ owns ──────► IMX500Camera
VisionFuser        ──◆ owns ──────► FireDetector
VisionFuser        ──◆ owns ──────► SceneClassifier
VisionFuser        ── creates ───►  VisionSnapshot
FireDetector       ── creates ───►  Detection
VisionSnapshot     ── contains ──►  List[Detection]
config.json        ── configures ►  VisionFuser (at init)
config.json        ── configures ►  FireDetector (model path, threshold)
config.json        ── configures ►  SceneClassifier (model path, threshold)
labels.json        ── read by ───►  VisionFuser, SceneClassifier
```

### 5.6 Config reference (SEE section)

```json
"vision": {
  "camera": {
    "enabled": true,
    "active": false,
    "resolution": [640, 480],
    "fps": 30
  },
  "models": {
    "fire": {
      "rpk": "models/fire_yolo.rpk",
      "conf_threshold": 0.5
    },
    "scene": {
      "rpk": "models/scene_mobilenet.rpk",
      "conf_threshold": 0.4
    }
  },
  "labels": "configs/labels.json"
}
```

**labels.json**
```json
{
  "scene_labels": ["classroom", "hospital", "kitchen", "warehouse",
                   "office", "server_room", "corridor", "parking_garage"],
  "human_labels": ["person", "child", "crowd"]
}
```

---

## 6. THINK Layer

The THINK layer is the analytical core of the system. It receives aligned `SensorSnapshot` and `VisionSnapshot` pairs, computes derived time-series metrics across a contiguous event chain retrieved from the database, assembles a `ThinkSnapshot`, logs it, runs the machine learning model to produce a danger assessment, and emits the result to the ACT layer.

THINK always executes the same pipeline regardless of operating mode. The mode branching happens in ACT. THINK's only job is to reason about the world accurately and completely.

### 6.1 Flowchart

![THINK layer — process flowchart](assets/flowchart_think.png)

### 6.2 UML class diagram

![THINK layer — UML class diagram](assets/uml_think.png)

### 6.3 Timestamp alignment

THINK receives `SensorSnapshot` and `VisionSnapshot` from their respective queues. Before processing, it checks whether the timestamps of the two snapshots are within `max_gap_ms` of each other (configured in `config.json`). If the gap is too large, the older snapshot is dropped and the next one is pulled from that queue. Anything older than the chosen pair is discarded from RAM immediately to prevent memory growth. Once an aligned pair is found, processing proceeds.

### 6.4 Event chain calculation — ThinkLogs

The most important computation in THINK is the event chain analysis performed by `ThinkLogs`. Rather than reasoning only about the current snapshot in isolation, THINK looks back through the database and collects all recent snapshots that belong to the same continuous event — defined as snapshots where the time gap between consecutive entries does not exceed `max_gap_ms`.

For example, if snapshots arrive at timestamps 1.0, 0.9, 0.8, 0.7, 0.6, 0.2 (seconds ago) and `max_gap_ms` is 150ms, the chain includes 1.0 through 0.6 and stops — the gap between 0.6 and 0.2 exceeds the threshold, meaning they belong to separate events.

For this event chain, `ThinkLogs` calculates the following for each sensor reading and each YOLO output field:

- **Average** across the chain
- **Variance** across the chain
- **Growth rate** (first derivative) — how fast the value is changing
- **Acceleration** (second derivative) — how fast the growth rate itself is changing

For the YOLO outputs, growth rate and acceleration are computed over `bbox_area` (width × height as a ratio of frame area), `fire_area_ratio`, and `fire_confidence`. These time-series derivatives are what allow the model to distinguish a stable candle from an accelerating fire — two events that may look identical in a single snapshot but are completely different across a chain.

### 6.5 Machine learning architecture

The model is designed to be swappable behind a single `BaseModel` interface. Three phases are planned:

**Phase 1 — RuleEngine** (day one, no training data required)  
A hand-tuned weighted scoring function across the feature vector. Weights and thresholds are stored in a JSON file and are editable from the website by an admin. This phase allows the system to be deployed and useful immediately.

**Phase 2 — XGBoostModel** (once approximately 200 validated rows exist in the database)  
An `XGBClassifier` trained on validated `ThinkSnapshot` rows. Predicts both `danger_level` (1–5) and `recommended_action` as separate classification heads. Handles mixed numeric and encoded categorical features well, produces interpretable feature importance scores, and runs fast on embedded hardware.

**Phase 3 — NeuralModel** (if XGBoost cannot capture temporal patterns sufficiently)  
A small LSTM or 1D-CNN operating over the chain sequence directly, capturing the shape of how readings evolve over time rather than just their current statistics.

All three implement the same `BaseModel(ABC)` interface. Swapping from phase 1 to phase 2 is done by changing one line in `config.json` and triggering a retrain from the website.

### 6.6 Feature vector

`FeatureBuilder` takes a `ThinkSnapshot` plus its event chain and flattens everything into a single dictionary of floats that the model can consume directly. The `ThinkSnapshot` stores human-readable structured data. The feature vector is the model's flat numeric representation of the same information.

For each sensor, the feature vector includes: `latest_normalized`, `avg_over_chain`, `variance_over_chain`, `growth_rate`, `acceleration`.

For vision outputs: `fire_detected` (0/1), `fire_count`, `fire_area_ratio`, `fire_confidence`, `bbox_area_ratio`, `bbox_growth_rate`, `bbox_acceleration`, `scene_label` (encoded to int), `human_near_fire` (0/1).

For derived fields: `escalation_trend` (encoded), `estimated_origin_zone` (encoded), `chain_length`.

Available actuators are also encoded as binary features so the model knows what tools it has when recommending an action. It will never recommend water suppression if that feature is always zero in training data.

### 6.7 ThinkSnapshot structure

`ThinkSnapshot` is a single dataclass that accumulates data from all four layers over the lifecycle of one event. It starts with SENSE and SEE inputs, gets THINK-derived fields added when assembled, gets ACT fields added when action is taken, gets outcome fields added when the fire is resolved, and gets training fields added if a human validates it.

```
--- INPUTS ---
timestamp: float
sensor_snapshot: SensorSnapshot
vision_snapshot: VisionSnapshot

--- THINK DERIVED ---
spread_rate: float
escalation_trend: str              WORSENING | STABLE | IMPROVING
estimated_origin_zone: str         TOPLEFT | TOPRIGHT | CENTER | etc.
danger_level: int                  1 through 5
danger_label: str
recommended_action: str

--- ACT OUTPUT (written by ACT after execution) ---
act_mode: str | None
act_executed: str | None
act_timestamp: float | None

--- OUTCOME (written after event resolves) ---
outcome_observed: bool
outcome_label: str | None          CONTAINED | ESCALATED | FALSE_ALARM
outcome_source: str | None         HUMAN | SENSOR_CLEARANCE | TIMEOUT

--- TRAINING (written by human in training mode) ---
validated: bool
true_danger_level: int | None
true_action: str | None
model_accuracy: float | None
```

One row in the database corresponds to one `ThinkSnapshot`. THINK creates it and writes the first set of fields. ACT updates the same row with execution details. The outcome is written when the event resolves. Human validators write the training fields. This makes the database the single source of truth for the complete lifecycle of every detected event.

### 6.8 Danger level scale

| Level | Label | Meaning |
|-------|-------|---------|
| 1 | MINIMAL | Logged only, no notification |
| 2 | LOW | Single notification, 15-minute reminder |
| 3 | MODERATE | Notification, ACT enters monitoring state |
| 4 | HIGH | Immediate notification, ACT executes response |
| 5 | CRITICAL | Continuous notification, full ACT response |

The threshold at which ACT activates physical actuators is configurable in `config.json` (`danger_threshold_to_act`). In a data centre this might be set to 2. In a wildfire monitoring context it might be set to 4.

### 6.9 Class definitions

**ThinkEngine**
```
fields:
  _model: BaseModel
  _model_accuracy: float | None
  _history: List[ThinkSnapshot]
  _db: ThinkDatabase
  _feature_builder: FeatureBuilder

methods:
  __init__(config_path: str) → None
  evaluate(s: SensorSnapshot, v: VisionSnapshot) → ThinkSnapshot
  _build_features(snap: ThinkSnapshot) → Dict
  update_accuracy(id: int, true_label: int) → None
  retrain() → None
  save_model(path: str) → None
  load_model(path: str) → None
```

**ThinkDatabase**
```
fields:
  _conn: Connection
  _logs: ThinkLogs

methods:
  __init__(db_path: str) → None
  log_event(snap: ThinkSnapshot) → int
  update_act(id: int, mode: str, action: str) → None
  update_outcome(id: int, label: str, source: str) → None
  validate_event(id: int, true_danger: int, true_action: str) → None
  get_training_data() → List[dict]       SELECT WHERE validated = 1
  get_act_training_data() → List[dict]   SELECT WHERE outcome_label IS NOT NULL
  export_csv(path: str) → None
  clear_logs() → None
```

**ThinkLogs**
```
fields:
  _db: ThinkDatabase
  max_gap_ms: int
  rolling_window_n: int

methods:
  __init__(db: ThinkDatabase, config: dict) → None
  get_chain(timestamp: float, gap_ms: int) → List[ThinkSnapshot]
  calc_avg(chain: List[ThinkSnapshot]) → Dict[str, float]
  calc_variance(chain: List[ThinkSnapshot]) → Dict[str, float]
  calc_growth_rate(chain: List[ThinkSnapshot]) → Dict[str, float]
  calc_acceleration(chain: List[ThinkSnapshot]) → Dict[str, float]
```

**FeatureBuilder**
```
fields:
  sensor_cols: List[str]
  vision_cols: List[str]
  encoding_map: Dict[str, int]

methods:
  __init__(config: dict) → None
  build(snap: ThinkSnapshot, chain: List[ThinkSnapshot]) → Dict[str, float]
  encode_categorical(value: str, col: str) → int
  to_dataframe(features: Dict) → DataFrame
```

**BaseModel (ABC)**
```
fields:
  _importance_cache: Dict[str, float] | None

methods:
  fit(X: DataFrame, y: Series) → None            [abstract]
  predict(features: Dict) → Tuple[int, str]      [abstract]
  save(path: str) → None                         [abstract]
  load(path: str) → None                         [abstract]
  feature_importance() → Dict[str, float]        [abstract]
```

**RuleEngine(BaseModel)**
```
fields:
  weights: Dict[str, float]
  thresholds: Dict[str, float]
  _importance_cache: Dict[str, float] | None

methods:
  fit(X, y) → None              no-op, rules are hand-tuned
  predict(features) → Tuple[int, str]
  save(path: str) → None        writes weights + thresholds to JSON
  load(path: str) → None        reads weights + thresholds from JSON
  feature_importance() → Dict   returns weights dict as importance proxy
  _score(features: Dict) → float
```

**XGBoostModel(BaseModel)**
```
fields:
  _clf: XGBClassifier
  n_estimators: int
  max_depth: int
  learning_rate: float
  subsample: float
  colsample_bytree: float
  _importance_cache: Dict[str, float] | None

methods:
  fit(X, y) → None              trains on validated DB rows
  predict(features) → Tuple[int, str]
  save(path: str) → None        XGBoost native .json format
  load(path: str) → None
  feature_importance() → Dict   get_booster().get_fscore(), cached after fit
```

**NeuralModel(BaseModel)**
```
fields:
  _model: Any
  sequence_len: int
  hidden_size: int
  learning_rate: float
  _importance_cache: Dict[str, float] | None

methods:
  fit(X, y) → None              trains LSTM/1D-CNN on chain sequence data
  predict(features) → Tuple[int, str]
  save(path: str) → None        .pt or .h5 file
  load(path: str) → None
  feature_importance() → Dict   permutation importance, cached after fit
```

### 6.10 THINK relationships

```
ThinkEngine      ──◆ owns ──────►  ThinkDatabase
ThinkEngine      ──◆ owns ──────►  FeatureBuilder
ThinkEngine      ── uses ────────►  BaseModel (swappable)
ThinkEngine      ── creates ────►  ThinkSnapshot
ThinkDatabase    ──◆ owns ──────►  ThinkLogs
ThinkDatabase    ── logs ────────►  ThinkSnapshot (updates same row)
ThinkLogs        ── queries ────►  ThinkDatabase
BaseModel (ABC)  ◄── inherits ──   RuleEngine
BaseModel (ABC)  ◄── inherits ──   XGBoostModel
BaseModel (ABC)  ◄── inherits ──   NeuralModel
ThinkSnapshot    ── contains ───►  SensorSnapshot
ThinkSnapshot    ── contains ───►  VisionSnapshot
```

---

## 7. ACT Layer

The ACT layer receives a `ThinkSnapshot` from THINK and executes an appropriate physical and notification response. It is the only layer that interacts with external hardware (GPIO pins, servos, network actuators) and external parties (admin and user notifications, website).

The operating mode (autopilot, copilot, surveillance, training) is a runtime-configurable parameter that controls the degree of human involvement in the response. All modes produce the same notifications. They differ only in whether physical actuators fire automatically, wait for human confirmation, or do not fire at all.

### 7.1 Orchestrator flowchart

![SystemOrchestrator and process lifecycle](assets/flowchart_orchestrator.png)

> Pending — will be added once the orchestrator design is finalised.

### 7.2 ACT engine flowchart

![ACT layer — ActEngine internal flow](assets/flowchart_act.png)

### 7.3 UML class diagram

![ACT layer — UML class diagram](assets/uml_act.png)

### 7.4 Operating modes

**Autopilot**  
The model's `recommended_action` is executed immediately without waiting for human input. A report email is sent after execution. This mode is appropriate for unattended deployments where the response hardware is trusted to act correctly.

**Copilot**  
The proposed action is displayed on the website dashboard and the system waits for human confirmation for up to `copilot_timeout_s` seconds. If the human confirms, the actuators fire. If rejected or timed out, the event is logged with the outcome recorded. This mode is appropriate when a human is available and monitoring the situation.

**Surveillance**  
No actuators fire under any circumstances. The system sends a notification email with a link to the live dashboard where the human can observe sensor readings, camera feed, and the model's assessment. The human takes any action manually. This mode is appropriate for ambiguous situations — a candle near a curtain, someone smoking in a garage, a stove that is intentionally hot.

**Training**  
After the full THINK pipeline runs, the system displays its prediction (danger level, recommended action, current model accuracy) on the website. The human then provides the true danger level and the correct action plan. These are written back to the database row with `validated = True`. The fire is allowed to progress naturally so the model can learn from growth rate patterns in real conditions.

### 7.5 2-DOF arm and IK

The robotic arm carries the camera, heat matrix sensor, and water pump at its tip. When the camera is active, the arm runs a continuous tracking loop, reading `heat_matrix_hotspot` from `SystemState` and moving to keep the highest-temperature region centred in its field of view. This provides the YOLO model with consistently framed fire detections.

When ACT decides to suppress, it sets `arm_locked = True` in `SystemState`. The `ArmController` process reads this flag and freezes the arm on its current target. The pump then fires. When suppression ends, `arm_locked = False` and tracking resumes.

The inverse kinematics solver (`DHSolver`) uses Denavit-Hartenberg parameters loaded from `config.json` to compute joint angles from a physical target coordinate. The 2-DOF geometric solution is implemented directly. For configurations with more than 2 degrees of freedom, `DHSolver.solve()` raises `NotImplementedError` — the architecture is designed for future extension but only the 2-DOF case is handled in this version.

**DH parameters per joint:**

| Parameter | Meaning |
|-----------|---------|
| alpha | Twist angle between consecutive z-axes (around x-axis) |
| a | Link length (distance along x-axis) |
| d | Link offset (distance along z-axis) |
| theta | Joint angle (what IK solves for) |

**2-DOF geometric solution:**
```
cos(theta2) = (x^2 + y^2 - L1^2 - L2^2) / (2 * L1 * L2)
theta2 = atan2(±sqrt(1 - cos^2(theta2)), cos(theta2))
theta1 = atan2(y, x) - atan2(L2*sin(theta2), L1 + L2*cos(theta2))
```

Two solutions exist (elbow up / elbow down). The solver selects the one within the joint's configured `theta_min` / `theta_max` limits.

### 7.6 Notification service

`NotificationService` is a shared utility that lives in `common/` and is used by both the SENSE layer (sensor fault notifications) and the ACT layer (fire event notifications). It is not owned by either layer. Both receive a reference to the same instance at construction time from the `SystemOrchestrator`.

Notifications take three forms: email (with dynamic content and action links), website popup (ephemeral, dismissable), and notification tab entry (persistent, remains visible until cleared by the admin).

The email structure changes based on `danger_level` and `escalation_trend`. A level 2 steady email looks very different from a level 4 accelerating email. Action links in the email redirect the recipient to the website where they can trigger suppress, monitor, or ignore responses directly.

### 7.7 Class definitions

**ActMode (ABC)**
```
methods:
  run(snapshot: ThinkSnapshot,
      actuators: List[Actuator],
      notifier: NotificationService) → None    [abstract]
```

**AutopilotMode(ActMode)**
```
methods:
  run(snapshot, actuators, notifier) → None
    arm already aimed by ArmController, fires pump immediately,
    triggers alarm, sends report email, logs to DB
```

**CopilotMode(ActMode)**
```
fields:  timeout_s: int
methods:
  run(snapshot, actuators, notifier) → None
    sends proposed action to website, waits up to timeout_s,
    executes on confirmation, logs rejection or timeout
```

**SurveillanceMode(ActMode)**
```
methods:
  run(snapshot, actuators, notifier) → None
    no actuators, sends dashboard link, human acts manually
```

**TrainingMode(ActMode)**
```
fields:  _db: ThinkDatabase
methods:
  run(snapshot, actuators, notifier) → None
    shows prediction on website, waits for human feedback,
    writes true_danger + true_action to DB row, sets validated = True
```

**ActEngine**
```
fields:
  _state: SystemState
  _mode: ActMode
  _actuators: List[Actuator]
  _notifier: NotificationService
  _db: ThinkDatabase
  _running: bool
  _processes: List[Process]

methods:
  __init__(config_path: str, state: SystemState,
           db: ThinkDatabase,
           notifier: NotificationService) → None
  start() → None
  stop() → None
  set_mode(mode: ActMode) → None
  _act_loop() → None
  _should_run() → bool
```

**Actuator (ABC)**
```
fields:
  id: int, name: str, enabled: bool, active: bool,
  fault: bool, retry_count: int, max_retries: int

methods:
  activate() → None      [abstract]
  deactivate() → None    [abstract]
  is_healthy() → bool    [abstract]
  handle_fault() → None
  run_process() → None
  stop() → None
```

**ArmController(Actuator)**
```
fields:
  dof: int
  segments: List[DHSegment]
  heat_matrix_offset: Tuple[float, float, float]
  camera_offset: Tuple[float, float, float]
  pump_offset: Tuple[float, float, float]
  _solver: DHSolver
  _current_angles: List[float]
  _target: Tuple[float, float] | None
  _locked: bool

methods:
  activate() → None
  deactivate() → None
  is_healthy() → bool
  aim(target: Tuple[float, float]) → None
  lock() → None
  unlock() → None
  _tracking_loop() → None
  _move_to(angles: List[float]) → None
  run_process() → None
```

**PumpActuator(Actuator)**
```
fields:  pin: int, max_duration_s: int, _start_time: float | None
methods:
  activate() → None
  deactivate() → None
  is_healthy() → bool
  _safety_cutoff() → None    auto-deactivates if running > max_duration_s
```

**AlarmActuator(Actuator)**
```
fields:  pin: int, duration_s: int
methods:
  activate() → None
  deactivate() → None
  is_healthy() → bool
```

**DHSegment (dataclass)**
```
fields:
  id: int
  alpha: float      twist angle around x-axis
  a: float          link length along x-axis
  d: float          offset along z-axis
  theta_min: float  joint limit, degrees
  theta_max: float  joint limit, degrees
```

**DHSolver**
```
fields:
  segments: List[DHSegment]
  dof: int

methods:
  __init__(segments: List[DHSegment], dof: int) → None
  solve(target: Tuple[float, float]) → List[float]
    raises NotImplementedError if dof > 2
  forward_kinematics(thetas: List[float]) → Tuple[float, float]
    works for any dof
  _solve_2dof(target) → List[float]
    geometric cosine rule, picks solution within joint limits
  _build_transform(seg: DHSegment, theta: float) → Matrix
    4x4 homogeneous transform from DH params
```

**ActuatorParser**
```
fields:  config_path: str
methods:
  __init__(config_path: str) → None
  load() → List[Actuator]
  _build_actuator(entry: dict) → Actuator
  _build_arm(entry: dict) → ArmController
```

**NotificationService (common/)**
```
fields:
  admin_email: str
  user_emails: List[str]
  smtp_config: dict
  dashboard_url: str

methods:
  notify_fault(sensor_name: str, fault_type: str) → None
  notify_fire(snapshot: ThinkSnapshot) → None
  notify_act(snapshot: ThinkSnapshot, action: str) → None
  push_popup(message: str, level: str) → None
  log_to_notification_tab(message: str, level: str) → None
```

### 7.8 ACT relationships

```
ActMode (ABC)    ◄── inherits ──  AutopilotMode
ActMode (ABC)    ◄── inherits ──  CopilotMode
ActMode (ABC)    ◄── inherits ──  SurveillanceMode
ActMode (ABC)    ◄── inherits ──  TrainingMode
ActEngine        ──◆ owns ──────► ActuatorController
ActEngine        ──◆ owns ──────► NotificationService
ActEngine        ── uses ────────► ActMode (swappable at runtime)
ActEngine        ── uses ────────► ThinkDatabase (updates rows)
ArmController    ──◆ owns ──────► DHSolver
DHSolver         ── uses ────────► List[DHSegment]
Actuator (ABC)   ◄── inherits ──  ArmController
Actuator (ABC)   ◄── inherits ──  PumpActuator
Actuator (ABC)   ◄── inherits ──  AlarmActuator
ActuatorParser   ── creates ────► List[Actuator] (factory at init)
```

### 7.9 Config reference (ACT section)

```json
"actuators": {
  "arm": {
    "enabled": true,
    "dof": 2,
    "segments": [
      { "id": 0, "alpha": 0.0, "a": 0.25, "d": 0.0,
        "theta_min": -90.0, "theta_max": 90.0 },
      { "id": 1, "alpha": 0.0, "a": 0.18, "d": 0.0,
        "theta_min": -120.0, "theta_max": 120.0 }
    ],
    "heat_matrix_offset": [0.0, 0.0, 0.02],
    "camera_offset": [0.0, 0.01, 0.02],
    "pump_offset": [0.0, 0.0, 0.03]
  },
  "outputs": [
    { "id": "water_valve", "name": "Water suppression",
      "type": "valve", "pin": 18, "enabled": true,
      "action_label": "water_suppress" },
    { "id": "chemical_valve", "name": "Chemical suppression",
      "type": "valve", "pin": 19, "enabled": false,
      "action_label": "chemical_suppress" },
    { "id": "alarm", "name": "Alarm buzzer",
      "type": "buzzer", "pin": 24, "enabled": true,
      "action_label": "alarm" }
  ]
},
"actions": {
  "available": [
    "monitor", "water_suppress", "chemical_suppress",
    "alarm", "call_fire_team", "evacuate"
  ],
  "poa_map": {
    "1": "monitor",
    "2": "monitor",
    "3": "alarm",
    "4": "water_suppress",
    "5": "evacuate"
  },
  "requires_actuator": {
    "water_suppress":    "water_valve",
    "chemical_suppress": "chemical_valve",
    "alarm":             "alarm",
    "call_fire_team":    null,
    "evacuate":          null,
    "monitor":           null
  }
},
"act": {
  "default_mode": "surveillance",
  "danger_threshold_to_act": 3,
  "clear_delay_s": 10,
  "suppress_timeout_s": 30,
  "copilot_timeout_s": 60
},
"notification": {
  "admin_email": "admin@system.com",
  "user_emails": ["user1@system.com"],
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "smtp_user": "system@gmail.com",
  "smtp_password": "xxxx",
  "dashboard_url": "http://192.168.1.1:5000"
}
```

---

## 8. Database Schema

A single table holds the complete lifecycle of every event the system observes. THINK creates a row. ACT updates it. Outcome is written when the event resolves. Human validators write the training columns.

```sql
CREATE TABLE think_snapshots (
  id                       SERIAL PRIMARY KEY,
  timestamp                FLOAT NOT NULL,

  -- sensor inputs
  triggered_sensors        TEXT[],
  sensor_readings          JSONB,
  sensor_normalized        JSONB,

  -- vision inputs
  fire_detected            BOOLEAN,
  fire_count               INT,
  fire_area_ratio          FLOAT,
  fire_confidence          FLOAT,
  scene_label              TEXT,
  scene_confidence         FLOAT,
  human_near_fire          BOOLEAN,
  raw_detections           JSONB,

  -- think derived
  spread_rate              FLOAT,
  escalation_trend         TEXT,
  estimated_origin_zone    TEXT,
  danger_level             INT,
  danger_label             TEXT,
  recommended_action       TEXT,

  -- act output (written by ACT after execution)
  act_mode                 TEXT,
  act_executed             TEXT,
  act_timestamp            FLOAT,

  -- outcome (written when event resolves)
  outcome_observed         BOOLEAN DEFAULT FALSE,
  outcome_label            TEXT,
  outcome_source           TEXT,

  -- training (written by human validation)
  validated                BOOLEAN DEFAULT FALSE,
  true_danger_level        INT,
  true_action              TEXT,
  model_accuracy           FLOAT
);
```

Structured and frequently queried fields (timestamps, danger levels, validated flag) are plain columns. Nested flexible data (sensor readings dict, raw detections list) are stored as JSONB so the schema does not need to change when new sensor types are added.

**Admin controls (website):**
- Export all rows to CSV for offline training
- Clear logs after export
- View DB size, row count, last training date
- Trigger model retraining on validated rows
- Only admin users can trigger retraining

---

## 9. Configuration Reference

All system behaviour is controlled through a single `config.json` file at the project root. No hardcoded thresholds exist in the codebase.

Key design decisions that belong in config:

| Setting | Why it belongs in config |
|---------|--------------------------|
| `threshold_physical` per sensor | Different deployments have different sensitivity requirements |
| `danger_threshold_to_act` | A data centre acts at level 2; a wildfire site acts at level 4 |
| `max_gap_ms` for chain calculation | Controls what counts as "the same event" |
| `min_training_rows` | Threshold before XGBoost replaces RuleEngine |
| `poa_map` (danger level to action) | Operator decides the action plan for their context |
| `available` actions | Only actions with connected actuators should be available |
| `copilot_timeout_s` | Varies by deployment context and staffing |
| `clear_delay_s` | How long fire must be gone before system resets |

---

## 10. Integration Contracts

These are the data contracts between layers. Each person building a layer needs to produce the exact output described here so that downstream layers can consume it without modification.

### SENSE output contract

`SensorSnapshot` emitted to `Queue[SensorSnapshot]`:

```python
@dataclass
class SensorSnapshot:
    timestamp: float               # Unix timestamp, seconds
    readings: Dict[str, float]     # sensor_name → physical value
    normalized: Dict[str, float]   # sensor_name → 0.0–1.0
    triggered_sensors: List[str]   # names of sensors above threshold
    disabled_sensors: List[str]    # names of sensors currently faulted
```

### SEE output contract

`VisionSnapshot` emitted to `Queue[VisionSnapshot]`:

```python
@dataclass
class VisionSnapshot:
    timestamp: float
    fire_detected: bool
    fire_count: int
    fire_area_ratio: float         # bbox_area / frame_area
    fire_confidence: float         # highest confidence detection
    scene_label: str               # from labels.json scene_labels
    scene_confidence: float
    human_near_fire: bool          # derived: fire AND human label detected
    raw_detections: List[Detection]

@dataclass
class Detection:
    label: str
    confidence: float
    bbox: Tuple[int, int, int, int]   # x, y, w, h in pixels
    area_ratio: float
```

### THINK output contract

`ThinkSnapshot` emitted to `Queue[ThinkSnapshot]` (includes all fields, training fields are None until validated):

The full field list is defined in section 6.7.

### ACT → DB update contract

ACT calls `ThinkDatabase.update_act(id, mode, action)` and later `ThinkDatabase.update_outcome(id, label, source)` on the same row that THINK created. The `id` is read from `SystemState.latest_think_snapshot_id`.

---

*Last updated: April 2026*  
*Architecture version: 0.1 — research prototype*
