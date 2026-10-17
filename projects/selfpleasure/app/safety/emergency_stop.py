"""Independent terminal stop command for Intiface Central."""

import asyncio
import sys

from buttplug import ButtplugClient

from app.config import settings


async def stop_from_terminal() -> None:
    client = ButtplugClient("SelfPleasure Emergency Stop")
    try:
        await asyncio.wait_for(client.connect(settings.intiface_url), timeout=5)
        await asyncio.wait_for(client.stop_all_devices(), timeout=3)
        print("Emergency stop sent to Intiface Central.")
    finally:
        if client.connected:
            await asyncio.wait_for(client.disconnect(), timeout=5)


def main() -> None:
    try:
        asyncio.run(stop_from_terminal())
    except Exception as exc:
        print(f"Emergency stop could not be confirmed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
