#!/usr/bin/env python3
"""Quick test script to verify the fake fan server works."""
# ruff: noqa: T201

import asyncio
import sys
from pathlib import Path

# Add the custom_components directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "custom_components"))

from siku.api_v2 import SikuV2Api


async def test_fan_server():
    """Test the fake fan server."""
    print("Testing Fake Fan Server")
    print("=" * 60)

    # Create API client
    api = SikuV2Api(
        host="127.0.0.1", port=4000, idnum="1234567890123456", password="1234"
    )

    try:
        # Test 1: Get status
        print("\n1. Getting initial status...")
        status = await api.status()
        print(f"   ✓ Power: {'ON' if status['is_on'] else 'OFF'}")
        print(f"   ✓ Speed: {status['speed']}")
        print(f"   ✓ Direction: {status['direction']}")
        print(f"   ✓ Humidity: {status['humidity']}%")
        print(f"   ✓ RPM: {status['rpm']}")

        # Test 2: Turn on
        print("\n2. Turning fan ON...")
        status = await api.power_on()
        print(f"   ✓ Power: {'ON' if status['is_on'] else 'OFF'}")

        # Test 3: Set speed
        print("\n3. Setting speed to 2...")
        status = await api.speed("02")
        print(f"   ✓ Speed: {status['speed']}")

        # Test 4: Set manual speed to 50%
        print("\n4. Setting manual speed to 50%...")
        status = await api.speed_manual(50)
        print(
            f"   ✓ Manual speed: {status['manual_speed']}/255 ({status['manual_speed'] / 255 * 100:.1f}%)"
        )

        # Test 5: Set direction to reverse
        print("\n5. Setting direction to reverse...")
        status = await api.direction("01")
        print(f"   ✓ Direction: {status['direction']}")

        # Test 6: Enable sleep mode
        print("\n6. Enabling sleep mode...")
        status = await api.sleep()
        print(f"   ✓ Mode: {status['mode']}")

        # Test 7: Turn off
        print("\n7. Turning fan OFF...")
        status = await api.power_off()
        print(f"   ✓ Power: {'ON' if status['is_on'] else 'OFF'}")

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("\nThe fake fan server is working correctly.")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nMake sure the fake fan server is running:")
        print("  python scripts/fake_fan_server.py")
        return False

    return True


if __name__ == "__main__":
    success = asyncio.run(test_fan_server())
    sys.exit(0 if success else 1)
