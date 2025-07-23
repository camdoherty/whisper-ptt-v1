# test_tray.py
import pystray
from PIL import Image
import sys

# This script tests the core functionality of displaying a transparent
# RGBA image in the system tray using pystray.

ICON_FILE = "icon-idle.png"

try:
    # Load the image and explicitly convert to RGBA
    image = Image.open(ICON_FILE).convert("RGBA")
    print(f"Successfully loaded '{ICON_FILE}'. Image mode: {image.mode}")

except FileNotFoundError:
    print(f"FATAL: Icon file '{ICON_FILE}' not found. Please place it in the same directory.")
    sys.exit(1)

def on_quit(icon, item):
    icon.stop()

# Create a simple menu with a quit button
menu = pystray.Menu(pystray.MenuItem('Quit', on_quit))

# Create and run the icon
icon = pystray.Icon("test_icon", image, "Test Tray Icon", menu)

print("Displaying icon. Check your system tray. Press Ctrl+C in this terminal to exit.")
icon.run()