# ACL Force Plate Prototype

Minimal end-to-end prototype for streaming Wii Balance Board sensor data from a Raspberry Pi to a laptop for processing and visualization.

## Project structure

```text
acl_force_plate/
├── pi/
│   └── board_server.py
├── laptop/
│   ├── client_visualizer.py
│   └── processing.py
└── README.md
```

## Requirements

- Python 3.10+
- `numpy`
- `matplotlib`

Install dependencies on both devices:

```bash
pip install numpy matplotlib
```

## 1) Run Raspberry Pi server

On the Raspberry Pi (or any Linux machine):

```bash
cd pi
python board_server.py --host 0.0.0.0 --port 8765 --mac AA:BB:CC:DD:EE:FF
```

- Replace `AA:BB:CC:DD:EE:FF` with your Wii Balance Board MAC address.
- If `--mac` is omitted, the server runs in **simulation mode** so you can test networking and plotting without hardware.

Simulation example:

```bash
python board_server.py --host 0.0.0.0 --port 8765
```

The server streams newline-delimited JSON messages, for example:

```json
{"timestamp": 1710000000.23, "top_left": 12.3, "top_right": 11.8, "bottom_left": 12.0, "bottom_right": 11.9}
```

## 2) Run laptop client visualizer

On the laptop:

```bash
cd laptop
python client_visualizer.py --host <RASPBERRY_PI_IP> --port 8765
```

The client will:

- Connect to the server
- Parse JSON messages
- Compute:
  - `left_force = top_left + bottom_left`
  - `right_force = top_right + bottom_right`
  - `total_force = left_force + right_force`
- Plot in real-time:
  - `total_force vs time`
  - `left_force vs right_force`

## 3) Processing helpers (`laptop/processing.py`)

- `compute_forces(data)` → `(left_force, right_force, total_force)`
- `compute_symmetry(left_force, right_force)` → symmetry percentage (`100%` is perfectly balanced)

## Example terminal output

```text
Connecting to 192.168.1.24:8765...
Connected.
t=   4.72s | total=  52.01 | left=  26.93 right=  25.08 | symmetry= 96.44%
```

If the socket drops, the client retries automatically every 2 seconds.
