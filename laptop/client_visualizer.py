"""TCP client that receives force data and visualizes it live.

# file: laptop/client_visualizer.py
"""

from __future__ import annotations

import argparse
import json
import socket
import time
from collections import deque
from typing import Deque, Dict, Iterable, Tuple

import matplotlib.pyplot as plt
import numpy as np

from processing import compute_forces, compute_symmetry


def json_lines_from_socket(sock: socket.socket) -> Iterable[Dict[str, float]]:
    """Yield decoded JSON objects from a newline-delimited stream."""
    buffer = ""
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            raise ConnectionResetError("Socket closed by server")
        buffer += chunk.decode("utf-8")
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


class RealtimePlot:
    """Manage two live matplotlib plots for the prototype."""

    def __init__(self, max_points: int = 300):
        self.max_points = max_points
        self.t: Deque[float] = deque(maxlen=max_points)
        self.total_force: Deque[float] = deque(maxlen=max_points)
        self.left_force: Deque[float] = deque(maxlen=max_points)
        self.right_force: Deque[float] = deque(maxlen=max_points)

        plt.ion()
        self.fig, (self.ax_total, self.ax_scatter) = plt.subplots(1, 2, figsize=(12, 5))

    def update(self, t: float, left: float, right: float, total: float) -> None:
        self.t.append(t)
        self.left_force.append(left)
        self.right_force.append(right)
        self.total_force.append(total)

        self.ax_total.cla()
        self.ax_total.plot(np.array(self.t), np.array(self.total_force), color="tab:blue")
        self.ax_total.set_title("Total Force vs Time")
        self.ax_total.set_xlabel("Time (s)")
        self.ax_total.set_ylabel("Force (a.u.)")
        self.ax_total.grid(True, alpha=0.3)

        self.ax_scatter.cla()
        self.ax_scatter.scatter(np.array(self.left_force), np.array(self.right_force), s=12, alpha=0.7)
        self.ax_scatter.set_title("Left Force vs Right Force")
        self.ax_scatter.set_xlabel("Left Force (a.u.)")
        self.ax_scatter.set_ylabel("Right Force (a.u.)")
        self.ax_scatter.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.pause(0.001)


def run_client(host: str, port: int) -> None:
    """Connect to the Pi server and keep plotting readings in real time."""
    plot = RealtimePlot()

    while True:
        try:
            print(f"Connecting to {host}:{port}...")
            with socket.create_connection((host, port), timeout=5.0) as sock:
                sock.settimeout(None)
                print("Connected.")
                t0 = time.time()

                for payload in json_lines_from_socket(sock):
                    left, right, total = compute_forces(payload)
                    symmetry = compute_symmetry(left, right)
                    elapsed = payload.get("timestamp", time.time()) - t0
                    plot.update(elapsed, left, right, total)
                    print(
                        f"t={elapsed:7.2f}s | total={total:7.2f} | "
                        f"left={left:7.2f} right={right:7.2f} | symmetry={symmetry:6.2f}%",
                        end="\r",
                    )

        except (ConnectionRefusedError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            print(f"\nConnection issue: {exc}. Retrying in 2 seconds...")
            time.sleep(2.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Force-plate client visualizer")
    parser.add_argument("--host", default="127.0.0.1", help="Raspberry Pi IP / hostname")
    parser.add_argument("--port", type=int, default=8765, help="Raspberry Pi TCP port")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_client(args.host, args.port)
