# Modbus Poll – Python Windows Application

A complete, production-quality Python replica of the **Modbus Poll** commercial master simulator. Built with `tkinter` (GUI), `pymodbus 3.x` (Modbus protocol), and `threading` (background polling).

---

## Features

- **Multiple Connection Types**: Modbus RTU (serial), Modbus ASCII (serial), Modbus TCP, Modbus UDP
- **MDI Interface**: Multiple independent slave-device poll windows
- **All Standard Function Codes**: FC01–FC16 (read coils, discrete inputs, holding & input registers; write single/multiple coils & registers)
- **10 Display Formats**: Signed/Unsigned Int, Hex, Binary, Float 32-bit (ABCD/CDAB/BADC/DCBA), Double 64-bit, ASCII String
- **Address Modes**: 0-based or 1-based (40001-style)
- **Configurable Scan Rate**: Millisecond-precision polling intervals per window
- **Traffic Monitor**: Real-time view of raw Modbus TX/RX frames
- **Color-coded Status**: Green = OK, Red = error/timeout
- **Configuration Files**: Save/load all settings as JSON (`.mbp`)
- **Live Status Bar**: Connection type, Tx/Rx counters, error count, clock

---

## Requirements

| Requirement | Version |
|-------------|---------|
| Python      | 3.8+    |
| pymodbus    | ≥ 3.0.0 |
| pyserial    | ≥ 3.5   |

> **Windows** is the primary target platform. The application also runs on Linux and macOS.

---

## Installation

### Step 1 – Install Python

Download Python 3.8 or later from <https://www.python.org/downloads/> and run the installer.  
Make sure **"Add Python to PATH"** is checked during installation.

### Step 2 – (Recommended) Create a Virtual Environment

Open a Command Prompt or PowerShell window in the project folder:

```cmd
python -m venv venv
venv\Scripts\activate
```

On Linux / macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3 – Install Dependencies

```cmd
pip install -r requirements.txt
```

Or install packages manually:

```cmd
pip install "pymodbus>=3.0.0" "pyserial>=3.5"
```

---

## Running the Application

```cmd
python modbus_poll.py
```

The main window opens with an empty workspace. Use the menus or toolbar to create slave windows and connect to a device.

---

## Quick-Start Walkthrough

### 1. Configure the Connection

Go to **Connection → Connection Setup…** (or click the **Connect** toolbar button to open setup automatically on first run).

**Modbus TCP / UDP**

| Field       | Description                          | Default     |
|-------------|--------------------------------------|-------------|
| IP Address  | Target device IP or hostname         | `127.0.0.1` |
| Port        | Modbus TCP port                      | `502`       |
| Timeout (s) | Response timeout                     | `1.0`       |

**Modbus RTU / ASCII (Serial)**

| Field      | Description                                | Default |
|------------|--------------------------------------------|---------|
| COM Port   | Serial port (e.g. `COM3`, `/dev/ttyUSB0`)  | `COM1`  |
| Baud Rate  | Must match device                          | `9600`  |
| Data Bits  | 7 or 8                                     | `8`     |
| Parity     | None / Even / Odd / Mark / Space           | `None`  |
| Stop Bits  | 1 / 1.5 / 2                                | `1`     |
| RTS / DTR  | Enable hardware flow control if needed     | Off     |

Click **OK** to save settings.

### 2. Create a Slave Poll Window

Go to **File → New** (or press **Ctrl+N**).  
The **Read / Write Definition** dialog opens:

| Setting         | Description                                    | Range / Default       |
|-----------------|------------------------------------------------|-----------------------|
| Slave ID        | Modbus device address                          | 1–247, default `1`    |
| Function Code   | FC01–FC16                                      | FC03 (holding regs)   |
| Starting Address| First register / coil address                  | 0–65535, default `0`  |
| Quantity        | Number of registers / coils to read            | 1–125, default `10`   |
| Scan Rate (ms)  | Polling interval in milliseconds               | 100–60000, default `1000` |
| Display Format  | How raw values are shown                       | Signed Int (16-bit)   |
| Address Display | 0-based (0, 1, 2…) or 1-based (40001, 40002…) | 0-based               |

Click **OK**. A slave window appears.

### 3. Connect and Start Polling

Click **Connection → Connect** (or the **Connect** toolbar button).  
If the device is reachable, the status bar turns green and all open slave windows start polling at their configured scan rate.

### 4. Reading Data

Each slave window shows a live-updating table:

| Column        | Description                                  |
|---------------|----------------------------------------------|
| **Address**   | Register / coil address                      |
| **Alias**     | User-defined label (right-click to edit)     |
| **Value**     | Formatted value in the selected display mode |
| **Raw (Hex)** | Raw 16-bit value in hexadecimal              |
| **Status**    | `OK` or error description                    |

Rows turn **red** on communication errors and **green** on successful reads.

### 5. Writing Values

**Double-click** any row to open the **Write Value** dialog.

- For coils (FC01 / FC05): enter `0` (OFF) or `1` (ON)
- For registers (FC03 / FC06 / FC16): enter a decimal integer (`1234`) or hex (`0x04D2`)

Click **Write** to send the value. The next poll cycle will confirm the updated value.

---

## Display Formats Reference

| Format              | Description                                                |
|---------------------|------------------------------------------------------------|
| Signed Int (16-bit) | Interprets the register as a signed 16-bit integer (−32768 to +32767) |
| Unsigned Int (16-bit)| Raw unsigned value (0 to 65535)                          |
| Hex                 | Four-digit hexadecimal (`0x1A2B`)                         |
| Binary              | 16-bit binary string (`0001101000101011`)                  |
| Float 32-bit ABCD   | IEEE 754 float, big-endian word order (most common)        |
| Float 32-bit CDAB   | IEEE 754 float, little-endian word order                   |
| Float 32-bit BADC   | IEEE 754 float, byte-swapped big-endian                    |
| Float 32-bit DCBA   | IEEE 754 float, byte-swapped little-endian                 |
| Double 64-bit       | 64-bit IEEE 754 double (4 consecutive registers)           |
| ASCII String        | Two ASCII characters per register (high byte + low byte)   |

---

## Function Code Reference

| FC  | Name                      | Read / Write | Data Type   |
|-----|---------------------------|--------------|-------------|
| FC01| Read Coils                | Read         | Bit (0/1)   |
| FC02| Read Discrete Inputs      | Read         | Bit (0/1)   |
| FC03| Read Holding Registers    | Read         | 16-bit word |
| FC04| Read Input Registers      | Read         | 16-bit word |
| FC05| Write Single Coil         | Write        | Bit (0/1)   |
| FC06| Write Single Register     | Write        | 16-bit word |
| FC15| Write Multiple Coils      | Write        | Bit array   |
| FC16| Write Multiple Registers  | Write        | 16-bit array|

---

## Modbus Exception Codes

| Code | Name                                  |
|------|---------------------------------------|
| 01   | Illegal Function                      |
| 02   | Illegal Data Address                  |
| 03   | Illegal Data Value                    |
| 04   | Server Device Failure                 |
| 05   | Acknowledge                           |
| 06   | Server Device Busy                    |
| 08   | Memory Parity Error                   |
| 0A   | Gateway Path Unavailable              |
| 0B   | Gateway Target Device Failed to Respond|

---

## Traffic Monitor

Open with **View → Show Traffic** (or the **Traffic** toolbar button).

- **Blue lines** — requests sent by the master (TX)
- **Green lines** — responses received from the slave (RX)
- Timestamp format: `HH:MM:SS.mmm`
- Click **Clear** to reset the log

---

## Saving and Loading Configurations

| Action       | Menu                        | Shortcut |
|--------------|-----------------------------|----------|
| Save         | File → Save                 | Ctrl+S   |
| Save As      | File → Save As…             |          |
| Open / Load  | File → Open…                | Ctrl+O   |

Configuration files use `.mbp` extension (JSON format). They store:
- Connection settings (type, host, port, baud rate, etc.)
- All slave window definitions (slave ID, FC, address, quantity, scan rate, aliases, display format)

---

## Window Management

| Action           | Menu                      |
|------------------|---------------------------|
| Cascade windows  | Window → Cascade          |
| Tile windows     | Window → Tile             |
| Close all        | Window → Close All        |

---

## Keyboard Shortcuts

| Shortcut | Action                         |
|----------|--------------------------------|
| Ctrl+N   | New slave window               |
| Ctrl+O   | Open configuration file        |
| Ctrl+S   | Save configuration file        |
| Alt+F4   | Exit application               |

---

## Troubleshooting

### Cannot connect via TCP
1. Verify the IP address and port (`502` is standard; some devices use `5020` or others).
2. Run `ping <ip>` to confirm network reachability.
3. Check for firewalls blocking port 502.
4. Some simulators (e.g. ModRSsim2, Diagslave) must be started before connecting.

### Cannot connect via Serial (RTU/ASCII)
1. Open **Device Manager** and confirm the COM port number.
2. Ensure no other program (PuTTY, another logger) holds the port open.
3. Match **all** serial parameters (baud, parity, stop bits, data bits) to the device.
4. For RS-485 converters: try enabling **RTS Control** in Connection Setup.

### "No Response" / Timeout Errors
- Increase the **Timeout** value in Connection Setup.
- Reduce the polling frequency (increase **Scan Rate**).
- Confirm the **Slave ID** matches the device's DIP switch / configuration.

### Garbled / Unexpected Register Values
- Check **byte order**: try different Float format variants (ABCD vs CDAB vs BADC vs DCBA).
- Confirm **Starting Address**: some devices count from 0, others from 1 internally.
- Verify the correct **Function Code** for the register type.

### `ImportError: No module named 'pymodbus'`
```cmd
pip install "pymodbus>=3.0.0" pyserial
```
Make sure you are using the same Python environment you launched the application from.

---

## Project Structure

```
Modbus/
├── modbus_poll.py      # Main application (single-file, self-contained)
├── requirements.txt    # Python package dependencies
└── README.md           # This file
```

---

## License

This software is provided for educational and development purposes as a Python implementation inspired by the Modbus Poll commercial product by WinTech A/S. It is not affiliated with or endorsed by WinTech A/S.
