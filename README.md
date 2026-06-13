# Modbus Poll – Python Replica

A comprehensive Python replica of the **Modbus Poll** master simulator, built with `tkinter` and `pymodbus` 3.x.

## Features

- **Multiple Connection Types**: Modbus RTU, ASCII (serial), TCP, and UDP
- **MDI Interface**: Multiple slave device windows inside the main application window
- **Function Codes**: FC01, FC02, FC03, FC04, FC05, FC06, FC15, FC16
- **Display Formats**: Signed Int, Unsigned Int, Hex, Binary, Float 32-bit (ABCD/CDAB/BADC/DCBA), Double 64-bit, ASCII String
- **Address Styles**: 0-based or 1-based (40001 style)
- **Configurable Scan Rate**: Millisecond-precision polling intervals
- **Traffic Log**: View raw Modbus frames in real-time
- **Configuration Save/Load**: JSON-based project files
- **Status Bar**: Live connection status, Tx/Rx counters, error count
- **Color Coding**: Green for valid data, red for errors/timeouts

## Requirements

- Python 3.8 or higher
- Windows (primary target; works on Linux/macOS with minor adjustments)

## Installation

### 1. Install Python

Download and install Python 3.8+ from https://www.python.org/downloads/

### 2. Create a Virtual Environment (recommended)

```cmd
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```cmd
pip install -r requirements.txt
```

Or install manually:

```cmd
pip install pymodbus>=3.0.0 pyserial>=3.5
```

## Running the Application

```cmd
python modbus_poll.py
```

## Usage Guide

### Connecting to a Device

#### Modbus TCP
1. Go to **Connection → Connection Setup...**
2. Select **Modbus TCP/IP** from the connection type dropdown
3. Enter the device IP address (e.g., `192.168.1.10`)
4. Enter the port number (default: `502`)
5. Set the timeout (default: `1000` ms)
6. Click **OK**
7. Go to **Connection → Connect** (or press the Connect toolbar button)

#### Modbus RTU (Serial)
1. Go to **Connection → Connection Setup...**
2. Select **Modbus RTU** from the connection type dropdown
3. Choose the COM port (e.g., `COM3`)
4. Set baud rate (e.g., `9600`)
5. Configure data bits, parity, and stop bits to match your device
6. Click **OK**
7. Go to **Connection → Connect**

### Configuring a Slave Window

1. After connecting, a default slave window appears
2. Go to **Setup → Read/Write Definition...**
3. Configure:
   - **Slave ID**: The Modbus device address (1-247)
   - **Function Code**: Select the appropriate FC (e.g., FC03 for holding registers)
   - **Starting Address**: First register address to read
   - **Quantity**: Number of registers/coils to read
   - **Scan Rate**: Polling interval in milliseconds (default: 1000)
4. Click **OK** — polling begins automatically

### Reading Registers

Once configured, the slave window displays a table with columns:
- **Row**: Sequential row number
- **Address**: Register address (0-based or 40001-style based on View setting)
- **Value**: Raw integer value
- **Formatted**: Value in the selected display format
- **Alias**: User-defined label (double-click to edit)

### Writing Values

- **Double-click** any register row to open the Write Value dialog
- Enter the new value and click **Write**
- For coils (FC01/FC05), enter `0` (OFF) or `1` (ON)
- For registers (FC03/FC06/FC16), enter the integer value

### Display Formats

Change the display format via **View → Display as**:

| Format | Description |
|--------|-------------|
| Signed Int | 16-bit signed integer (-32768 to 32767) |
| Unsigned Int | 16-bit unsigned integer (0 to 65535) |
| Hex | Hexadecimal (e.g., `0x1A2B`) |
| Binary | Binary string (e.g., `0b0001101000101011`) |
| Float ABCD | 32-bit IEEE 754 float, big-endian word order |
| Float CDAB | 32-bit IEEE 754 float, little-endian word order |
| Float BADC | 32-bit IEEE 754 float, byte-swapped big-endian |
| Float DCBA | 32-bit IEEE 754 float, byte-swapped little-endian |
| Double | 64-bit IEEE 754 double |
| ASCII | ASCII string representation |

### Address Display

Toggle between address styles via **View → Address Base**:
- **0-based**: Addresses shown as 0, 1, 2, ...
- **1-based (40001)**: Addresses shown as 40001, 40002, ... (offset depends on FC)

### Traffic Log

- Go to **View → Show Traffic Log** to open the traffic monitor
- Shows timestamp, direction (Tx/Rx), and raw hex bytes for every frame
- Use **Clear** button to reset the log

### Multiple Slave Windows

- Go to **File → New** to create an additional slave window
- Each window can monitor a different slave ID, FC, or address range
- Arrange windows via **Window → Cascade** or **Window → Tile**

### Saving and Loading Configurations

- **File → Save** / **File → Save As**: Save current window layout and settings to a `.json` file
- **File → Open**: Load a previously saved configuration
- Configuration files store connection settings, all slave window definitions, and display preferences

## Function Code Reference

| FC | Name | Description |
|----|------|-------------|
| FC01 | Read Coils | Read output coil status (bit) |
| FC02 | Read Discrete Inputs | Read input status (bit) |
| FC03 | Read Holding Registers | Read output registers (16-bit) |
| FC04 | Read Input Registers | Read input registers (16-bit) |
| FC05 | Write Single Coil | Write one output coil |
| FC06 | Write Single Register | Write one holding register |
| FC15 | Write Multiple Coils | Write multiple output coils |
| FC16 | Write Multiple Registers | Write multiple holding registers |

## Modbus Exception Codes

| Code | Name | Description |
|------|------|-------------|
| 01 | Illegal Function | FC not supported by device |
| 02 | Illegal Data Address | Address out of range |
| 03 | Illegal Data Value | Value out of range |
| 04 | Slave Device Failure | Device internal error |
| 05 | Acknowledge | Command accepted, processing |
| 06 | Slave Device Busy | Device busy, retry later |
| 08 | Memory Parity Error | Memory error detected |
| 0A | Gateway Path Unavailable | Gateway misconfigured |
| 0B | Gateway Target Failed | No response from target |

## Troubleshooting

### Cannot connect via TCP
- Verify the IP address and port are correct
- Ensure no firewall is blocking port 502
- Check that the Modbus device is powered on and reachable (`ping <ip>`)

### Cannot connect via Serial (RTU)
- Ensure the correct COM port is selected (check Device Manager)
- Verify baud rate, data bits, parity, and stop bits match the device
- Check that no other application is using the COM port
- Try enabling RTS/DTR if required by your RS-232/RS-485 converter

### "No Response" / Timeout Errors
- Increase the timeout value in Connection Setup
- Reduce the scan rate (increase the interval)
- Verify the slave ID matches the physical device address

### Garbled Data / Wrong Values
- Check that the byte order / word order matches your device
- Verify the function code is correct for the register type
- Ensure the starting address is correct (some devices use 0-based, others 1-based internally)

### pymodbus Import Error
- Re-run `pip install pymodbus>=3.0.0`
- Ensure you are using the correct Python environment

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Ctrl+N | New slave window |
| Ctrl+O | Open configuration |
| Ctrl+S | Save configuration |
| F5 | Connect |
| F6 | Disconnect |
| F2 | Read/Write Definition |

## License

This software is provided for educational and development purposes. It is a Python implementation inspired by the Modbus Poll commercial product by WinTech A/S.
