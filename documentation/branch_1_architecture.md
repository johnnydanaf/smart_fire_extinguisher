LEVEL 1 — The 4-Layer Cognitive Architecture
text
SENSE LAYER ──────► SEE LAYER ──────► THINK LAYER ──────► ACT LAYER
     │                  │                  │                  │
     │                  │                  │                  │
   "What do          "What do          "What should       "Do it"
   I sense?"         I see?"           I decide?"
     │                  │                  │                  │
     ▼                  ▼                  ▼                  ▼
  Sensors +         Camera +           FireRisk(t)        Servos +
  Thresholds        Thermal            Fusion Model       Solenoid
LEVEL 2 — SENSE Layer Breakdown
text
SENSE
  │
  ├── CONFIG ──────────► What sensors exist? What are their thresholds?
  │
  ├── READ ────────────► Get raw values from hardware continuously
  │
  └── EVALUATE ────────► Compare readings against thresholds → TRIGGER?
LEVEL 3 — CONFIG Sub-layer Breakdown
text
CONFIG
  │
  ├── config.json ──────► Persistent storage (human-readable, writable from code)
  │
  └── SensorManager ────► Loads JSON, creates Sensor objects, handles errors, disables failed sensors
CONFIG Tree Detail
text
config.json
  │
  ├── sensors {
  │     ├── smoke {
  │     │     ├── enabled: bool
  │     │     ├── interface: "adc"
  │     │     ├── address_pin: 0
  │     │     ├── raw_min: 0
  │     │     ├── raw_max: 4095
  │     │     ├── threshold: 300
  │     │     └── unit: "ppm"
  │     │   }
  │     ├── heat_max { ... }
  │     ├── lidar_z { ... }
  │     └── ... }
  │
  └── system {
        ├── polling_interval_idle_ms: 10000
        └── polling_interval_active_ms: 1000
      }
SensorManager Class Diagram
text
┌─────────────────────────────────────────────────────────────┐
│                      SensorManager                          │
├─────────────────────────────────────────────────────────────┤
│ - config_path: str                                          │
│ - config: dict                                              │
├─────────────────────────────────────────────────────────────┤
│ + __init__(config_path)                                     │
│ + load_config() → dict                                      │
│ + create_sensors() → List[Sensor]                           │
│ + disable_sensor(name)                                      │
│ + save_config()                                             │
│ + reload() → List[Sensor]                                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ creates
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        Sensor                               │
├─────────────────────────────────────────────────────────────┤
│ - name: str                                                 │
│ - unit: str                                                 │
│ - interface: str (adc/i2c/uart/gpio)                        │
│ - address_pin: str/int                                      │
│ - raw_min: float                                            │
│ - raw_max: float                                            │
│ - threshold_physical: float                                 │
│ - threshold_normalized: float (computed)                    │
├─────────────────────────────────────────────────────────────┤
│ + read_raw() → float                                        │
│ + read_physical() → float                                   │
│ + read_normalized() → float                                 │
│ + is_triggered() → bool                                     │
└─────────────────────────────────────────────────────────────┘
LEVEL 3 — READ Sub-layer Breakdown
text
READ
  │
  ├── Continuous Monitoring Loop ──► Runs every N seconds (idle: 10s, active: 1s)
  │
  ├── Hardware Interfaces ─────────► ADC (ADS1115), I2C, UART, GPIO
  │
  └── Sensor Objects ──────────────► Each knows how to read its own hardware
READ Tree Detail
text
Continuous Monitoring
  │
  ├── Polling Loop ──► while True:
  │     │
  │     ├── for sensor in sensors:
  │     │     ├── sensor.read_raw()
  │     │     ├── sensor.read_physical()
  │     │     └── sensor.read_normalized()
  │     │
  │     └── wait(interval)
  │
  └── Hardware Abstraction
        │
        ├── ADC Interface ──► smoke, gas, PM2.5
        ├── I2C Interface ──► thermal (MLX90640), particle (MAX30105)
        ├── UART Interface ─► LiDAR (TFMini), servos (ST3215)
        └── GPIO Interface ─► flow sensor (YF-B5)
LEVEL 3 — EVALUATE Sub-layer Breakdown
text
EVALUATE
  │
  ├── SensorFuser ──────► Polls all sensors, collects readings
  │
  ├── Threshold Check ──► Compares physical readings against thresholds
  │
  └── Trigger Decision ─► Returns (triggered_bool, triggered_sensors)
SensorFuser Class Diagram
text
┌─────────────────────────────────────────────────────────────┐
│                       SensorFuser                           │
├─────────────────────────────────────────────────────────────┤
│ - sensors: List[Sensor]                                     │
│ - interval_idle_ms: int                                     │
│ - interval_active_ms: int                                   │
│ - currently_triggered: bool                                 │
├─────────────────────────────────────────────────────────────┤
│ + __init__(sensors, interval_idle, interval_active)         │
│ + evaluate() → (bool, List[Sensor])                         │
│ + start_monitoring() ──────────────────────────────────────►│
│   │                                                         │
│   │   while True:                                           │
│   │       triggered, triggered_list = self.evaluate()       │
│   │       if triggered:                                     │
│   │           emit("TRIGGER", triggered_list)               │
│   │           wait(interval_active_ms)                      │
│   │       else:                                             │
│   │           wait(interval_idle_ms)                        │
│   │                                                         │
└─────────────────────────────────────────────────────────────┘
LEVEL 4 — Complete SENSE Layer Class Diagram
text
                              ┌─────────────────┐
                              │   config.json   │
                              └────────┬────────┘
                                       │ reads
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SensorManager                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ - config_path: str                                                   │   │
│  │ - config: dict                                                       │   │
│  │ + load_config() → dict                                               │   │
│  │ + create_sensors() → List[Sensor]                                    │   │
│  │ + disable_sensor(name)                                               │   │
│  │ + save_config()                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       │ creates
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                             Sensor (generic)                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ - name: str                                                          │   │
│  │ - unit: str                                                          │   │
│  │ - interface: str                                                     │   │
│  │ - address_pin: str/int                                               │   │
│  │ - raw_min: float                                                     │   │
│  │ - raw_max: float                                                     │   │
│  │ - threshold_physical: float                                          │   │
│  │ - threshold_normalized: float                                        │   │
│  │ + read_raw() → float                                                 │   │
│  │ + read_physical() → float                                            │   │
│  │ + read_normalized() → float                                          │   │
│  │ + is_triggered() → bool                                              │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       │ stored in
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            SensorFuser                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ - sensors: List[Sensor]                                              │   │
│  │ - interval_idle_ms: int                                              │   │
│  │ - interval_active_ms: int                                            │   │
│  │ - currently_triggered: bool                                          │   │
│  │ + evaluate() → (bool, List[Sensor])                                  │   │
│  │ + start_monitoring() ──────────────────────────────────────────────► │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       │ emits
                                       ▼
                              ┌─────────────────┐
                              │   TRIGGER event  │
                              │   to SEE layer   │
                              └─────────────────┘
LEVEL 5 — The Monitoring Loop (Inside SensorFuser.start_monitoring())
text
START MONITORING
      │
      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MONITORING LOOP                            │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │                                                         │   │
│   │   while True:                                           │   │
│   │       │                                                 │   │
│   │       ├──► triggered = False                            │   │
│   │       ├──► triggered_list = []                          │   │
│   │       │                                                 │   │
│   │       ├──► for each sensor in sensors:                  │   │
│   │       │       raw = sensor.read_raw()                   │   │
│   │       │       physical = sensor.read_physical()         │   │
│   │       │       if sensor.is_triggered(physical):         │   │
│   │       │           triggered = True                      │   │
│   │       │           triggered_list.append(sensor)         │   │
│   │       │                                                 │   │
│   │       ├──► if triggered:                                │   │
│   │       │       emit("TRIGGER", triggered_list)           │   │
│   │       │       wait(interval_active_ms)  # fast poll     │   │
│   │       │                                                 │   │
│   │       └──► else:                                        │   │
│   │               wait(interval_idle_ms)    # slow poll     │   │
│   │                                                         │   │
│   └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
The Complete Flow from Config to Trigger
text
1. START
      │
2. SensorManager.load_config() ──► reads config.json
      │
3. SensorManager.create_sensors() ──► creates List[Sensor]
      │
4. SensorFuser.__init__(sensors) ──► stores sensors
      │
5. SensorFuser.start_monitoring() ──► begins polling loop
      │
6. Each iteration:
      │
      ├── Sensor.read_raw() ──► hardware call
      ├── Sensor.read_physical() ──► raw → physical units
      ├── Sensor.is_triggered() ──► physical >= threshold?
      │
      └── If any triggered:
            emit("TRIGGER", triggered_sensors) ──► to SEE layer