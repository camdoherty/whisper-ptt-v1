import logging
import subprocess
import urllib.parse

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Notify', '0.7')
from gi.repository import Gtk, GdkPixbuf, Notify

class TrayIconGTK:
    """Manages the GTK System Tray Icon and notifications."""
    def __init__(self, app_instance, base_dir):
        self.app = app_instance
        self.base_dir = base_dir
        self.icon = Gtk.StatusIcon()
        self.icon.set_property("title", "Whisper PTT")
        self.icon.connect("popup-menu", self.on_right_click)
        Notify.init("Whisper PTT")
        self.notification = Notify.Notification.new("", "", "")
        self.notification.add_action("default", "Open File", self.on_notification_click)
        self.set_state("idle") # Set initial icon

    def on_notification_click(self, notification, action):
        """Callback for when the notification is clicked."""
        logging.info("Notification clicked, opening voice note in Obsidian.")
        try:
            # Deconstruct the path to get the vault and file name
            note_path = self.app.voicenote_file_path
            vault_name = note_path.parent.name

            # URL-encode the components for the Obsidian URI
            encoded_vault = urllib.parse.quote(vault_name)
            # Obsidian URI uses the filename without the extension (.stem)
            encoded_file = urllib.parse.quote(note_path.stem)

            # Construct the Obsidian URI
            obsidian_uri = f"obsidian://open?vault={encoded_vault}&file={encoded_file}"

            logging.info(f"Constructed Obsidian URI: {obsidian_uri}")

            # Use xdg-open to launch the URI
            subprocess.run(["xdg-open", obsidian_uri], check=True)
        except FileNotFoundError:
            logging.error("`xdg-open` command not found. Cannot open Obsidian URI.")
        except Exception as e:
            logging.error(f"Failed to open Obsidian URI: {e}")

    def show_notification(self, title: str, body: str):
        """Displays a desktop notification."""
        self.notification.update(title, body)
        self.notification.set_timeout(5000) # 5 seconds
        self.notification.show()

    def set_state(self, state: str):
        """Updates the icon and tooltip based on the application state."""
        icon_map = {
            "idle": "icon-idle.png",
            "recording": "icon-rec.png",
            "processing": "icon-proc.png",
            "error": "icon-error.png",
        }
        tooltip_map = {
            "idle": "Whisper PTT (Idle)",
            "recording": "Whisper PTT (Recording...)",
            "processing": "Whisper PTT (Processing...)",
            "error": "Whisper PTT (Error: Audio device unavailable)",
        }
        icon_name = icon_map.get(state, "icon-idle.png")
        icon_path = self.base_dir / icon_name
        try:
            # GdkPixbuf is the native way to load images for GTK icons.
            # This correctly handles RGBA transparency.
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(str(icon_path))
            self.icon.set_property("pixbuf", pixbuf)
            self.icon.set_property("tooltip-text", tooltip_map.get(state, "Whisper PTT"))
            self.icon.set_property("visible", True)
        except gi.repository.GLib.Error as e:
            logging.warning(f"Could not load icon '{icon_path}': {e.message}. Tray icon not updated.")

    def on_right_click(self, icon, button, time):
        menu = Gtk.Menu()
        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", self.app.stop)
        menu.append(quit_item)
        menu.show_all()
        menu.popup(None, None, None, None, button, time)

    def run(self):
        """Starts the GTK main loop. This is a blocking call."""
        Gtk.main()

    def stop(self):
        """Stops the GTK main loop."""
        Gtk.main_quit()
