"""
Modbus Poll - Python Replica
A comprehensive Modbus master simulator replicating Modbus Poll functionality.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import time
import json
import struct
import queue
import serial.tools.list_ports
from datetime import datetime
from typing import Optional, List, Dict, Any

try:
    from pymodbus.client import ModbusSerialClient, ModbusTcpClient
    from pymodbus.exceptions import ModbusException, ConnectionException
    from pymodbus.pdu import ExceptionResponse
    PYMODBUS_AVAILABLE = True
except ImportError:
    PYMODBUS_AVAILABLE = False
    print("WARNING: pymodbus not installed. Run: pip install pymodbus pyserial")


# ─────────────────────────── Constants ───────────────────────────

APP_TITLE = "Modbus Poll"
VERSION = "1.0.0"

FUNCTION_CODES = {
    1:  "FC01 Read Coils",
    2:  "FC02 Read Discrete Inputs",
    3:  "FC03 Read Holding Registers",
    4:  "FC04 Read Input Registers",
    5:  "FC05 Write Single Coil",
    6:  "FC06 Write Single Register",
    15: "FC15 Write Multiple Coils",
    16: "FC16 Write Multiple Registers",
}

DISPLAY_FORMATS = [
    "Signed Int (16-bit)",
    "Unsigned Int (16-bit)",
    "Hex",
    "Binary",
    "Float 32-bit ABCD",
    "Float 32-bit CDAB",
    "Float 32-bit BADC",
    "Float 32-bit DCBA",
    "Double 64-bit",
    "ASCII String",
]

BAUD_RATES = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
PARITY_OPTIONS = {"None": "N", "Even": "E", "Odd": "O", "Mark": "M", "Space": "S"}
STOP_BITS = [1, 1.5, 2]
DATA_BITS = [7, 8]

MODBUS_EXCEPTIONS = {
    1:  "Illegal Function",
    2:  "Illegal Data Address",
    3:  "Illegal Data Value",
    4:  "Server Device Failure",
    5:  "Acknowledge",
    6:  "Server Device Busy",
    8:  "Memory Parity Error",
    10: "Gateway Path Unavailable",
    11: "Gateway Target Device Failed to Respond",
}

COLOR_OK    = "#00aa00"
COLOR_ERROR = "#cc0000"
COLOR_WARN  = "#cc8800"
COLOR_BG    = "#f0f0f0"
COLOR_GRID  = "#ffffff"
COLOR_SEL   = "#cce8ff"


# ─────────────────────────── Data Models ─────────────────────────

class ConnectionConfig:
    def __init__(self):
        self.conn_type   = "TCP"          # TCP, UDP, RTU, ASCII
        self.host        = "127.0.0.1"
        self.port        = 502
        self.timeout     = 1.0
        self.com_port    = "COM1"
        self.baudrate    = 9600
        self.data_bits   = 8
        self.parity      = "N"
        self.stop_bits   = 1
        self.rts_control = False
        self.dtr_control = False

    def to_dict(self):
        return self.__dict__.copy()

    def from_dict(self, d):
        self.__dict__.update(d)


class SlaveConfig:
    def __init__(self):
        self.slave_id      = 1
        self.function_code = 3
        self.start_address = 0
        self.quantity      = 10
        self.scan_rate     = 1000        # ms
        self.display_fmt   = "Signed Int (16-bit)"
        self.address_base  = 0           # 0 = 0-based, 1 = 1-based (40001 style)
        self.aliases: Dict[int, str] = {}

    def to_dict(self):
        return self.__dict__.copy()

    def from_dict(self, d):
        self.__dict__.update(d)


# ─────────────────────────── Helpers ─────────────────────────────

def format_value(raw: int, fmt: str, raw2: int = 0) -> str:
    """Convert a raw 16-bit integer to the chosen display format."""
    try:
        if fmt == "Signed Int (16-bit)":
            v = raw if raw < 32768 else raw - 65536
            return str(v)
        elif fmt == "Unsigned Int (16-bit)":
            return str(raw & 0xFFFF)
        elif fmt == "Hex":
            return f"0x{raw & 0xFFFF:04X}"
        elif fmt == "Binary":
            return f"{raw & 0xFFFF:016b}"
        elif fmt == "Float 32-bit ABCD":
            b = struct.pack(">HH", raw, raw2)
            return f"{struct.unpack('>f', b)[0]:.6g}"
        elif fmt == "Float 32-bit CDAB":
            b = struct.pack(">HH", raw2, raw)
            return f"{struct.unpack('>f', b)[0]:.6g}"
        elif fmt == "Float 32-bit BADC":
            b = struct.pack("<HH", raw, raw2)
            return f"{struct.unpack('<f', b)[0]:.6g}"
        elif fmt == "Float 32-bit DCBA":
            b = struct.pack("<HH", raw2, raw)
            return f"{struct.unpack('<f', b)[0]:.6g}"
        elif fmt == "Double 64-bit":
            return f"{raw:.6g}"
        elif fmt == "ASCII String":
            hi = (raw >> 8) & 0xFF
            lo = raw & 0xFF
            return "".join(chr(c) if 32 <= c < 127 else "." for c in (hi, lo))
        else:
            return str(raw)
    except Exception:
        return "ERR"


def addr_label(addr: int, base: int, fc: int) -> str:
    """Format address label based on address base setting."""
    if base == 1:
        offsets = {1: 0, 2: 10001, 3: 40001, 4: 30001, 5: 0, 6: 40001, 15: 0, 16: 40001}
        offset = offsets.get(fc, 40001)
        return str(offset + addr)
    return str(addr)


# ─────────────────────────── Modbus Engine ───────────────────────

class ModbusEngine:
    """Handles the actual Modbus communication in a background thread."""

    def __init__(self, log_callback, traffic_callback):
        self.log_cb     = log_callback
        self.traffic_cb = traffic_callback
        self.client     = None
        self.conn_cfg   = ConnectionConfig()
        self.connected  = False
        self._lock      = threading.Lock()
        self.tx_count   = 0
        self.rx_count   = 0
        self.err_count  = 0

    def connect(self, cfg: ConnectionConfig) -> bool:
        self.disconnect()
        self.conn_cfg = cfg
        try:
            if cfg.conn_type in ("TCP", "UDP"):
                self.client = ModbusTcpClient(
                    host=cfg.host,
                    port=cfg.port,
                    timeout=cfg.timeout,
                )
            else:  # RTU or ASCII
                method = "rtu" if cfg.conn_type == "RTU" else "ascii"
                self.client = ModbusSerialClient(
                    port=cfg.com_port,
                    baudrate=cfg.baudrate,
                    bytesize=cfg.data_bits,
                    parity=cfg.parity,
                    stopbits=cfg.stop_bits,
                    timeout=cfg.timeout,
                    method=method,
                )
            result = self.client.connect()
            self.connected = result
            if result:
                self.log_cb(f"Connected via {cfg.conn_type}")
            else:
                self.log_cb(f"Connection failed via {cfg.conn_type}")
            return result
        except Exception as e:
            self.log_cb(f"Connection error: {e}")
            self.connected = False
            return False

    def disconnect(self):
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
            self.client = None
        self.connected = False
        self.log_cb("Disconnected")

    def read_registers(self, slave_cfg: SlaveConfig):
        """
        Returns (values: list, error: str or None).
        values is list of raw int (or bool for coils).
        """
        if not self.connected or not self.client:
            return None, "Not connected"

        fc  = slave_cfg.function_code
        sid = slave_cfg.slave_id
        sa  = slave_cfg.start_address
        qty = slave_cfg.quantity

        with self._lock:
            try:
                self.tx_count += 1
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]

                if fc == 1:
                    rr = self.client.read_coils(sa, qty, slave=sid)
                elif fc == 2:
                    rr = self.client.read_discrete_inputs(sa, qty, slave=sid)
                elif fc == 3:
                    rr = self.client.read_holding_registers(sa, qty, slave=sid)
                elif fc == 4:
                    rr = self.client.read_input_registers(sa, qty, slave=sid)
                else:
                    return None, f"FC{fc:02d} not a read function"

                if rr.isError():
                    self.err_count += 1
                    exc_code = getattr(rr, "exception_code", 0)
                    msg = MODBUS_EXCEPTIONS.get(exc_code, f"Exception {exc_code}")
                    self.traffic_cb(ts, f"[TX] FC{fc:02d} Slave={sid} Addr={sa} Qty={qty}")
                    self.traffic_cb(ts, f"[RX] EXCEPTION: {msg}")
                    return None, msg

                self.rx_count += 1
                if fc in (1, 2):
                    vals = [int(b) for b in rr.bits[:qty]]
                else:
                    vals = list(rr.registers)

                hex_vals = " ".join(f"{v:04X}" for v in vals[:min(8, len(vals))])
                self.traffic_cb(ts, f"[TX] FC{fc:02d} Slave={sid} Addr={sa} Qty={qty}")
                self.traffic_cb(ts, f"[RX] {hex_vals}{'...' if len(vals) > 8 else ''}")
                return vals, None

            except ConnectionException as e:
                self.err_count += 1
                self.connected = False
                return None, f"Connection lost: {e}"
            except Exception as e:
                self.err_count += 1
                return None, str(e)

    def write_register(self, slave_id: int, address: int, value: int, fc: int = 6) -> Optional[str]:
        if not self.connected or not self.client:
            return "Not connected"
        with self._lock:
            try:
                self.tx_count += 1
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                if fc == 5:
                    rr = self.client.write_coil(address, bool(value), slave=slave_id)
                elif fc == 6:
                    rr = self.client.write_register(address, value, slave=slave_id)
                else:
                    return f"Use write_multiple for FC{fc}"

                if rr.isError():
                    self.err_count += 1
                    exc_code = getattr(rr, "exception_code", 0)
                    msg = MODBUS_EXCEPTIONS.get(exc_code, f"Exception {exc_code}")
                    self.traffic_cb(ts, f"[TX] FC{fc:02d} Write Slave={slave_id} Addr={address} Val={value}")
                    self.traffic_cb(ts, f"[RX] EXCEPTION: {msg}")
                    return msg

                self.rx_count += 1
                self.traffic_cb(ts, f"[TX] FC{fc:02d} Write Slave={slave_id} Addr={address} Val={value}")
                self.traffic_cb(ts, f"[RX] OK")
                return None
            except Exception as e:
                self.err_count += 1
                return str(e)

    def write_multiple(self, slave_id: int, address: int, values: list, fc: int = 16) -> Optional[str]:
        if not self.connected or not self.client:
            return "Not connected"
        with self._lock:
            try:
                self.tx_count += 1
                ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                if fc == 15:
                    rr = self.client.write_coils(address, [bool(v) for v in values], slave=slave_id)
                else:
                    rr = self.client.write_registers(address, values, slave=slave_id)

                if rr.isError():
                    self.err_count += 1
                    exc_code = getattr(rr, "exception_code", 0)
                    msg = MODBUS_EXCEPTIONS.get(exc_code, f"Exception {exc_code}")
                    self.traffic_cb(ts, f"[TX] FC{fc:02d} Write Multiple Slave={slave_id} Addr={address}")
                    self.traffic_cb(ts, f"[RX] EXCEPTION: {msg}")
                    return msg

                self.rx_count += 1
                self.traffic_cb(ts, f"[TX] FC{fc:02d} Write Multiple Slave={slave_id} Addr={address} Count={len(values)}")
                self.traffic_cb(ts, f"[RX] OK")
                return None
            except Exception as e:
                self.err_count += 1
                return str(e)


# ─────────────────────────── Dialogs ─────────────────────────────

class ConnectionDialog(tk.Toplevel):
    def __init__(self, parent, cfg: ConnectionConfig):
        super().__init__(parent)
        self.title("Connection Setup")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self.cfg = cfg
        self._build(cfg)
        self.transient(parent)
        self.wait_window()

    def _build(self, cfg):
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # ── TCP/UDP tab ──────────────────────────────────────────
        tcp_frame = ttk.Frame(nb)
        nb.add(tcp_frame, text="TCP / UDP")

        ttk.Label(tcp_frame, text="Connection Type:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.conn_type_var = tk.StringVar(value=cfg.conn_type)
        conn_cb = ttk.Combobox(tcp_frame, textvariable=self.conn_type_var,
                               values=["TCP", "UDP", "RTU", "ASCII"], state="readonly", width=12)
        conn_cb.grid(row=0, column=1, sticky="w", padx=8, pady=4)

        ttk.Label(tcp_frame, text="IP Address:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.host_var = tk.StringVar(value=cfg.host)
        ttk.Entry(tcp_frame, textvariable=self.host_var, width=20).grid(row=1, column=1, padx=8, pady=4)

        ttk.Label(tcp_frame, text="Port:").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        self.port_var = tk.IntVar(value=cfg.port)
        ttk.Spinbox(tcp_frame, textvariable=self.port_var, from_=1, to=65535, width=8).grid(row=2, column=1, padx=8, pady=4, sticky="w")

        ttk.Label(tcp_frame, text="Timeout (s):").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        self.timeout_var = tk.DoubleVar(value=cfg.timeout)
        ttk.Spinbox(tcp_frame, textvariable=self.timeout_var, from_=0.1, to=30.0,
                    increment=0.1, width=8, format="%.1f").grid(row=3, column=1, padx=8, pady=4, sticky="w")

        # ── Serial tab ───────────────────────────────────────────
        ser_frame = ttk.Frame(nb)
        nb.add(ser_frame, text="Serial (RTU/ASCII)")

        ports = [p.device for p in serial.tools.list_ports.comports()]
        if not ports:
            ports = ["COM1", "COM2", "COM3", "/dev/ttyS0", "/dev/ttyUSB0"]

        ttk.Label(ser_frame, text="COM Port:").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.com_var = tk.StringVar(value=cfg.com_port)
        ttk.Combobox(ser_frame, textvariable=self.com_var, values=ports, width=16).grid(row=0, column=1, padx=8, pady=4)

        ttk.Label(ser_frame, text="Baud Rate:").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        self.baud_var = tk.IntVar(value=cfg.baudrate)
        ttk.Combobox(ser_frame, textvariable=self.baud_var,
                     values=BAUD_RATES, state="readonly", width=10).grid(row=1, column=1, padx=8, pady=4, sticky="w")

        ttk.Label(ser_frame, text="Data Bits:").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        self.data_bits_var = tk.IntVar(value=cfg.data_bits)
        ttk.Combobox(ser_frame, textvariable=self.data_bits_var,
                     values=DATA_BITS, state="readonly", width=6).grid(row=2, column=1, padx=8, pady=4, sticky="w")

        ttk.Label(ser_frame, text="Parity:").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        parity_map_r = {v: k for k, v in PARITY_OPTIONS.items()}
        self.parity_var = tk.StringVar(value=parity_map_r.get(cfg.parity, "None"))
        ttk.Combobox(ser_frame, textvariable=self.parity_var,
                     values=list(PARITY_OPTIONS.keys()), state="readonly", width=10).grid(row=3, column=1, padx=8, pady=4, sticky="w")

        ttk.Label(ser_frame, text="Stop Bits:").grid(row=4, column=0, sticky="w", padx=8, pady=4)
        self.stop_bits_var = tk.DoubleVar(value=cfg.stop_bits)
        ttk.Combobox(ser_frame, textvariable=self.stop_bits_var,
                     values=STOP_BITS, state="readonly", width=6).grid(row=4, column=1, padx=8, pady=4, sticky="w")

        self.rts_var = tk.BooleanVar(value=cfg.rts_control)
        ttk.Checkbutton(ser_frame, text="RTS Control", variable=self.rts_var).grid(
            row=5, column=0, columnspan=2, sticky="w", padx=8, pady=4)

        self.dtr_var = tk.BooleanVar(value=cfg.dtr_control)
        ttk.Checkbutton(ser_frame, text="DTR Control", variable=self.dtr_var).grid(
            row=6, column=0, columnspan=2, sticky="w", padx=8, pady=4)

        # ── Buttons ──────────────────────────────────────────────
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=8, pady=8)
        ttk.Button(btn_frame, text="OK", width=10, command=self._ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="Cancel", width=10, command=self.destroy).pack(side=tk.RIGHT, padx=4)

    def _ok(self):
        cfg = ConnectionConfig()
        cfg.conn_type   = self.conn_type_var.get()
        cfg.host        = self.host_var.get().strip()
        cfg.port        = int(self.port_var.get())
        cfg.timeout     = float(self.timeout_var.get())
        cfg.com_port    = self.com_var.get()
        cfg.baudrate    = int(self.baud_var.get())
        cfg.data_bits   = int(self.data_bits_var.get())
        cfg.parity      = PARITY_OPTIONS.get(self.parity_var.get(), "N")
        cfg.stop_bits   = float(self.stop_bits_var.get())
        cfg.rts_control = self.rts_var.get()
        cfg.dtr_control = self.dtr_var.get()
        self.result = cfg
        self.destroy()


class ReadWriteDefinitionDialog(tk.Toplevel):
    def __init__(self, parent, slave_cfg: SlaveConfig):
        super().__init__(parent)
        self.title("Read / Write Definition")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self._build(slave_cfg)
        self.transient(parent)
        self.wait_window()

    def _build(self, cfg):
        f = ttk.Frame(self, padding=12)
        f.pack(fill=tk.BOTH, expand=True)

        rows = [
            ("Slave ID (1-247):",      "slave_id",      tk.IntVar,    cfg.slave_id),
            ("Function Code:",         "fc",             tk.StringVar, FUNCTION_CODES.get(cfg.function_code, "FC03 Read Holding Registers")),
            ("Starting Address:",      "start_addr",     tk.IntVar,    cfg.start_address),
            ("Quantity:",              "quantity",       tk.IntVar,    cfg.quantity),
            ("Scan Rate (ms):",        "scan_rate",      tk.IntVar,    cfg.scan_rate),
            ("Display Format:",        "display_fmt",    tk.StringVar, cfg.display_fmt),
            ("Address Display:",       "addr_base",      tk.StringVar, "0-based" if cfg.address_base == 0 else "1-based (40001)"),
        ]

        self._vars = {}
        for r, (label, key, vartype, val) in enumerate(rows):
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=3)
            var = vartype(value=val)
            self._vars[key] = var
            if key == "fc":
                w = ttk.Combobox(f, textvariable=var, values=list(FUNCTION_CODES.values()),
                                 state="readonly", width=30)
            elif key == "display_fmt":
                w = ttk.Combobox(f, textvariable=var, values=DISPLAY_FORMATS,
                                 state="readonly", width=30)
            elif key == "addr_base":
                w = ttk.Combobox(f, textvariable=var, values=["0-based", "1-based (40001)"],
                                 state="readonly", width=18)
            else:
                w = ttk.Spinbox(f, textvariable=var,
                                from_=1 if key == "slave_id" else 0,
                                to=247 if key == "slave_id" else 1000000,
                                width=14)
            w.grid(row=r, column=1, sticky="w", padx=8, pady=3)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=12, pady=8)
        ttk.Button(btn_frame, text="OK", width=10, command=self._ok).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="Cancel", width=10, command=self.destroy).pack(side=tk.RIGHT, padx=4)

    def _ok(self):
        cfg = SlaveConfig()
        cfg.slave_id      = int(self._vars["slave_id"].get())
        fc_str            = self._vars["fc"].get()
        cfg.function_code = next((k for k, v in FUNCTION_CODES.items() if v == fc_str), 3)
        cfg.start_address = int(self._vars["start_addr"].get())
        cfg.quantity      = int(self._vars["quantity"].get())
        cfg.scan_rate     = int(self._vars["scan_rate"].get())
        cfg.display_fmt   = self._vars["display_fmt"].get()
        cfg.address_base  = 0 if self._vars["addr_base"].get().startswith("0") else 1
        self.result = cfg
        self.destroy()


class WriteValueDialog(tk.Toplevel):
    def __init__(self, parent, address: int, current_value: str, fc: int):
        super().__init__(parent)
        self.title(f"Write Value - Address {address}")
        self.resizable(False, False)
        self.grab_set()
        self.result = None
        self.fc = fc

        f = ttk.Frame(self, padding=12)
        f.pack()

        ttk.Label(f, text=f"Address: {address}").grid(row=0, column=0, columnspan=2, sticky="w", pady=2)
        ttk.Label(f, text="Current Value:").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Label(f, text=current_value, foreground=COLOR_OK).grid(row=1, column=1, sticky="w", pady=2)
        ttk.Label(f, text="New Value:").grid(row=2, column=0, sticky="w", pady=2)
        self.val_var = tk.StringVar(value="0")
        ttk.Entry(f, textvariable=self.val_var, width=20).grid(row=2, column=1, pady=2)

        if fc in (1, 5):
            ttk.Label(f, text="(Use 0 or 1 for coil)").grid(row=3, column=0, columnspan=2, sticky="w")
        elif fc == 6:
            ttk.Label(f, text="(0–65535 decimal or 0x hex)").grid(row=3, column=0, columnspan=2, sticky="w")

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=12, pady=8)
        ttk.Button(btn_frame, text="Write", width=10, command=self._write).pack(side=tk.RIGHT, padx=4)
        ttk.Button(btn_frame, text="Cancel", width=10, command=self.destroy).pack(side=tk.RIGHT, padx=4)
        self.transient(parent)
        self.wait_window()

    def _write(self):
        raw = self.val_var.get().strip()
        try:
            if raw.lower().startswith("0x"):
                self.result = int(raw, 16)
            else:
                self.result = int(raw)
        except ValueError:
            messagebox.showerror("Error", "Invalid value. Enter a decimal or hex (0x…) integer.")
            return
        self.destroy()


# ─────────────────────────── Slave Window ────────────────────────

class SlaveWindow(tk.Toplevel):
    """An MDI-like child window representing one Modbus slave poll definition."""

    _instances = []

    def __init__(self, parent_app: "ModbusPollApp", slave_cfg: Optional[SlaveConfig] = None):
        super().__init__(parent_app.root)
        SlaveWindow._instances.append(self)
        self.app        = parent_app
        self.slave_cfg  = slave_cfg or SlaveConfig()
        self.values: List[Any]     = []
        self.errors: List[Optional[str]] = []
        self.polling    = False
        self._poll_thread = None
        self._stop_event  = threading.Event()
        self.filename   = None

        self._build_ui()
        self._update_title()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Position nicely
        count = len(SlaveWindow._instances)
        offset = (count - 1) * 24
        self.geometry(f"520x340+{60 + offset}+{60 + offset}")
        self.lift()

    # ── UI Construction ──────────────────────────────────────────

    def _build_ui(self):
        self.configure(bg=COLOR_BG)

        # Toolbar strip
        tb = tk.Frame(self, bg="#dcdcdc", relief=tk.RAISED, bd=1)
        tb.pack(fill=tk.X)
        tk.Label(tb, text="  Slave Window", bg="#dcdcdc", font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=4)

        # Status strip inside window
        self.win_status = tk.Label(self, text="Not polling", bg="#e8e8e8",
                                   anchor="w", relief=tk.SUNKEN, font=("Consolas", 8))
        self.win_status.pack(fill=tk.X, side=tk.BOTTOM)

        # Grid frame
        grid_frame = ttk.Frame(self)
        grid_frame.pack(fill=tk.BOTH, expand=True)

        cols = ("address", "alias", "value", "raw", "status")
        self.tree = ttk.Treeview(grid_frame, columns=cols, show="headings", selectmode="browse")
        self.tree.heading("address", text="Address")
        self.tree.heading("alias",   text="Alias")
        self.tree.heading("value",   text="Value")
        self.tree.heading("raw",     text="Raw (Hex)")
        self.tree.heading("status",  text="Status")

        self.tree.column("address", width=90,  anchor="center")
        self.tree.column("alias",   width=110, anchor="w")
        self.tree.column("value",   width=140, anchor="e")
        self.tree.column("raw",     width=80,  anchor="center")
        self.tree.column("status",  width=80,  anchor="center")

        vsb = ttk.Scrollbar(grid_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Tag styles
        self.tree.tag_configure("ok",    foreground=COLOR_OK)
        self.tree.tag_configure("error", foreground=COLOR_ERROR)
        self.tree.tag_configure("sel",   background=COLOR_SEL)

        # Double-click to write
        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>",   self._on_double_click)

        self._populate_rows()

    def _populate_rows(self):
        self.tree.delete(*self.tree.get_children())
        cfg = self.slave_cfg
        for i in range(cfg.quantity):
            addr    = cfg.start_address + i
            a_label = addr_label(addr, cfg.address_base, cfg.function_code)
            alias   = cfg.aliases.get(addr, "")
            self.tree.insert("", "end", iid=str(i),
                             values=(a_label, alias, "---", "---", "---"))
        self.values = [None] * cfg.quantity
        self.errors = [None]  * cfg.quantity

    def _update_title(self):
        cfg = self.slave_cfg
        fc_name = FUNCTION_CODES.get(cfg.function_code, f"FC{cfg.function_code:02d}")
        self.title(f"Slave ID: {cfg.slave_id}  |  {fc_name}  |  Addr: {cfg.start_address}  |  Rate: {cfg.scan_rate}ms")

    # ── Polling ──────────────────────────────────────────────────

    def start_polling(self):
        if self.polling:
            return
        self.polling = True
        self._stop_event.clear()
        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()
        self.win_status.config(text="Polling...", fg=COLOR_OK)

    def stop_polling(self):
        self.polling = False
        self._stop_event.set()
        self.win_status.config(text="Stopped", fg=COLOR_WARN)

    def _poll_loop(self):
        while not self._stop_event.is_set():
            start = time.monotonic()
            values, error = self.app.engine.read_registers(self.slave_cfg)
            self.after(0, self._update_display, values, error)
            elapsed = (time.monotonic() - start) * 1000
            wait_ms = max(10, self.slave_cfg.scan_rate - elapsed)
            self._stop_event.wait(wait_ms / 1000.0)

    def _update_display(self, values, error):
        cfg = self.slave_cfg
        if error:
            self.win_status.config(text=f"Error: {error}", fg=COLOR_ERROR)
            for i in range(cfg.quantity):
                self.tree.set(str(i), "value",  "ERROR")
                self.tree.set(str(i), "raw",    "----")
                self.tree.set(str(i), "status", error[:12])
                self.tree.item(str(i), tags=("error",))
            self.errors = [error] * cfg.quantity
            self.app.update_status()
            return

        self.win_status.config(text=f"OK  [{datetime.now().strftime('%H:%M:%S')}]", fg=COLOR_OK)
        self.values = values
        self.errors = [None] * cfg.quantity

        for i, raw in enumerate(values[:cfg.quantity]):
            addr    = cfg.start_address + i
            a_label = addr_label(addr, cfg.address_base, cfg.function_code)
            alias   = cfg.aliases.get(addr, "")
            raw2    = values[i + 1] if i + 1 < len(values) else 0
            disp    = format_value(raw, cfg.display_fmt, raw2)
            hex_str = f"0x{raw & 0xFFFF:04X}" if isinstance(raw, int) else str(raw)
            self.tree.set(str(i), "address", a_label)
            self.tree.set(str(i), "alias",   alias)
            self.tree.set(str(i), "value",   disp)
            self.tree.set(str(i), "raw",     hex_str)
            self.tree.set(str(i), "status",  "OK")
            self.tree.item(str(i), tags=("ok",))

        self.app.update_status()

    # ── Interaction ──────────────────────────────────────────────

    def _on_double_click(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        idx  = int(sel[0])
        cfg  = self.slave_cfg
        addr = cfg.start_address + idx
        fc   = cfg.function_code

        # Only allow writes for write-capable FCs or single-register
        write_fc = None
        if fc in (1, 2):
            write_fc = 5   # Write Single Coil
        elif fc in (3, 4):
            write_fc = 6   # Write Single Register
        elif fc in (5, 6, 15, 16):
            write_fc = fc
        else:
            return

        cur_val = self.tree.set(sel[0], "value")
        dlg = WriteValueDialog(self, addr, cur_val, write_fc)
        if dlg.result is not None:
            err = self.app.engine.write_register(cfg.slave_id, addr, dlg.result, write_fc)
            if err:
                messagebox.showerror("Write Error", err, parent=self)
            else:
                self.app.log(f"Written {dlg.result} to address {addr} (FC{write_fc:02d})")

    def edit_alias(self, idx: int):
        cfg  = self.slave_cfg
        addr = cfg.start_address + idx
        cur  = cfg.aliases.get(addr, "")
        new  = simpledialog.askstring("Edit Alias", f"Alias for address {addr}:", initialvalue=cur, parent=self)
        if new is not None:
            cfg.aliases[addr] = new
            self.tree.set(str(idx), "alias", new)

    def configure(self, **kwargs):
        # Override to handle bg without passing to super if needed
        try:
            super().configure(**kwargs)
        except tk.TclError:
            pass

    def reconfigure(self):
        """Open the definition dialog and apply new settings."""
        dlg = ReadWriteDefinitionDialog(self.app.root, self.slave_cfg)
        if dlg.result:
            was_polling = self.polling
            if was_polling:
                self.stop_polling()
            self.slave_cfg = dlg.result
            self._update_title()
            self._populate_rows()
            if was_polling:
                self.start_polling()

    def _on_close(self):
        self.stop_polling()
        if self in SlaveWindow._instances:
            SlaveWindow._instances.remove(self)
        self.destroy()

    def get_config_dict(self):
        return self.slave_cfg.to_dict()


# ─────────────────────────── Traffic Log Window ───────────────────

class TrafficWindow(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Modbus Traffic Monitor")
        self.geometry("700x300")
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        frame = ttk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True)

        self.text = tk.Text(frame, font=("Consolas", 9), bg="#1a1a2e", fg="#a0ffa0",
                            state=tk.DISABLED, wrap=tk.NONE)
        vsb = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.text.yview)
        hsb = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=self.text.xview)
        self.text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.text.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(btn_frame, text="Clear", command=self._clear).pack(side=tk.LEFT)
        self.max_lines = 500
        self.withdraw()

    def append(self, ts: str, msg: str):
        self.text.configure(state=tk.NORMAL)
        line = f"{ts}  {msg}\n"
        self.text.insert(tk.END, line)
        # Colour TX / RX differently
        line_idx = int(self.text.index("end-1c").split(".")[0])
        if "[TX]" in msg:
            self.text.tag_add("tx", f"{line_idx}.0", f"{line_idx}.end")
            self.text.tag_configure("tx", foreground="#80cfff")
        elif "[RX]" in msg:
            self.text.tag_add("rx", f"{line_idx}.0", f"{line_idx}.end")
            self.text.tag_configure("rx", foreground="#a0ffa0")
        # Trim
        lines = int(self.text.index("end-1c").split(".")[0])
        if lines > self.max_lines:
            self.text.delete("1.0", f"{lines - self.max_lines}.0")
        self.text.configure(state=tk.DISABLED)
        self.text.see(tk.END)

    def _clear(self):
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)
        self.text.configure(state=tk.DISABLED)


# ─────────────────────────── Main Application ────────────────────

class ModbusPollApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("900x600")
        self.root.minsize(700, 400)

        self.conn_cfg   = ConnectionConfig()
        self.engine     = ModbusEngine(self.log, self._traffic_callback)
        self.log_queue: queue.Queue = queue.Queue()
        self._slave_windows: List[SlaveWindow] = []

        self._build_menu()
        self._build_toolbar()
        self._build_workspace()
        self._build_statusbar()
        self._build_log_pane()

        self.traffic_win = TrafficWindow(self.root)

        # Periodically flush log queue to UI
        self.root.after(200, self._flush_log)
        self.root.protocol("WM_DELETE_WINDOW", self._on_exit)

        if not PYMODBUS_AVAILABLE:
            self.log("WARNING: pymodbus not found. Install with: pip install pymodbus pyserial")

    # ── Build UI ─────────────────────────────────────────────────

    def _build_menu(self):
        mb = tk.Menu(self.root)
        self.root.config(menu=mb)

        # File
        fm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="File", menu=fm)
        fm.add_command(label="New",        accelerator="Ctrl+N", command=self.cmd_new)
        fm.add_command(label="Open...",    accelerator="Ctrl+O", command=self.cmd_open)
        fm.add_command(label="Save",       accelerator="Ctrl+S", command=self.cmd_save)
        fm.add_command(label="Save As...",                        command=self.cmd_save_as)
        fm.add_separator()
        fm.add_command(label="Close",                             command=self.cmd_close_active)
        fm.add_separator()
        fm.add_command(label="Exit",       accelerator="Alt+F4", command=self._on_exit)
        self.root.bind_all("<Control-n>", lambda e: self.cmd_new())
        self.root.bind_all("<Control-o>", lambda e: self.cmd_open())
        self.root.bind_all("<Control-s>", lambda e: self.cmd_save())

        # Connection
        cm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Connection", menu=cm)
        cm.add_command(label="Connect",           command=self.cmd_connect)
        cm.add_command(label="Disconnect",         command=self.cmd_disconnect)
        cm.add_separator()
        cm.add_command(label="Connection Setup...", command=self.cmd_connection_setup)

        # Setup
        sm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Setup", menu=sm)
        sm.add_command(label="Read/Write Definition...", command=self.cmd_rw_definition)

        # Functions
        fnm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Functions", menu=fnm)
        for fc, name in FUNCTION_CODES.items():
            fnm.add_command(label=name, command=lambda f=fc: self.cmd_new_with_fc(f))

        # View
        vm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="View", menu=vm)
        self.show_traffic_var = tk.BooleanVar(value=False)
        vm.add_checkbutton(label="Show Traffic", variable=self.show_traffic_var,
                           command=self._toggle_traffic)
        vm.add_separator()
        vm.add_command(label="Clear Log", command=self._clear_log)
        vm.add_separator()
        for fmt in DISPLAY_FORMATS:
            vm.add_command(label=f"Display as {fmt}", command=lambda f=fmt: self.set_display_format(f))

        # Window
        wm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Window", menu=wm)
        wm.add_command(label="Cascade",      command=self.cascade_windows)
        wm.add_command(label="Tile",         command=self.tile_windows)
        wm.add_separator()
        wm.add_command(label="Close All",    command=self.close_all_windows)

        # Help
        hm = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Help", menu=hm)
        hm.add_command(label=f"About {APP_TITLE}", command=self.cmd_about)

    def _build_toolbar(self):
        tb = tk.Frame(self.root, relief=tk.RAISED, bd=1, bg="#dcdcdc")
        tb.pack(fill=tk.X)

        buttons = [
            ("New",        self.cmd_new),
            ("Open",       self.cmd_open),
            ("Save",       self.cmd_save),
            ("|",          None),
            ("Connect",    self.cmd_connect),
            ("Disconnect", self.cmd_disconnect),
            ("|",          None),
            ("Setup",      self.cmd_rw_definition),
            ("|",          None),
            ("Traffic",    self._toggle_traffic),
        ]

        for label, cmd in buttons:
            if label == "|":
                tk.Frame(tb, width=2, bg="#999999").pack(side=tk.LEFT, fill=tk.Y, padx=4, pady=2)
            else:
                btn = tk.Button(tb, text=label, command=cmd,
                                relief=tk.FLAT, bg="#dcdcdc", padx=6, pady=2,
                                font=("Segoe UI", 8), cursor="hand2")
                btn.pack(side=tk.LEFT, padx=2, pady=2)
                btn.bind("<Enter>", lambda e, b=btn: b.config(relief=tk.RAISED))
                btn.bind("<Leave>", lambda e, b=btn: b.config(relief=tk.FLAT))

    def _build_workspace(self):
        """Central paned area: workspace (for slave windows) + log."""
        self.main_pane = tk.PanedWindow(self.root, orient=tk.VERTICAL, sashrelief=tk.RAISED)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        # Workspace frame (slave windows float as Toplevels referencing root)
        self.workspace_label = tk.Label(
            self.main_pane,
            text="Modbus Poll  –  No active connections\n\nUse  File > New  to create a slave poll window\nthen  Connection > Connect  to start polling.",
            justify=tk.CENTER,
            fg="#aaaaaa", font=("Segoe UI", 11),
            bg="#e8e8e8"
        )
        self.main_pane.add(self.workspace_label, minsize=120)

    def _build_log_pane(self):
        log_frame = ttk.LabelFrame(self.main_pane, text="Application Log")
        self.main_pane.add(log_frame, minsize=80)

        self.log_text = tk.Text(log_frame, height=6, font=("Consolas", 8),
                                state=tk.DISABLED, wrap=tk.WORD, bg="#1e1e1e", fg="#d4d4d4")
        vsb = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def _build_statusbar(self):
        sb = tk.Frame(self.root, relief=tk.SUNKEN, bd=1, bg="#dcdcdc")
        sb.pack(fill=tk.X, side=tk.BOTTOM)

        self.status_conn  = tk.Label(sb, text="Disconnected", width=20, anchor="w",
                                     bg="#dcdcdc", fg=COLOR_ERROR, font=("Segoe UI", 8))
        self.status_tx    = tk.Label(sb, text="Tx: 0",  width=10, anchor="w",
                                     bg="#dcdcdc", font=("Segoe UI", 8))
        self.status_rx    = tk.Label(sb, text="Rx: 0",  width=10, anchor="w",
                                     bg="#dcdcdc", font=("Segoe UI", 8))
        self.status_err   = tk.Label(sb, text="Err: 0", width=10, anchor="w",
                                     bg="#dcdcdc", fg=COLOR_ERROR, font=("Segoe UI", 8))
        self.status_rate  = tk.Label(sb, text="Rate: ---", width=14, anchor="w",
                                     bg="#dcdcdc", font=("Segoe UI", 8))
        self.status_time  = tk.Label(sb, text="", width=22, anchor="e",
                                     bg="#dcdcdc", font=("Segoe UI", 8))

        for w in (self.status_conn, self.status_tx, self.status_rx,
                  self.status_err, self.status_rate, self.status_time):
            w.pack(side=tk.LEFT, padx=6)

        self._tick_clock()

    def _tick_clock(self):
        self.status_time.config(text=datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        self.root.after(1000, self._tick_clock)

    # ── Status helpers ───────────────────────────────────────────

    def update_status(self):
        eng = self.engine
        connected = eng.connected
        self.status_conn.config(
            text=f"{'Connected' if connected else 'Disconnected'} [{self.conn_cfg.conn_type}]",
            fg=COLOR_OK if connected else COLOR_ERROR
        )
        self.status_tx.config(text=f"Tx: {eng.tx_count}")
        self.status_rx.config(text=f"Rx: {eng.rx_count}")
        self.status_err.config(text=f"Err: {eng.err_count}",
                               fg=COLOR_ERROR if eng.err_count else "#555555")
        active = [w for w in SlaveWindow._instances if w.polling]
        if active:
            rate = active[0].slave_cfg.scan_rate
            self.status_rate.config(text=f"Rate: {rate}ms")

    def log(self, msg: str):
        self.log_queue.put(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def _flush_log(self):
        while not self.log_queue.empty():
            msg = self.log_queue.get_nowait()
            self.log_text.configure(state=tk.NORMAL)
            self.log_text.insert(tk.END, msg + "\n")
            # Trim to 500 lines
            lines = int(self.log_text.index("end-1c").split(".")[0])
            if lines > 500:
                self.log_text.delete("1.0", f"{lines - 500}.0")
            self.log_text.configure(state=tk.DISABLED)
            self.log_text.see(tk.END)
        self.root.after(200, self._flush_log)

    def _traffic_callback(self, ts: str, msg: str):
        self.traffic_win.after(0, self.traffic_win.append, ts, msg)

    def _clear_log(self):
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

    # ── Commands ─────────────────────────────────────────────────

    def cmd_new(self):
        dlg = ReadWriteDefinitionDialog(self.root, SlaveConfig())
        if dlg.result:
            win = SlaveWindow(self, dlg.result)
            self._slave_windows.append(win)
            self.log(f"New slave window: ID={dlg.result.slave_id} FC={dlg.result.function_code}")
            if self.engine.connected:
                win.start_polling()

    def cmd_new_with_fc(self, fc: int):
        cfg = SlaveConfig()
        cfg.function_code = fc
        dlg = ReadWriteDefinitionDialog(self.root, cfg)
        if dlg.result:
            win = SlaveWindow(self, dlg.result)
            self._slave_windows.append(win)
            if self.engine.connected:
                win.start_polling()

    def cmd_open(self):
        path = filedialog.askopenfilename(
            title="Open Modbus Poll Definition",
            filetypes=[("Modbus Poll files", "*.mbp"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            conn_d = data.get("connection", {})
            self.conn_cfg.from_dict(conn_d)
            for wd in data.get("windows", []):
                cfg = SlaveConfig()
                cfg.from_dict(wd)
                win = SlaveWindow(self, cfg)
                win.filename = path
                self._slave_windows.append(win)
            self.log(f"Opened: {path}")
        except Exception as e:
            messagebox.showerror("Open Error", str(e))

    def cmd_save(self):
        if not SlaveWindow._instances:
            return
        win = self._active_slave_window()
        if win and win.filename:
            self._save_to(win.filename)
        else:
            self.cmd_save_as()

    def cmd_save_as(self):
        path = filedialog.asksaveasfilename(
            title="Save Modbus Poll Definition",
            defaultextension=".mbp",
            filetypes=[("Modbus Poll files", "*.mbp"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        if not path:
            return
        self._save_to(path)
        win = self._active_slave_window()
        if win:
            win.filename = path

    def _save_to(self, path: str):
        data = {
            "connection": self.conn_cfg.to_dict(),
            "windows": [w.get_config_dict() for w in SlaveWindow._instances]
        }
        try:
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            self.log(f"Saved: {path}")
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    def cmd_close_active(self):
        win = self._active_slave_window()
        if win:
            win._on_close()

    def _active_slave_window(self) -> Optional[SlaveWindow]:
        for win in reversed(SlaveWindow._instances):
            try:
                if win.winfo_exists() and win.focus_displayof():
                    return win
            except Exception:
                pass
        return SlaveWindow._instances[-1] if SlaveWindow._instances else None

    def cmd_connect(self):
        ok = self.engine.connect(self.conn_cfg)
        if ok:
            self.log(f"Connected: {self.conn_cfg.conn_type} {self.conn_cfg.host}:{self.conn_cfg.port}")
            for win in SlaveWindow._instances:
                win.start_polling()
        else:
            messagebox.showerror("Connection Failed",
                                 f"Could not connect via {self.conn_cfg.conn_type}.\n"
                                 "Check settings under Connection > Connection Setup.")
        self.update_status()

    def cmd_disconnect(self):
        for win in SlaveWindow._instances:
            win.stop_polling()
        self.engine.disconnect()
        self.update_status()

    def cmd_connection_setup(self):
        dlg = ConnectionDialog(self.root, self.conn_cfg)
        if dlg.result:
            was_connected = self.engine.connected
            if was_connected:
                self.cmd_disconnect()
            self.conn_cfg = dlg.result
            self.log(f"Connection settings updated: {self.conn_cfg.conn_type}")
            if was_connected:
                self.cmd_connect()

    def cmd_rw_definition(self):
        win = self._active_slave_window()
        if win:
            win.reconfigure()
        else:
            self.cmd_new()

    def _toggle_traffic(self):
        if self.show_traffic_var.get():
            self.traffic_win.deiconify()
        else:
            self.traffic_win.withdraw()
        # If called from toolbar (no checkbutton state change), toggle manually
        if not hasattr(self, 'show_traffic_var'):
            return
        if self.traffic_win.winfo_viewable():
            self.traffic_win.withdraw()
            self.show_traffic_var.set(False)
        else:
            self.traffic_win.deiconify()
            self.show_traffic_var.set(True)

    def set_display_format(self, fmt: str):
        win = self._active_slave_window()
        if win:
            win.slave_cfg.display_fmt = fmt
            self.log(f"Display format set to: {fmt}")

    def cascade_windows(self):
        for i, win in enumerate(SlaveWindow._instances):
            if win.winfo_exists():
                win.geometry(f"+{60 + i*24}+{60 + i*24}")
                win.lift()

    def tile_windows(self):
        wins = [w for w in SlaveWindow._instances if w.winfo_exists()]
        if not wins:
            return
        n = len(wins)
        cols = max(1, int(n ** 0.5))
        rows = (n + cols - 1) // cols
        w = max(400, self.root.winfo_width() // cols)
        h = max(250, (self.root.winfo_height() - 100) // rows)
        for i, win in enumerate(wins):
            c, r = i % cols, i // cols
            win.geometry(f"{w}x{h}+{c*w}+{r*h + 60}")
            win.lift()

    def close_all_windows(self):
        for win in list(SlaveWindow._instances):
            win._on_close()

    def cmd_about(self):
        messagebox.showinfo(
            f"About {APP_TITLE}",
            f"{APP_TITLE}  v{VERSION}\n\n"
            "A Python replica of Modbus Poll.\n"
            "Supports Modbus RTU, ASCII, TCP, UDP.\n\n"
            "Built with:\n"
            "  • tkinter (GUI)\n"
            "  • pymodbus (Modbus protocol)\n"
            "  • pyserial (Serial communication)\n\n"
            "Double-click any register value to write."
        )

    def _on_exit(self):
        if messagebox.askokcancel("Exit", "Exit Modbus Poll?"):
            self.close_all_windows()
            self.engine.disconnect()
            self.root.destroy()

    # ── Main loop ────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


# ─────────────────────────── Entry Point ─────────────────────────

def main():
    app = ModbusPollApp()
    app.run()


if __name__ == "__main__":
    main()
