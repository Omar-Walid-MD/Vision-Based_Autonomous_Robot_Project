#!/usr/bin/env python3
"""
main.py - Entry point for the Peripherals Node.

Vision-Based Autonomous Hospital Assistant Robot

Run in mock mode on laptop:
    python3 main.py --mock

Run on Raspberry Pi:
    python3 main.py --server http://127.0.0.1:5000

Disable specific hardware:
    python3 main.py --no-vital      # Skip MLX90614 + MAX30102
    python3 main.py --no-lcd        # Skip I2C LCD screen
    python3 main.py --no-servo      # Skip PCA9685 + all servos
"""

import argparse
import logging
import sys

from config import PeripheralsConfig
from vital_sensors import VitalSensorsReader
from peripherals_node import PeripheralsNode
 
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Raspberry Pi Peripherals Node")
    parser.add_argument(
        "--server", default="http://127.0.0.1:5000", help="Socket.IO server URL"
    )
    parser.add_argument(
        "--mock", action="store_true", help="Run without hardware for testing"
    )
    parser.add_argument(
        "--log-level", default="INFO", help="DEBUG, INFO, WARNING, ERROR"
    )
    parser.add_argument(
        "--no-vital", action="store_true", help="Disable vital sensors (MLX90614, MAX30102)"
    )
    parser.add_argument(
        "--no-lcd", action="store_true", help="Disable LCD screen"
    )
    parser.add_argument(
        "--no-servo", action="store_true", help="Disable servo driver and all servo controllers"
    )
    parser.add_argument(
        "--debug-vitals", action="store_true",
        help="Print continuous real-time vital sensor readings to console and exit"
    )
    return parser.parse_args()



def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
 
    # --debug-vitals: bypass the full node, run a tight sensor debug loop
    if args.debug_vitals:
        vitals = VitalSensorsReader(PeripheralsConfig(), mock=args.mock)
        try:
            vitals.debug_loop()
        except KeyboardInterrupt:
            print("\nDebug stopped.")
        # ~ return 0
 
    node = PeripheralsNode(
        server_url=args.server,
        mock=args.mock,
        no_vital=args.no_vital,
        no_lcd=args.no_lcd,
        no_servo=args.no_servo,
    )
    try:
        node.loop()
    except KeyboardInterrupt:
        logging.info("Stopping peripherals node...")
    except Exception as exc:
        logging.exception("Peripherals node crashed: %s", exc)
        return 1
    finally:
        node.shutdown()
    return 0
 
 
if __name__ == "__main__":
    sys.exit(main())
