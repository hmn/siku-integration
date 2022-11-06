"""Constants for the Siku RV Fan integration."""

DOMAIN = "siku"
DEFAULT_MANUFACTURER = "Siku"
DEFAULT_MODEL = "RV"
DEFAULT_NAME = "Fan"
DEFAULT_PORT = 4000

PACKET_PREFIX = bytes.fromhex("6d6f62696c65")
PACKET_POSTFIX = bytes.fromhex("0d0a")
