#!/usr/bin/env python3

import collections
import datetime
import logging
import os
import pathlib
import signal
import sys
import threading
import time

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from pynput import keyboard
from gi.repository import GLib

from config import AppConfig, load_or_create_config
from tray import TrayIconGTK

# Global config instance
CONFIG: AppConfig = None

# --- Globals ---
BASE_DIR = pathlib.Path(__file__).parent.resolve()

class WhisperPTT:
    """The main application class."""
    def __init__(self, config: AppConfig, base_dir: pathlib.Path):
        global CONFIG
        CONFIG = config
        self.base_dir = base_dir
        self.state = "idle"  # idle, recording, recording_voicenote, processing, error
        self.shutdown_event = threading.Event()
        self.audio_device_ok = threading.Event()
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
        self.tray = TrayIconGTK(self, self.base_dir)
        self.model = self._load_model()
        self.keyboard_controller = keyboard.Controller()
        self.hotkeys = self._parse_hotkeys(CONFIG.ui.hotkeys)
        self.hotkeys_voicenote = self._parse_hotkeys(CONFIG.ui.hotkey_voicenote)
        self.pressed_keys = set()
        self.beep_start = self._create_beep(freq=440, duration_ms=50)
        self.beep_stop = self._create_beep(freq=880, duration_ms=50)

    #region Helper Methods
    def _load_model(self) -> WhisperModel:
        # If we are reloading, explicitly delete the old model to free CUDA resources.
        if hasattr(self, 'model') and self.model is not None:
            logging.info("Releasing existing Whisper model...")
            del self.model
            self.model = None
            import gc
            gc.collect()
            time.sleep(1)

        model_path = self.base_dir / CONFIG.model.path
        if not model_path.exists():
            logging.fatal(f"Model dir not found: {model_path}")
            sys.exit(1)
        
        logging.info("Loading Whisper model...")
        try:
            model = WhisperModel(str(model_path), device=CONFIG.model.device, compute_type=CONFIG.model.compute_type)
            logging.info(f"Model '{model_path.name}' loaded.")
            return model
        except Exception as e:
            logging.fatal(f"Failed to load Whisper model: {e}")
            self._update_state("error")
            GLib.idle_add(self.tray.show_notification, "Whisper PTT Fatal Error", "Failed to load model. See logs.")
            return None

    def _parse_hotkeys(self, key_strs: list[str]) -> set:
        keys = set()
        for key_str in key_strs:
            key_str = key_str.lower()
            if hasattr(keyboard.Key, key_str):
                keys.add(getattr(keyboard.Key, key_str))
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

    #region Event Handlers & Workers
    def _audio_callback(self, indata, frames, time_info, status):
        if status: logging.warning(f"PortAudio status: {status}")
        audio_chunk = indata.flatten().astype(np.float32) / 32768.0
        self.ring_buffer.append(audio_chunk)
        if self.state in ["recording", "recording_voicenote"]:
            self.capture_buffer.append(audio_chunk)

    def _write_to_voicenote_file(self, text: str):
        try:
            self.voicenote_file_path.parent.mkdir(parents=True, exist_ok=True)
            existing_content = ""
            if self.voicenote_file_path.exists():
                with open(self.voicenote_file_path, "r", encoding="utf-8") as f:
                    existing_content = f.read()
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_note = f"__{timestamp}__\n{text}\n\n"
            with open(self.voicenote_file_path, "w", encoding="utf-8") as f:
                f.write(new_note)
                f.write(existing_content)
            logging.info(f"Prepended to {self.voicenote_file_path}")
            GLib.idle_add(self.tray.show_notification, f"Note Saved to {self.voicenote_file_path.name}", text)
        except Exception as e:
            logging.error(f"Failed to write to voice note file: {e}")

    def _on_press(self, key):
        if isinstance(key, keyboard.Key) or isinstance(key, keyboard.KeyCode):
            self.pressed_keys.add(key)
        with self._lock:
            if self.state != "idle" or not self.audio_device_ok.is_set():
                return
            if self.hotkeys.issubset(self.pressed_keys):
                self._update_state("recording")
                self._play_sound(self.beep_start)
                self.capture_buffer.clear()
                self.capture_buffer.extend(list(self.ring_buffer)[-self.pre_roll_blocks:])
            elif self.hotkeys_voicenote.issubset(self.pressed_keys):
                self._update_state("recording_voicenote")
                self._play_sound(self.beep_start)
                self.capture_buffer.clear()
                self.capture_buffer.extend(list(self.ring_buffer)[-self.pre_roll_blocks:])

    def _on_release(self, key):
        was_recording_type = self.state == "recording" and key in self.hotkeys
        was_recording_voicenote = self.state == "recording_voicenote" and key in self.hotkeys_voicenote
        if was_recording_type or was_recording_voicenote:
            with self._lock:
                if self.state not in ["recording", "recording_voicenote"]: return
                self._update_state("processing")
            self._play_sound(self.beep_stop)
            post_roll_silence = np.zeros(self.post_roll_frames, dtype=np.float32)
            final_audio_data = np.concatenate(self.capture_buffer + [post_roll_silence])
            is_voicenote = was_recording_voicenote
            threading.Thread(
                target=self._process_transcription,
                args=(final_audio_data, is_voicenote),
                daemon=True
            ).start()
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

    def _audio_worker(self):
        logging.info("Audio worker started.")
        while not self.shutdown_event.is_set():
            try:
                with sd.InputStream(
                    samplerate=CONFIG.audio.sample_rate,
                    channels=1,
                    dtype="int16",
                    blocksize=self.block_size,
                    callback=self._audio_callback,
                    device=CONFIG.audio.device,
                ):
                    if not self.audio_device_ok.is_set():
                        logging.info("Audio device reconnected. Re-initializing model...")
                        self.model = self._load_model()
                        if self.model:
                            GLib.idle_add(self.tray.show_notification, "Whisper PTT", "Audio device connected.")
                            self._update_state("idle")
                        else:
                            self._update_state("error")
                    self.audio_device_ok.set()
                    self.shutdown_event.wait()
            except sd.PortAudioError as e:
                if self.audio_device_ok.is_set():
                    logging.error(f"Audio device error: {e}")
                    self._update_state("error")
                    GLib.idle_add(self.tray.show_notification, "Whisper PTT Error", "Audio device disconnected. Retrying...")
                self.audio_device_ok.clear()
                time.sleep(5)
            except Exception as e:
                logging.fatal(f"An unhandled exception occurred in the audio worker: {e}")
                GLib.idle_add(self.tray.show_notification, "Whisper PTT Fatal Error", "See logs for details.")
                self.shutdown_event.set()
        logging.info("Audio worker stopped.")
    #endregion
    
    def run(self):
        self.audio_device_ok.set()
        self.audio_thread = threading.Thread(target=self._audio_worker, daemon=True)
        self.audio_thread.start()
        self.keyboard_listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.keyboard_listener.start()
        hotkey_str = " + ".join(map(str, CONFIG.ui.hotkeys))
        voicenote_hotkey_str = " + ".join(map(str, CONFIG.ui.hotkey_voicenote))
        logging.info(f"PTT is running.")
        logging.info(f"Hold '{hotkey_str}' to type.")
        logging.info(f"Hold '{voicenote_hotkey_str}' to save a voice note.")
        self.tray.run()

    def stop(self, widget=None):
        if not self.shutdown_event.is_set():
            logging.info("Shutting down...")
            self.shutdown_event.set()
            if self.audio_thread:
                self.audio_thread.join()
            if self.keyboard_listener:
                self.keyboard_listener.stop()
            self.tray.stop()

def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
    if "--list-devices" in sys.argv:
        print("Available audio devices:")
        print(sd.query_devices())
        sys.exit(0)
    
    config = load_or_create_config()
    app = WhisperPTT(config, BASE_DIR)
    signal.signal(signal.SIGINT, lambda s, f: app.stop())
    app.run()

if __name__ == "__main__":
    main()
