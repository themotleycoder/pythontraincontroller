import asyncio
from bleak import BleakClient, BleakScanner
import logging
import sys
import tty
import termios
import sys
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TrainHub:
    def __init__(self):
        self._client = None
        self.connected = False
        self.current_speed = 0

    async def connect(self):
        try:
            logger.info("Scanning for Train Hub...")
            async with BleakScanner() as scanner:
                devices = await scanner.discover()
                device = None
                for d in devices:
                    if d.name and "HUB" in d.name.upper():
                        device = d
                        logger.info(f"Found Train Hub: {d.name}")
                        break
                        
            if not device:
                raise Exception("Could not find Train Hub")

            self._client = BleakClient(device)
            await self._client.connect()
            self.connected = True
            logger.info(f"Connected to hub: {device.name}")

            await self._client.start_notify(
                "00001624-1212-efde-1623-785feabcd123",
                self._notification_handler
            )
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Error connecting to hub: {str(e)}")
            raise

    async def disconnect(self):
        if self._client and self._client.is_connected:
            await self.stop()
            await self._client.disconnect()
            self.connected = False
            logger.info("Disconnected from hub")

    async def _notification_handler(self, sender, data):
        logger.debug(f"Received notification: {' '.join([f'{b:02x}' for b in data])}")

    async def set_speed(self, speed: int):
        """
        Set the train's speed
        :param speed: Speed from -100 to 100 (negative values for reverse)
        """
        try:
            if not -100 <= speed <= 100:
                raise ValueError("Speed must be between -100 and 100")

            # Convert speed to power value
            if speed < 0:
                power = min(abs(speed), 100)
                power += 128  # Add 128 for reverse direction
            else:
                power = min(speed, 100)

            command = bytes([
                0x08,   # Length
                0x00,   # Hub ID
                0x81,   # Output command
                0x00,   # Port 0
                0x11,   # Execute immediately
                0x51,   # Write direct mode
                0x01,   # Mode
                power   # Speed value
            ])
            
            self.current_speed = speed
            print(f"\rSpeed: {speed}%   ", end='', flush=True)
            
            await self._client.write_gatt_char(
                "00001624-1212-efde-1623-785feabcd123",
                command,
                response=True
            )
            await asyncio.sleep(0.1)
            
        except Exception as e:
            logger.error(f"Error setting speed: {e}")

    async def stop(self):
        """Stop the train"""
        await self.set_speed(0)

    async def increase_speed(self, increment=10):
        """Increase speed by increment"""
        new_speed = min(100, self.current_speed + increment)
        await self.set_speed(new_speed)

    async def decrease_speed(self, decrement=10):
        """Decrease speed by decrement"""
        new_speed = max(-100, self.current_speed - decrement)
        await self.set_speed(new_speed)

    async def reverse_direction(self):
        """Reverse the train's direction"""
        await self.set_speed(-self.current_speed)

def get_key():
    """Get a single keypress from the user"""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

async def process_key(train, key):
    """Process a single keypress"""
    if key in ['w', 'W', 'A']:  # Up
        await train.increase_speed()
    elif key in ['s', 'S', 'B']:  # Down
        await train.decrease_speed()
    elif key == ' ':  # Space
        await train.stop()
    elif key in ['r', 'R']:  # Reverse
        await train.reverse_direction()
    elif key in ['q', 'Q']:  # Quit
        return False
    return True

async def main():
    train = TrainHub()
    try:
        await train.connect()
        
        print("""
Train Controls:
--------------
W: Increase speed
S: Decrease speed
Space: Stop
R: Reverse direction
Q: Quit
        """)
        
        while True:
            key = get_key()
            if not await process_key(train, key):
                break
                
    except Exception as e:
        logger.error(f"Error: {str(e)}")
    finally:
        if train.connected:
            await train.stop()
            await train.disconnect()
        print("\nDisconnected from train.")

if __name__ == "__main__":
    # Check if running on Windows
    if os.name == 'nt':
        print("This script requires a Unix-like environment (Mac/Linux).")
        print("Please use the administrator version for Windows.")
        sys.exit(1)
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(0)