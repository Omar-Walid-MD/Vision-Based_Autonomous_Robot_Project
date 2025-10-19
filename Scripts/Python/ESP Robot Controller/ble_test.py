import asyncio
from bleak import BleakClient, BleakScanner

SERVICE_UUID = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
RX_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  # write
TX_UUID = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # notify

DEVICE_NAME = "ESP32_BLE"


async def main():
    print("🔍 Scanning for ESP32_BLE...")
    devices = await BleakScanner.discover(timeout=5)
    target = None

    for d in devices:
        if d.name:
            if DEVICE_NAME in d.name:
                target = d
                break

    if not target:
        print("❌ ESP32_BLE not found. Make sure it's powered and advertising.")
        return

    print(f"✅ Found {target.name} ({target.address})")
    async with BleakClient("80:65:99:DF:4C:89") as client:
        print("🔗 Connected to ESP32_BLE")

        # Set up notification handler
        def handle_rx(_, data: bytearray):
            print("📩 Received:", data.decode().strip())

        await client.start_notify(TX_UUID, handle_rx)

        print("✅ Notifications started. Type 'exit' to quit.")
        print("Type '1' or '0' to control LED.\n")

        while True:
            cmd = input(">>> ").strip()
            if cmd.lower() == "exit":
                break
            if not cmd:
                continue
            await client.write_gatt_char(RX_UUID, cmd.encode())

        await client.stop_notify(TX_UUID)
        print("🔌 Disconnected.")


if __name__ == "__main__":
    asyncio.run(main())
