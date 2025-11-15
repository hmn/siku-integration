# Testing the Fake Siku Fan Server

## Quick Start

### 1. Start the Fake Fan Server

In one terminal:

```bash
python fake_fan/fake_fan_server.py
```

You should see:

```
2025-11-08 16:20:23,598 - INFO - Fake fan controller initialized
2025-11-08 16:20:23,598 - INFO -   Device ID: 1234567890123456
2025-11-08 16:20:23,598 - INFO -   Password: 1234
2025-11-08 16:20:23,598 - INFO -
============================================================
2025-11-08 16:20:23,598 - INFO - Fake Siku Fan Server Started
2025-11-08 16:20:23,598 - INFO - Listening on 0.0.0.0:4000
2025-11-08 16:20:23,598 - INFO - ============================================================

2025-11-08 16:20:23,598 - INFO - Waiting for commands...
```

### 2. Run the Test Script

In another terminal:

```bash
python fake_fan/test_fake_fan.py
```

This will execute a series of test commands against the fake fan server.

### 3. Use with Home Assistant

Start Home Assistant (if not already running):

```bash
scripts/develop
```

Then add the Siku integration in the UI with these credentials:
- **Host**: `localhost`
- **Port**: `4000`
- **Device ID**: `1234567890123456`
- **Password**: `1234`

## What You'll See

When you interact with the fan through Home Assistant or the test script, the fake fan server will log all traffic:

```
============================================================
Connection from: 127.0.0.1:52134
============================================================
RECEIVED: FDFD02103132333435363738393031323334353637383930043132333401B9020244B74A6483860B2564
Length: 40 bytes
✓ Checksum verified
✓ Authentication successful
Function: 01
Command: READ
RESPONSE: FDFD02103132333435363738393031323334353637383930043132333406B9010203804A48250C...
Length: 50 bytes
============================================================

============================================================
Connection from: 127.0.0.1:52135
============================================================
RECEIVED: FDFD021031323334353637383930313233343536373839300431323334030101
Length: 33 bytes
✓ Checksum verified
✓ Authentication successful
Function: 03
Command: READ_WRITE
✓ Fan turned ON
RESPONSE: FDFD0210313233343536373839303132333435363738393004313233340601013F
Length: 34 bytes
============================================================
```

## Traffic Legend

Each transaction shows:

1. **Connection Info**: Source IP and port
2. **Received Packet**: The raw hex packet received
3. **Verification**: Checksum and authentication status
4. **Function**: The command type (READ, WRITE, READ_WRITE, etc.)
5. **Action**: What the server did (turned on, changed speed, etc.)
6. **Response**: The response packet sent back (if any)

## Protocol Functions

The fake fan server supports all protocol functions:

### READ (0x01)
Read current state without changing anything.

### WRITE (0x02)
Change state, no response sent.

### READ_WRITE (0x03)
Change state and return new state.

### INCREMENT (0x04)
Increment a value (speed, etc.)

### DECREMENT (0x05)
Decrement a value (speed, etc.)

## Simulated State

The fake fan maintains realistic state:

- **Power**: On/Off (starts OFF)
- **Speed**: 1-10 preset speeds (starts at 3)
- **Manual Speed**: 0-255 (starts at 128 = 50%)
- **Direction**: Forward/Reverse/Alternating (starts Forward)
- **Boost**: On/Off (starts OFF)
- **Mode**: Auto/Sleep/Party (starts Auto)
- **Humidity**: 45% (simulated sensor)
- **RPM**: 1200 (simulated)
- **Filter Timer**: Tracks minutes since last reset
- **Countdown Timer**: Active countdown in seconds
- **Alarm**: Filter alarm status
- **Firmware**: Version 2.5

## Debugging Tips

### Enable Debug Mode

For more detailed logging:

```bash
python fake_fan/fake_fan_server.py --debug
```

### Watch Traffic in Real-Time

You can run the server and see all packets as they come in:

```bash
python fake_fan/fake_fan_server.py | grep -E "RECEIVED|RESPONSE|✓"
```

### Test Specific Commands

You can write your own test scripts by importing the API:

```python
from custom_components.siku.api_v2 import SikuV2Api

api = SikuV2Api(
    host="127.0.0.1",
    port=4000,
    idnum="1234567890123456",
    password="1234"
)

# Test commands
await api.power_on()
await api.speed("07")
await api.direction("02")  # alternating
```

## Custom Configuration

### Different Port

```bash
python fake_fan/fake_fan_server.py --port 5000
```

Then configure Home Assistant to use port 5000.

### Custom Credentials

```bash
python fake_fan/fake_fan_server.py \
  --id "mydevice123456789012" \
  --password "secret123"
```

Then use these credentials in Home Assistant.

### Multiple Fans

You can run multiple fake fans on different ports:

Terminal 1:
```bash
python fake_fan/fake_fan_server.py --port 4000 --id "bedroom123456789012"
```

Terminal 2:
```bash
python fake_fan/fake_fan_server.py --port 4001 --id "living123456789012"
```

Then add two separate integrations in Home Assistant.

## Troubleshooting

### Connection Refused

Make sure the fake fan server is running and listening on the correct port.

### Authentication Failed

Check that the Device ID and Password match exactly (case-sensitive).

### No Response

WRITE commands don't send responses - this is normal. Use READ_WRITE if you need confirmation.

### Port Already in Use

Change the port:
```bash
python fake_fan/fake_fan_server.py --port 4001
```

## Integration with Home Assistant

Once configured in Home Assistant, you can:

1. **View the fan entity** in the UI
2. **Control power** (on/off)
3. **Set speed** (1-10 or percentage)
4. **Change direction** (forward/reverse)
5. **Enable oscillation** (alternating mode)
6. **Activate preset modes** (sleep/party)
7. **View humidity** sensor
8. **Monitor RPM** sensor
9. **Check filter status** and reset

All changes will be logged in the fake fan server terminal!

## Files Created

- **`fake_fan/fake_fan_server.py`** - The main fake fan server
- **`fake_fan/test_fake_fan.py`** - Test script to verify functionality
- **`fake_fan/README.md`** - Documentation for the fake fan server
- **`fake_fan/TESTING_GUIDE.md`** - This guide

## Next Steps

1. Start the fake fan server
2. Run the test script to verify it works
3. Add it to Home Assistant
4. Test all fan controls in the UI
5. Watch the traffic logs to understand the protocol
6. Develop and test new features without hardware!
