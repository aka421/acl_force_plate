"""TCP server for streaming Wii Balance Board force data as JSON.

# file: pi/board_server.py
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import socket
import struct
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ForceReading:
    """Single force reading from the board."""

    timestamp: float
    top_left: float
    top_right: float
    bottom_left: float
    bottom_right: float

    def to_json_line(self) -> bytes:
        """Serialize as newline-delimited JSON for easy socket framing."""
        payload = {
            "timestamp": self.timestamp,
            "top_left": self.top_left,
            "top_right": self.top_right,
            "bottom_left": self.bottom_left,
            "bottom_right": self.bottom_right,
        }
        return (json.dumps(payload) + "\n").encode("utf-8")


class SimulatedBoard:
    """Simulation fallback so the full pipeline can be tested without hardware."""

    def __init__(self) -> None:
        self._phase = 0.0

    def connect(self) -> None:
        logging.info("Using simulated board readings.")

    def read_forces(self) -> ForceReading:
        self._phase += 0.08
        base = 12.0 + 2.0 * (1 + random.uniform(-0.15, 0.15))
        sway = 2.0 * random.uniform(-1.0, 1.0)
        return ForceReading(
            timestamp=time.time(),
            top_left=base + sway,
            top_right=base - sway,
            bottom_left=base + 0.5 * sway,
            bottom_right=base - 0.5 * sway,
        )


class WiiBalanceBoard:
    """Minimal Bluetooth reader using Linux L2CAP sockets.

    Note: This is a prototype implementation using the board's raw sensor bytes.
    For clinical use, add full calibration parsing and validation.
    """

    CTRL_PSM = 0x11
    DATA_PSM = 0x13

    def __init__(self, mac_address: str) -> None:
        self.mac_address = mac_address
        self.ctrl_sock: Optional[socket.socket] = None
        self.data_sock: Optional[socket.socket] = None

    def connect(self) -> None:
        logging.info("Connecting to Wii Balance Board at %s", self.mac_address)
        self.ctrl_sock = socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP
        )
        self.data_sock = socket.socket(
            socket.AF_BLUETOOTH, socket.SOCK_SEQPACKET, socket.BTPROTO_L2CAP
        )

        self.ctrl_sock.connect((self.mac_address, self.CTRL_PSM))
        self.data_sock.connect((self.mac_address, self.DATA_PSM))
        self.data_sock.settimeout(2.0)

        # Request extension reporting mode for balance-board force packets.
        self._write_control(b"\x12\x04\x32")
        logging.info("Bluetooth connection established.")

    def _write_control(self, payload: bytes) -> None:
        if not self.ctrl_sock:
            raise RuntimeError("Control socket not connected")
        self.ctrl_sock.send(payload)

    def _raw_to_force(self, raw_value: int) -> float:
        # Placeholder conversion from raw ADC-like value to kg-force estimate.
        return max(0.0, (raw_value - 2000) / 100.0)

    def read_forces(self) -> ForceReading:
        if not self.data_sock:
            raise RuntimeError("Data socket not connected")

        packet = self.data_sock.recv(64)
        # Typical extension packet for balance board starts with 0xA1 0x32.
        if len(packet) < 10 or packet[1] != 0x32:
            raise RuntimeError(f"Unexpected packet format: {packet!r}")

        # Sensor byte ordering in 0x32 reports.
        tl_raw, tr_raw, bl_raw, br_raw = struct.unpack(">HHHH", packet[2:10]
        )

        return ForceReading(
            timestamp=time.time(),
            top_left=self._raw_to_force(tl_raw),
            top_right=self._raw_to_force(tr_raw),
            bottom_left=self._raw_to_force(bl_raw),
            bottom_right=self._raw_to_force(br_raw),
        )


class BoardServer:
    """TCP server that streams newline-delimited JSON force readings."""

    def __init__(
        self,
        host: str,
        port: int,
        board,
        sample_rate_hz: float = 25.0,
    ) -> None:
        self.host = host
        self.port = port
        self.board = board
        self.sample_period = 1.0 / sample_rate_hz
        self._shutdown = threading.Event()

    def run(self) -> None:
        """Run forever, accepting clients and streaming data."""
        self.board.connect()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_sock.bind((self.host, self.port))
            server_sock.listen(1)
            logging.info("Server listening on %s:%d", self.host, self.port)

            while not self._shutdown.is_set():
                client, addr = server_sock.accept()
                logging.info("Client connected: %s:%s", *addr)
                with client:
                    try:
                        self._stream_to_client(client)
                    except (BrokenPipeError, ConnectionResetError, OSError) as exc:
                        logging.warning("Client disconnected: %s", exc)

    def _stream_to_client(self, client: socket.socket) -> None:
        while not self._shutdown.is_set():
            reading = self.board.read_forces()
            client.sendall(reading.to_json_line())
            time.sleep(self.sample_period)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wii Balance Board TCP JSON server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8765, help="TCP port")
    parser.add_argument(
        "--mac",
        default=None,
        help="Wii Balance Board MAC address (if omitted, simulation mode is used)",
    )
    parser.add_argument("--rate", type=float, default=25.0, help="Sample rate (Hz)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    board = WiiBalanceBoard(args.mac) if args.mac else SimulatedBoard()
    server = BoardServer(host=args.host, port=args.port, board=board, sample_rate_hz=args.rate)
    server.run()


if __name__ == "__main__":
    main()
