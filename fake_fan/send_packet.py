#!/usr/bin/env python3
"""Send a single UDP command to the fake fan server - useful for quick testing."""
# ruff: noqa: T201

import argparse
import socket


def send_command(host: str, port: int, packet_hex: str):
    """Send a hex packet to the fan server."""
    print(f"Sending to {host}:{port}")
    print(f"Packet: {packet_hex}")
    print(f"Length: {len(packet_hex) // 2} bytes\n")

    packet_data = bytes.fromhex(packet_hex)

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(2)
        sock.sendto(packet_data, (host, port))

        try:
            result_data, server = sock.recvfrom(4096)
            result_hex = result_data.hex().upper()
            print(f"Response from {server[0]}:{server[1]}")
            print(f"Packet: {result_hex}")
            print(f"Length: {len(result_data)} bytes")
            return result_hex
        except TimeoutError:
            print("No response (timeout)")
            return None


def main():
    """Run manual packet sender."""
    parser = argparse.ArgumentParser(
        description="Send raw UDP packets to the fake fan server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Read device type (auth: ID=1234567890123456, password=1234)
  %(prog)s FDFD02103132333435363738393031323334353637383930043132333401B906ED

  # Turn fan ON
  %(prog)s FDFD021031323334353637383930313233343536373839300431323334030101013F

  # Set speed to 5
  %(prog)s FDFD0210313233343536373839303132333435363738393004313233340302050248

Note: Packets must include valid authentication and checksum.
        """,
    )
    parser.add_argument("packet", help="Hex packet to send (no spaces)")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Target host (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=4000, help="Target port (default: 4000)"
    )

    args = parser.parse_args()

    # Remove spaces and make uppercase
    packet = args.packet.replace(" ", "").upper()

    send_command(args.host, args.port, packet)


if __name__ == "__main__":
    main()
