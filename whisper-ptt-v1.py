#!/usr/bin/env python3
#
# whisper-ptt-v1.py
#
# A professional-grade, single-file Push-to-Talk script using faster-whisper.
#
# This script captures microphone audio when a hotkey is held down, transcribes
# the audio using a GPU-accelerated Whisper model, and types the resulting
# text into the active window. It is designed for low latency and high accuracy.
#
# Core Features:
# - Push-to-Talk: Audio is only captured while a hotkey is active.
# - Pre-roll Buffer: Captures audio 0.7 seconds *before* the hotkey is pressed.
# - High-Performance Transcription: Uses `faster-whisper` with GPU (INT8).
# - Non-Blocking: Transcription runs in a separate thread to keep the UI responsive.
# - Direct Text Input: Uses `pynput` for efficient and reliable text output.
# - Robust and Stable: Gracefully handles signals and errors.
#
# Author: Your Name/Handle
# Version: 1.0
# Date: 2024-05-21

from __future__ import annotations

import collections
import pathlib
import signal
import sys
import threading
import time
from typing import Final

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
from pynput import keyboard

# --- CONFIGURATION CONSTANTS ---

# Performance & Model
MODEL_PATH: Final[str] = "models/faster-whisper-medium.en-int8/"
# Compute type for the model. "int8_float16" or "int8" for an even smaller footprint.
# "int8_float32" is a good balance for GTX 1080.
COMPUTE_TYPE: Final[str] = "int8_float32"
DEVICE: Final[str] = "cuda"

# Audio
SAMPLE_RATE: Final[int] = 16_000
# Block size in milliseconds. Determines how often the audio stream is processed.
BLOCK_DURATION_MS: Final[int] = 30
BLOCK_SIZE: Final[int] = int(SAMPLE_RATE * BLOCK_DURATION_MS / 1000)
# Ring buffer size in seconds. This holds audio history for the pre-roll.
RING_BUFFER_DURATION_S: Final[float] = 3.0
# Pre-roll duration in seconds. Audio captured *before* the hotkey is pressed.
PRE_ROLL_S: Final[float] = 0.7
# Post-roll silence in seconds. Added to the end to help the model finalize segments.
POST_ROLL_S: Final[float] = 0.3

# Hotkey
# Use a set for key combinations, for example: {keyboard.Key.ctrl_l, keyboard.Key.alt_l}
HOTKEY_COMBO: Final[set] = {keyboard.Key.ctrl_l, keyboard.Key.shift_l}

# Transcription Parameters
BEAM_SIZE: Final[int] = 5
BEST_OF: Final[int] = 5
TEMPERATURE: Final[float] = 0.0
REPETITION_PENALTY: Final[float] = 1.2
LOG_PROB_THRESHOLD: Final[float | None] = -1.0
VAD_MIN_SILENCE_MS: Final[int] = 500  # VAD looks for this much silence.

# --- DERIVED CONSTANTS ---
RING_BUFFER_FRAMES: Final[int] = int(RING_BUFFER_DURATION_S * SAMPLE_RATE)
RING_BUFFER_BLOCKS: Final[int] = RING_BUFFER_FRAMES // BLOCK_SIZE + 1
PRE_ROLL_BLOCKS: Final[int] = int(PRE_ROLL_S * SAMPLE_RATE) // BLOCK_SIZE
POST_ROLL_FRAMES: Final[int] = int(POST_ROLL_S * SAMPLE_RATE)


class WhisperPTT:
    """
    A Push-to-Talk application that transcribes speech using Whisper.

    This class encapsulates all the logic for audio capture, buffering,
    transcription, and text output, managing its own threads for responsive
    operation.
    """

    def __init__(self):
        # State flags and locks
        self.is_capturing: bool = False
        self.shutdown_event = threading.Event()
        self._lock = threading.Lock()
        self.pressed_keys = set()

        # Threads
        self.audio_thread: threading.Thread | None = None
        self.transcription_thread: threading.Thread | None = None

        # Buffers
        # 1. A ring buffer to constantly store recent audio
        self.ring_buffer = collections.deque(maxlen=RING_BUFFER_BLOCKS)
        # 2. A buffer to hold the audio for the current PTT session
        self.capture_buffer: list[np.ndarray] = []

        # Dependencies
        self.model = self._load_model()
        self.keyboard_controller = keyboard.Controller()

        # Timing metrics
        self.t_key_release: float = 0.0

    def _load_model(self) -> WhisperModel:
        """Loads the faster-whisper model from the specified path."""
        model_dir = pathlib.Path(MODEL_PATH)
        if not model_dir.exists() or not any(model_dir.iterdir()):
            print(f"FATAL: Model directory not found or empty: {MODEL_PATH}", file=sys.stderr)
            sys.exit(1)
        print("Loading Whisper model...")
        try:
            model = WhisperModel(
                MODEL_PATH,
                device=DEVICE,
                compute_type=COMPUTE_TYPE,
            )
            print(f"Model '{MODEL_PATH}' loaded on {DEVICE} ({COMPUTE_TYPE}).")
            return model
        except Exception as e:
            print(f"FATAL: Could not load the model. Error: {e}", file=sys.stderr)
            print("Please ensure torch, CUDA, and cuDNN are correctly installed.", file=sys.stderr)
            sys.exit(1)

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info, status: sd.CallbackFlags
    ) -> None:
        """This function is called by the sounddevice stream for each audio block."""
        if status:
            print(f"[WARN] PortAudio status: {status}", file=sys.stderr)

        # The input data is int16, convert it to float32
        audio_chunk = indata.flatten().astype(np.float32) / 32768.0
        self.ring_buffer.append(audio_chunk)

        if self.is_capturing:
            self.capture_buffer.append(audio_chunk)

    def _process_transcription(self, audio_data: np.ndarray) -> None:
        """Transcribe audio data and output the result."""
        t_decode_start = time.perf_counter()
        print("Transcribing...")

        try:
            segments, _ = self.model.transcribe(
                audio_data,
                language="en",
                beam_size=BEAM_SIZE,
                best_of=BEST_OF,
                temperature=TEMPERATURE,
                repetition_penalty=REPETITION_PENALTY,
                log_prob_threshold=LOG_PROB_THRESHOLD,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=VAD_MIN_SILENCE_MS),
                condition_on_previous_text=False,
            )

            # Join segments into a single string
            full_text = " ".join(s.text.strip() for s in segments)
            full_text = full_text.strip()

            t_decode_end = time.perf_counter()

            if full_text:
                print(f"-> Transcribed: '{full_text}'")
                self._output_text(full_text)
                t_type_done = time.perf_counter()
                print(
                    f"[perf] Decode: {(t_decode_end - t_decode_start):.3f}s | "
                    f"Type: {(t_type_done - t_decode_end):.3f}s | "
                    f"Total: {(t_type_done - self.t_key_release):.3f}s"
                )
            else:
                print("Transcription was empty.")

        except Exception as e:
            print(f"[ERROR] Transcription failed: {e}", file=sys.stderr)

    def _output_text(self, text: str) -> None:
        """Types the transcribed text using a keyboard controller."""
        try:
            # Prepend a space to detach from the previous word
            self.keyboard_controller.type(" " + text)
        except Exception as e:
            print(f"[ERROR] Failed to type text: {e}", file=sys.stderr)

    def _on_press(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        """Hotkey press handler."""
        if key in HOTKEY_COMBO:
            self.pressed_keys.add(key)
            if HOTKEY_COMBO.issubset(self.pressed_keys) and not self.is_capturing:
                with self._lock:
                    if self.is_capturing: return
                    self.is_capturing = True

                print("\n▶ Recording started...")
                # Start capture with pre-roll audio from the ring buffer
                self.capture_buffer.clear()
                self.capture_buffer.extend(list(self.ring_buffer)[-PRE_ROLL_BLOCKS:])

    def _on_release(self, key: keyboard.Key | keyboard.KeyCode | None) -> None:
        """Hotkey release handler."""
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)

        if key in HOTKEY_COMBO and self.is_capturing:
            with self._lock:
                if not self.is_capturing: return
                self.is_capturing = False
            
            self.t_key_release = time.perf_counter()
            print("■ Recording stopped. Processing...")

            # Add post-roll silence
            post_roll_silence = np.zeros(POST_ROLL_FRAMES, dtype=np.float32)
            final_audio_data = np.concatenate(self.capture_buffer + [post_roll_silence])
            self.capture_buffer.clear()

            # Start transcription in a new thread to avoid blocking the listener
            self.transcription_thread = threading.Thread(
                target=self._process_transcription, args=(final_audio_data,)
            )
            self.transcription_thread.start()

    def _audio_worker(self):
        """The main loop for the audio stream."""
        print("Audio worker started. Listening to microphone...")
        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype="int16",
                blocksize=BLOCK_SIZE,
                callback=self._audio_callback,
            ):
                while not self.shutdown_event.is_set():
                    time.sleep(0.1)
        except Exception as e:
            print(f"FATAL: Could not open audio stream. Error: {e}", file=sys.stderr)
            print("Please ensure you have a working microphone and the 'sounddevice' library is correctly installed.", file=sys.stderr)
            self.shutdown_event.set() # Signal main thread to exit

        print("Audio worker finished.")

    def run(self) -> None:
        """Starts the application threads and listeners."""
        # Start the audio worker thread
        self.audio_thread = threading.Thread(target=self._audio_worker)
        self.audio_thread.start()

        # Start the keyboard listener in the main thread
        with keyboard.Listener(on_press=self._on_press, on_release=self._on_release) as listener:
            hotkey_str = " + ".join(str(k).split('.')[-1] for k in HOTKEY_COMBO)
            print(f"PTT is running. Hold '{hotkey_str}' to talk. Press Ctrl+C to exit.")
            # Wait until shutdown is signaled
            self.shutdown_event.wait()
            # Stop the listener when shutdown is triggered
            listener.stop()

    def stop(self) -> None:
        """Gracefully shuts down all application threads."""
        print("\nShutting down...")
        self.shutdown_event.set()

        if self.audio_thread and self.audio_thread.is_alive():
            self.audio_thread.join()

        if self.transcription_thread and self.transcription_thread.is_alive():
            self.transcription_thread.join()
        
        print("Shutdown complete.")


def main():
    """Main function to run the PTT application."""
    app = WhisperPTT()

    # Set up a signal handler for graceful shutdown on Ctrl+C
    def signal_handler(sig, frame):
        app.stop()

    signal.signal(signal.SIGINT, signal_handler)
    
    app.run()
    sys.exit(0)


if __name__ == "__main__":
    main()
