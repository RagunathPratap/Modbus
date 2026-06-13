# Modbus Poll Python Replica

A complete Python Windows application replicating the functionality of the commercial Modbus Poll software. Built with tkinter for the GUI, pymodbus 3.x for Modbus protocol support, and threading for background polling.

## Features

- **Multiple Connection Types**: Modbus RTU (serial), Modbus ASCII (serial), Modbus TCP, Modbus UDP
- **MDI Interface**: Multiple Document Interface with child windows for each slave device
- **All Standard Function Codes**: FC01, FC02, FC03, FC04, FC05, FC06, FC15, FC16
- **Multiple Display Formats**: Signed/Unsigned Integer, Hex, Binary, Float 32-bit (ABCD/CDAB/BADC/DCBA), Double 64-bit, ASCII String
- **Configurable Polling**: Scan rate configurable in milliseconds (default 1000ms)
- **Traffic Log**: Real-time hex frame display for Tx/Rx traffic
- **Configuration Save/Load**: JSON-based configuration files
- **Color-coded Status**: Green for valid data, red for errors
- **Write Support**: Double-click any register to write a new value
- **Modbus Exception Handling**: Full exception code support (01-11)
- **Status Bar**: Connection status, Tx/Rx counters, error count, scan rate

## Requirements

- Python 3.8+
- Windows (tested), Linux/Mac may work with minor adjustments
- pymodbus >= 3.0.0
- pyserial >= 3.5

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
python modbus_poll.py
```

### Connecting via TCP

1. Go to **Connection > Connection Setup...**
2. Select **Modbus TCP** as connection type
3. Enter IP address and port (default 502)
4. Click **Connect** or go to **Connection > Connect**

### Connecting via Serial (RTU/ASCII)

1. Go to **Connection > Connection Setup...**
2. Select **Modbus RTU** or **Modbus ASCII**
3. Choose COM port, baud rate, data bits, parity, stop bits
4. Configure RTS/DTR control if needed
5. Click **Connect**

### Setting Up a Slave Window

1. After connecting, go to **Setup > Read/Write Definition...**
2. Set Slave ID (1-247)
3. Choose Function Code (FC01-FC04 for reading)
4. Set starting address and quantity of registers
5. Configure scan rate (ms)
6. Click OK — a new slave window appears and polling begins

### Writing Values

- Double-click any register row in a slave window to open the Write dialog
- Enter a new value and click Write
- Supports FC05, FC06, FC15, FC16

### Display Formats

Right-click or use **View > Display as** to change how register values are shown:
- **Signed Integer**: 16-bit signed (-32768 to 32767)
- **Unsigned Integer**: 16-bit unsigned (0 to 65535)
- **Hex**: Hexadecimal (0x0000 to 0xFFFF)
- **Binary**: 16-bit binary string
- **Float ABCD/CDAB/BADC/DCBA**: 32-bit IEEE 754 float, various byte orders
- **Double**: 64-bit double (uses 4 consecutive registers)
- **ASCII**: Two ASCII characters per register

### Traffic Log

- Go to **View > Show Traffic** to open the traffic log window
- Shows timestamp, direction (Tx/Rx), and hex frame bytes
- Useful for debugging communication issues

### Configuration Files

- **File > Save** / **File > Save As**: Save current windows and connection settings to JSON
- **File > Open**: Load a previously saved configuration

## Menu Reference

| Menu | Item | Description |
|------|------|-------------|
| File | New | Reset application |
| File | Open | Load configuration |
| File | Save/Save As | Save configuration |
| File | Exit | Quit application |
| Connection | Connect | Establish connection |
| Connection | Disconnect | Close connection |
| Connection | Connection Setup | Configure connection parameters |
| Setup | Read/Write Definition | Configure polling parameters |
| Functions | Read Coils (FC01) | Read coil status |
| Functions | Read Discrete Inputs (FC02) | Read discrete inputs |
| Functions | Read Holding Registers (FC03) | Read holding registers |
| Functions | Read Input Registers (FC04) | Read input registers |
| Functions | Write Single Coil (FC05) | Write one coil |
| Functions | Write Single Register (FC06) | Write one register |
| Functions | Write Multiple Coils (FC15) | Write multiple coils |
| Functions | Write Multiple Registers (FC16) | Write multiple registers |
| View | Display as Signed | Show as signed integer |
| View | Display as Unsigned | Show as unsigned integer |
| View | Display as Hex | Show as hexadecimal |
| View | Display as Binary | Show as binary |
| View | Display as Float ABCD | Show as 32-bit float |
| View | Show Traffic | Open traffic log window |
| View | Show Errors | Filter to show only error registers |
| Window | Cascade | Cascade MDI windows |
| Window | Tile | Tile MDI windows |

## Architecture

- `ModbusPollApp` — Main application window, MDI container, menu/toolbar/status bar
- `ConnectionManager` — Manages pymodbus client lifecycle (connect/disconnect/read/write)
- `SlaveWindow` — MDI child frame displaying a ttk.Treeview grid of register values
- `ConnectionDialog` — Modal dialog for configuring connection parameters
- `ReadWriteDefinitionDialog` — Modal dialog for FC/address/quantity/scan rate
- `WriteValueDialog` — Modal dialog for writing a value to a register
- `TrafficLog` — Toplevel window showing live hex traffic
- `PollingThread` — Background daemon thread that polls registers and updates the UI

## Modbus Exception Codes

| Code | Name | Description |
|------|------|-------------|
| 01 | Illegal Function | Function code not supported |
| 02 | Illegal Data Address | Address not in valid range |
| 03 | Illegal Data Value | Value not allowed |
| 04 | Slave Device Failure | Unrecoverable error |
| 05 | Acknowledge | Long-duration command accepted |
| 06 | Slave Device Busy | Processing long-duration command |
| 08 | Memory Parity Error | Memory parity error detected |
| 0A | Gateway Path Unavailable | Gateway misconfigured |
| 0B | Gateway Target No Response | Target device failed to respond |

## License

This is an open-source replica for educational and development purposes. The original Modbus Poll is a commercial product by Witte Software.
