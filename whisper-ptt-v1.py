#!/usr/bin/env python3
#
# whisper-ptt-v1.3.py
#
# This version replaces the pystray library with a native GTK system tray icon
# using PyGObject. This provides a robust and visually correct icon on Linux
# desktops like XFCE, GNOME, and MATE, solving rendering issues.
#
# Author: Your Name/Handle
# Version: 1.3
# Date: 2024-05-22

import collections
import datetime
import logging
import os
import pathlib
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass, field

import numpy as np
import sounddevice as sd
import tomli
from faster_whisper import WhisperModel
from pynput import keyboard

# Attempt to import GTK libraries, which are now required for the UI.
try:
    import gi
    gi.require_version('Gtk', '3.0')
    gi.require_version('Notify', '0.7')
    from gi.repository import Gtk, GdkPixbuf, GLib, Notify
except ImportError:
    print("FATAL: PyGObject is not installed. Please install it to use the GTK interface.")
    print("On Debian/Ubuntu: sudo apt-get install libgirepository1.0-dev libcairo2-dev && pip install PyGObject")
    sys.exit(1)

# (Configuration dataclasses and loading function remain the same as v1.1)
# ... [ dataclasses and load_or_create_config are here ] ...

#region Configuration Loading
@dataclass
class AudioConfig:
    device: str | int | None = None
    sample_rate: int = 16000
    block_duration_ms: int = 30
    ring_buffer_duration_s: float = 3.0
    pre_roll_s: float = 0.7
    post_roll_s: float = 0.3

@dataclass
class ModelConfig:
    path: str = "models/faster-whisper-medium.en-int8/"
    compute_type: str = "int8_float32"
    device: str = "cuda"
    beam_size: int = 5
    repetition_penalty: float = 1.2
    log_prob_threshold: float | None = -1.0
    vad_min_silence_ms: int = 500

@dataclass
class UIConfig:
    hotkeys: list[str] = field(default_factory=lambda: ["ctrl_r", "shift_r"])
    hotkey_voicenote: list[str] = field(default_factory=lambda: ["ctrl_r", "alt_r"])
    voicenote_file: str = "~/ObsidianVault/🎙️VoiceNotes.md"
    enable_audio_cues: bool = True

@dataclass
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    ui: UIConfig = field(default_factory=UIConfig)


def load_or_create_config(path: str = "config.toml") -> AppConfig:
    config_path = pathlib.Path(path)
    if not config_path.exists():
        logging.info(f"Config file not found. Creating a default '{path}'.")
        default_config_str = f"""
[audio]
device = "default"
sample_rate = 16000

[model]
path = "models/faster-whisper-medium.en-int8/"
compute_type = "int8_float32"
device = "cuda"

[ui]
hotkeys = ["ctrl_r", "shift_r"]
hotkey_voicenote = ["ctrl_r", "alt_r"]
voicenote_file = "~/ObsidianVault/🎙️VoiceNotes.md"
enable_audio_cues = true
"""
        config_path.write_text(default_config_str.strip())
    with open(config_path, "rb") as f:
        toml_data = tomli.load(f)
    app_conf = AppConfig()
    app_conf.audio = AudioConfig(**toml_data.get("audio", {}))
    app_conf.model = ModelConfig(**toml_data.get("model", {}))
    app_conf.ui = UIConfig(**toml_data.get("ui", {}))
    return app_conf
#endregion

class TrayIconGTK:
    """Manages the GTK System Tray Icon and notifications."""
    def __init__(self, app_instance):
        self.app = app_instance
        self.icon = Gtk.StatusIcon()
        self.icon.set_title("Whisper PTT")
        self.icon.connect("popup-menu", self.on_right_click)
        Notify.init("Whisper PTT")
        self.notification = Notify.Notification.new("", "", "")
        self.notification.add_action("default", "Open File", self.on_notification_click)
        self.set_state("idle") # Set initial icon

    def on_notification_click(self, notification, action):
        """Callback for when the notification is clicked."""
        logging.info("Notification clicked, opening voice note file.")
        try:
            # Use xdg-open for broad desktop environment compatibility on Linux.
            subprocess.run(["xdg-open", str(self.app.voicenote_file_path)], check=True)
        except FileNotFoundError:
            logging.error("`xdg-open` command not found. Cannot open file.")
        except Exception as e:
            logging.error(f"Failed to open voice note file: {e}")

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
        }
        tooltip_map = {
            "idle": "Whisper PTT (Idle)",
            "recording": "Whisper PTT (Recording...)",
            "processing": "Whisper PTT (Processing...)",
        }
        icon_path = icon_map.get(state, "icon-idle.png")
        try:
            # GdkPixbuf is the native way to load images for GTK icons.
            # This correctly handles RGBA transparency.
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(icon_path)
            self.icon.set_from_pixbuf(pixbuf)
            self.icon.set_tooltip_text(tooltip_map.get(state, "Whisper PTT"))
            self.icon.set_visible(True)
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

class WhisperPTT:
    """The main application class."""
    def __init__(self, config: AppConfig):
        global CONFIG
        CONFIG = config
        # ... (most of the __init__ from v1.1 is identical) ...
        self.state = "idle"  # idle, recording, recording_voicenote, processing
        self.shutdown_event = threading.Event()
        self._lock = threading.Lock()
        self.voicenote_file_path = pathlib.Path(os.path.expanduser(CONFIG.ui.voicenote_file))
        
        self.audio_thread = None
        self.keyboard_listener = None
        
        self.block_size = int(CONFIG.audio.sample_rate * CONFIG.audio.block_duration_ms / 1000)
        ring_buffer_frames = int(CONFIG.audio.ring_buffer_duration_s * CONFIG.audio.sample_rate)
        self.ring_buffer_blocks = ring_buffer_frames // self.block_size + 1
        self.pre_roll_blocks = int(CONFIG.audio.pre_roll_s * CONFIG.audio.sample_rate) // self.block_size
        self.post_roll_frames = int(CONFIG.audio.post_roll_s * CONFIG.audio.sample_rate)
        
        self.ring_buffer = collections.deque(maxlen=self.ring_buffer_blocks)
        self.capture_buffer: list[np.ndarray] = []

        # Dependencies
        self.model = self._load_model()
        self.keyboard_controller = keyboard.Controller()
        self.hotkeys = self._parse_hotkeys(CONFIG.ui.hotkeys)
        self.hotkeys_voicenote = self._parse_hotkeys(CONFIG.ui.hotkey_voicenote)
        self.pressed_keys = set()
        self.beep_start = self._create_beep(freq=440, duration_ms=50)
        self.beep_stop = self._create_beep(freq=880, duration_ms=50)

        # NEW: Instantiate the GTK Tray Icon
        self.tray = TrayIconGTK(self)

    # ... (all helper methods like _load_model, _parse_hotkey, _create_beep, etc., are identical) ...
    #region Helper Methods
    def _load_model(self) -> WhisperModel:
        model_path = pathlib.Path(CONFIG.model.path)
        if not model_path.exists(): logging.fatal(f"Model dir not found: {model_path}"); sys.exit(1)
        logging.info("Loading Whisper model...")
        model = WhisperModel(str(model_path), device=CONFIG.model.device, compute_type=CONFIG.model.compute_type)
        logging.info(f"Model '{model_path.name}' loaded.")
        return model

    def _parse_hotkeys(self, key_strs: list[str]) -> set:
        keys = set()
        for key_str in key_strs:
            key_str = key_str.lower()
            # Handle special keys from pynput
            if hasattr(keyboard.Key, key_str):
                keys.add(getattr(keyboard.Key, key_str))
            # Handle regular character keys
            elif len(key_str) == 1:
                keys.add(keyboard.KeyCode.from_char(key_str))
            else:
                logging.warning(f"Invalid hotkey '{key_str}' in config. Ignoring.")
        return keys

    def _create_beep(self, freq: int, duration_ms: int) -> np.ndarray:
        samples = int(duration_ms / 1000 * CONFIG.audio.sample_rate)
        t = np.linspace(0, duration_ms / 1000, samples, False)
        return 0.2 * np.sin(freq * 2 * np.pi * t).astype(np.float32)
    #endregion

    def _play_sound(self, sound_array: np.ndarray):
        if CONFIG.ui.enable_audio_cues:
            threading.Thread(target=sd.play, args=(sound_array, CONFIG.audio.sample_rate), daemon=True).start()

    def _update_state(self, new_state: str):
        if self.state == new_state: return
        self.state = new_state
        logging.info(f"State changed to: {self.state}")
        # Schedule the UI update on the main GTK thread
        GLib.idle_add(self.tray.set_state, self.state)

    def _process_transcription(self, audio_data: np.ndarray, to_file: bool = False):
        try:
            segments, _ = self.model.transcribe(
                audio_data, language="en", beam_size=CONFIG.model.beam_size,
                repetition_penalty=CONFIG.model.repetition_penalty,
                log_prob_threshold=CONFIG.model.log_prob_threshold,
                vad_filter=True, vad_parameters=dict(min_silence_duration_ms=CONFIG.model.vad_min_silence_ms),
            )
            full_text = " ".join(s.text.strip() for s in segments).strip()
            if full_text:
                logging.info(f"-> Transcribed: '{full_text}'")
                if to_file:
                    self._write_to_voicenote_file(full_text)
                else:
                    self.keyboard_controller.type(full_text)
        except Exception as e:
            logging.error(f"Transcription failed: {e}")
        finally:
            self._update_state("idle")

    # ... (_on_press, _on_release, _audio_worker are identical to v1.1) ...
    #region Event Handlers & Workers
    def _audio_callback(self, indata, frames, time_info, status):
        if status: logging.warning(f"PortAudio status: {status}")
        audio_chunk = indata.flatten().astype(np.float32) / 32768.0
        self.ring_buffer.append(audio_chunk)
        if self.state in ["recording", "recording_voicenote"]:
            self.capture_buffer.append(audio_chunk)

    def _write_to_voicenote_file(self, text: str):
        """Appends a formatted transcription to the voice note file."""
        try:
            self.voicenote_file_path.parent.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            formatted_line = f"__{timestamp}__\n{text}\n\n"
            with open(self.voicenote_file_path, "a", encoding="utf-8") as f:
                f.write(formatted_line)
            logging.info(f"Appended to {self.voicenote_file_path}")
            GLib.idle_add(self.tray.show_notification, f"Note Saved to {self.voicenote_file_path.name}", text)
        except Exception as e:
            logging.error(f"Failed to write to voice note file: {e}")

    def _on_press(self, key):
        # Add the pressed key to our set
        if isinstance(key, keyboard.Key) or isinstance(key, keyboard.KeyCode):
            self.pressed_keys.add(key)

        with self._lock:
            if self.state != "idle": return
            
            # Check for type-out hotkey combo
            if self.hotkeys.issubset(self.pressed_keys):
                self._update_state("recording")
                self._play_sound(self.beep_start)
                self.capture_buffer.clear()
                self.capture_buffer.extend(list(self.ring_buffer)[-self.pre_roll_blocks:])
            
            # Check for voice note hotkey combo
            elif self.hotkeys_voicenote.issubset(self.pressed_keys):
                self._update_state("recording_voicenote")
                self._play_sound(self.beep_start)
                self.capture_buffer.clear()
                self.capture_buffer.extend(list(self.ring_buffer)[-self.pre_roll_blocks:])

    def _on_release(self, key):
        # Determine which hotkey was active, if any
        was_recording_type = self.state == "recording" and key in self.hotkeys
        was_recording_voicenote = self.state == "recording_voicenote" and key in self.hotkeys_voicenote

        if was_recording_type or was_recording_voicenote:
            with self._lock:
                # Check again to prevent race conditions
                if self.state not in ["recording", "recording_voicenote"]: return
                self._update_state("processing")
            
            self._play_sound(self.beep_stop)
            post_roll_silence = np.zeros(self.post_roll_frames, dtype=np.float32)
            final_audio_data = np.concatenate(self.capture_buffer + [post_roll_silence])
            
            # Start transcription in a background thread
            is_voicenote = was_recording_voicenote
            threading.Thread(
                target=self._process_transcription,
                args=(final_audio_data, is_voicenote),
                daemon=True
            ).start()

        # Always remove the released key from the set
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    def _audio_worker(self):
        logging.info("Audio worker started.")
        try:
            with sd.InputStream(samplerate=CONFIG.audio.sample_rate, channels=1, dtype="int16",
                                blocksize=self.block_size, callback=self._audio_callback,
                                device=CONFIG.audio.device):
                self.shutdown_event.wait()
        except Exception as e:
            logging.fatal(f"Could not open audio stream: {e}"); self.shutdown_event.set()
    #endregion
    
    def run(self):
        """Starts background threads and the main GTK loop."""
        self.audio_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self.audio_thread.start()

        self.keyboard_listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.keyboard_listener.start()
        
        hotkey_str = " + ".join(map(str, CONFIG.ui.hotkeys))
        voicenote_hotkey_str = " + ".join(map(str, CONFIG.ui.hotkey_voicenote))
        logging.info(f"PTT is running.")
        logging.info(f"Hold '{hotkey_str}' to type.")
        logging.info(f"Hold '{voicenote_hotkey_str}' to save a voice note.")
        # NEW: The main blocking call is now the GTK loop, managed by our tray class
        self.tray.run()
        # After Gtk.main() exits, the script will proceed to shutdown.

    def stop(self, widget=None):
        """Gracefully shuts down all application components."""
        if not self.shutdown_event.is_set():
            logging.info("Shutting down...")
            self.shutdown_event.set()

            # Wait for the audio thread to finish cleaning up
            if self.audio_thread:
                self.audio_thread.join()

            if self.keyboard_listener:
                self.keyboard_listener.stop()

            # Tell the GTK loop to quit
            self.tray.stop()

# (main function and entry point are mostly the same)
def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    # ... (the rest of main is identical to v1.1) ...
    if "--list-devices" in sys.argv:
        # Code to list devices
        sys.exit(0)
    config = load_or_create_config()
    app = WhisperPTT(config)
    signal.signal(signal.SIGINT, lambda s, f: app.stop())
    app.run()

if __name__ == "__main__":
    main()
