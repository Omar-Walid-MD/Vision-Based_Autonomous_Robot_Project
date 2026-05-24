#!/usr/bin/env python3
"""
main.py - Entry point for the Peripherals Node.

Vision-Based Autonomous Hospital Assistant Robot

Run in mock mode on laptop:
    python3 main.py --mock

Run on Raspberry Pi:
    python3 main.py --server http://127.0.0.1:5000
"""

from dotenv import load_dotenv
load_dotenv()

import argparse
import logging
import sys

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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    node = PeripheralsNode(server_url=args.server, mock=args.mock)
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