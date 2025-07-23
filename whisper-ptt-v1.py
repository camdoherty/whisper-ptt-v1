#!/usr/bin/env python3
#
# whisper-ptt-v1.2.py
#
# This version replaces the pystray library with a native GTK system tray icon
# using PyGObject. This provides a robust and visually correct icon on Linux
# desktops like XFCE, GNOME, and MATE, solving rendering issues.
#
# Author: Your Name/Handle
# Version: 1.2
# Date: 2024-05-22

import collections
import logging
import pathlib
import signal
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
    from gi.repository import Gtk, GdkPixbuf
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
    hotkey: str = "ctrl_l"
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
hotkey = "ctrl_l"
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
    """Manages the GTK System Tray Icon."""
    def __init__(self, app_instance):
        self.app = app_instance
        self.icon = Gtk.StatusIcon()
        self.icon.set_title("Whisper PTT")
        self.icon.connect("popup-menu", self.on_right_click)
        self.set_state("idle") # Set initial icon

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
        self.state = "idle"  # idle, recording, processing
        self.shutdown_event = threading.Event()
        self._lock = threading.Lock()
        
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
        self.hotkey = self._parse_hotkey(CONFIG.ui.hotkey)
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

    def _parse_hotkey(self, key_str: str) -> keyboard.Key:
        key_str = key_str.lower()
        if hasattr(keyboard.Key, key_str): return getattr(keyboard.Key, key_str)
        logging.fatal(f"Invalid hotkey '{key_str}'"); sys.exit(1)

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
        # NEW: Delegate UI update to the tray icon class
        self.tray.set_state(self.state)

    def _process_transcription(self, audio_data: np.ndarray):
        # ... (this method is identical to v1.1) ...
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
        if self.state == "recording":
            self.capture_buffer.append(audio_chunk)
    
    def _on_press(self, key):
        if key == self.hotkey and self.state == "idle":
            with self._lock:
                if self.state != "idle": return
                self._update_state("recording")
            self._play_sound(self.beep_start)
            self.capture_buffer.clear()
            self.capture_buffer.extend(list(self.ring_buffer)[-self.pre_roll_blocks:])

    def _on_release(self, key):
        if key == self.hotkey and self.state == "recording":
            with self._lock:
                if self.state != "recording": return
                self._update_state("processing")
            self._play_sound(self.beep_stop)
            post_roll_silence = np.zeros(self.post_roll_frames, dtype=np.float32)
            final_audio_data = np.concatenate(self.capture_buffer + [post_roll_silence])
            threading.Thread(target=self._process_transcription, args=(final_audio_data,), daemon=True).start()

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
        
        logging.info(f"PTT is running. Hold '{CONFIG.ui.hotkey}' to talk.")
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
