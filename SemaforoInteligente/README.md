# Smart Pedestrian Traffic Light (IoT)

Smart pedestrian crossing for a **divided boulevard** (two carriageways separated by a
central median). Pedestrians cross in **two stages**, using the median as a refuge, and
there are **two independent signals** (one per carriageway): while someone crosses
carriageway 1, carriageway 2 can stay green.

People are detected with **YOLOv4-tiny** (OpenCV-DNN, CPU, no torch), with **HOG** as a
fallback if the model is missing. For each carriageway the signal goes
**GREEN → AMBER → RED** and **holds red until that carriageway is actually clear** (never a
fixed time), with a minimum safe-clearance red.

**Automatic multi-camera setup:** on start it detects how many cameras are connected and
configures itself — 1 camera = full 5-zone view, 2 cameras = one per side, 3 cameras =
carriageway 1 / median / carriageway 2. It also runs without an Arduino (simulation mode).

## How to run

```bash
pip install opencv-python numpy pillow pyserial
python descargar_modelo.py        # downloads YOLOv4-tiny into modelos/ (optional; HOG otherwise)
python semaforo_inteligente.py            # simulation mode (no Arduino)
python semaforo_inteligente.py COM6       # with the Arduino on COM6
python semaforo_inteligente.py COM6 1,2   # force camera indexes
```

Upload `firmware_semaforo/firmware_semaforo.ino` to an Arduino Uno to drive the physical
LEDs, buttons and buzzer.

## Requirements

- Python 3.8+ with `opencv-python`, `numpy`, `pillow`, `pyserial`.
- A webcam (1–3 cameras supported).
- Optional: an Arduino Uno for the physical signals.

## Files

| File | Description |
|---|---|
| [`semaforo_inteligente.py`](semaforo_inteligente.py) | Vision platform (detection, two state machines, Tkinter GUI) |
| [`descargar_modelo.py`](descargar_modelo.py) | Downloads the YOLOv4-tiny model into `modelos/` |
| [`firmware_semaforo/firmware_semaforo.ino`](firmware_semaforo/firmware_semaforo.ino) | Arduino firmware (two carriageways, buttons, buzzer) |

The YOLOv4-tiny weights (~24 MB) are **not** stored in the repository; run
`descargar_modelo.py` to fetch them.
