# Fake Siku Fan Server

This script simulates a Siku fan controller for testing purposes. It implements the UDP protocol used by real Siku fans, allowing you to test the Home Assistant integration without physical hardware.

## Quick Start

**Start the server:**
```bash
python fake_fan/fake_fan_server.py
```

**Test it works:**
```bash
python fake_fan/test_fake_fan.py
```

That's it! The fake fan is now running and responding to commands.

## Features

- ✅ Full protocol implementation (read, write, read-write commands)
- ✅ Simulates fan state (on/off, speed, direction, etc.)
- ✅ Verbose logging of all traffic
- ✅ Configurable device ID and password
- ✅ Supports all fan commands (speed, direction, boost, modes, etc.)

## Usage

### Basic Usage

Run with default settings (listens on `0.0.0.0:4000`, ID: `1234567890123456`, Password: `1234`):

```bash
python fake_fan/fake_fan_server.py
```

### Custom Configuration

```bash
python fake_fan/fake_fan_server.py \
  --host 0.0.0.0 \
  --port 4000 \
  --id "mydevice123456789012" \
  --password "secret"
```

### With Debug Logging

```bash
python fake_fan/fake_fan_server.py --debug
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `0.0.0.0` | Host/IP address to bind to |
| `--port` | `4000` | UDP port to listen on |
| `--id` | `1234567890123456` | Device ID (20 characters) |
| `--password` | `1234` | Device password |
| `--debug` | `False` | Enable debug logging |

## Using with Home Assistant

1. Start the fake fan server:
   ```bash
   python fake_fan/fake_fan_server.py
   ```

2. In Home Assistant, add the Siku integration with these settings:
   - Host: `localhost` (or your server IP)
   - Port: `4000`
   - Device ID: `1234567890123456`
   - Password: `1234`

3. The fake fan will appear in Home Assistant and respond to all commands!

## Example Output

When you interact with the fan through Home Assistant, you'll see detailed logs:

```
============================================================
RECEIVED: FDFD02103132333435363738393031323334353637383930043132333401B9
Length: 31 bytes
✓ Checksum verified
✓ Authentication successful
Function: 01
Command: READ
RESPONSE: FDFD02103132333435363738393031323334353637383930043132333406B901
Length: 32 bytes
============================================================
```

## Simulated Fan State

The fake fan maintains the following state:

- **Power**: On/Off
- **Speed**: 1-10 (preset speeds)
- **Manual Speed**: 0-255 (fine control)
- **Direction**: Forward, Reverse, Alternating
- **Boost Mode**: Enabled/Disabled
- **Mode**: Auto, Sleep, Party
- **Humidity**: Current humidity (simulated at 45%)
- **RPM**: Fan speed in RPM (simulated at 1200)
- **Filter Timer**: Time since filter change
- **Countdown Timer**: Active countdown timer
- **Alarm**: Filter alarm status
- **Firmware**: Version 2.5

## Commands Supported

All Siku protocol commands are supported:

- Power on/off/toggle
- Speed control (preset 1-10)
- Manual speed control (0-255)
- Direction control
- Boost mode
- Sleep/Party modes
- Timer control
- Filter reset
- Status queries
- And more...

## Development

The server logs all incoming packets and responses, making it easy to:

1. Debug protocol issues
2. Verify packet format
3. Test edge cases
4. Develop new features

## Tools Included

### `fake_fan_server.py`
The main fake fan server that simulates a real Siku fan controller.

### `test_fake_fan.py`
Automated test script that exercises all fan commands. Great for verifying the server works.

```bash
python fake_fan/test_fake_fan.py
```

### `send_packet.py`
Send raw UDP packets for low-level testing:

```bash
# Read device type
python fake_fan/send_packet.py FDFD02103132333435363738393031323334353637383930043132333401B906ED

# Turn fan ON
python fake_fan/send_packet.py FDFD021031323334353637383930313233343536373839300431323334030101013F
```

## Documentation

- **`README.md`** (this file) - Overview and usage
- **`TESTING_GUIDE.md`** - Comprehensive testing guide with examples

## Notes

- The server uses UDP (like real Siku fans)
- Authentication is enforced (device ID + password must match)
- Checksums are verified on all packets
- All protocol functions are implemented (READ, WRITE, READ_WRITE, INC, DEC)
