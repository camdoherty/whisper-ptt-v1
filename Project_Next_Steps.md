# Whisper PTT - Next Steps

This document outlines the recommended next steps for improving the `whisper-ptt-v1` project, focusing on stability, functionality, and user experience.

---

## 1. Address Long-Term Stability (Hotkey Timeout Issue)

**Problem:** The application's hotkeys become unresponsive after a long period of inactivity, suggesting a silent crash in a background thread.

**Hypothesis:** The `pynput` keyboard listener thread, which hooks into the OS's low-level input system, is likely crashing due to system events like screen locking, sleep/wake cycles, or other applications grabbing exclusive input focus.

### Recommended Plan:

1.  **Add "Heartbeat" Logging (Immediate Diagnosis):**
    *   **Action:** Add logging statements at the very beginning of the `_on_press` and `_on_release` methods.
    *   **Goal:** To confirm that the `pynput` thread is the point of failure. If the log messages stop appearing when hotkeys are pressed, the diagnosis is confirmed.

2.  **Implement a Listener Watchdog (Long-Term Fix):**
    *   **Action:** Create a new "watchdog" thread that runs in the background. Its sole responsibility is to check every few seconds if the `keyboard_listener` thread is still alive (`is_alive()`).
    *   **Goal:** If the watchdog finds the listener thread has died, it should log the event and automatically restart a new listener, making the application self-healing and resilient to these silent crashes.

---

## 2. Improve Functionality and User Experience

Here are the top 5 most impactful feature enhancements, ordered by priority:

1.  **Dynamic Model Loading and Configuration:**
    *   **Problem:** The model path is hard-coded in the `config.toml` default and requires a manual, multi-step download process.
    *   **Solution:** Modify the `_load_model` function to accept a model name (e.g., "base.en", "small.en"). The script would then automatically download the specified model from Hugging Face into the `./models` directory if it doesn't already exist. This would simplify setup and allow users to easily switch models to balance speed and accuracy for their hardware.

2.  **Systemd Service for Autostart:**
    *   **Problem:** The application must be started manually from the command line.
    *   **Solution:** Create a `systemd` user service file (`whisper-ptt.service`). This would allow the application to be managed by the system, enabling it to start automatically on login and run reliably in the background. The service file would use the `run.sh` script to ensure the environment is always correct.

3.  **Refactor `setup_venv.sh` for Idempotency and Robustness:**
    *   **Problem:** The current setup script is a simple, one-shot tool. It doesn't handle existing installations or potential failures gracefully.
    *   **Solution:** Enhance the `setup_venv.sh` script to be idempotent (safe to run multiple times). It should check for existing dependencies, verify the success of each step, and provide clearer instructions. It could also automatically detect the OS to recommend the correct `apt` packages and offer to create the `run.sh` script.

4.  **Graceful Handling of Audio Device Errors:**
    *   **Problem:** The application currently exits with a fatal error if the audio stream fails to open (e.g., if a USB microphone is unplugged).
    *   **Solution:** Implement more robust error handling in the `_audio_worker` thread. Instead of crashing, the application could display a persistent desktop notification (e.g., "Error: Microphone not found.") and periodically retry opening the audio device.

5.  **Implement a "Settings" Dialog in the Tray Menu:**
    *   **Problem:** All configuration requires manually editing the `config.toml` file.
    *   **Solution:** Add a "Settings" option to the GTK tray icon's right-click menu. This would open a simple dialog window allowing the user to change key settings on the fly, such as the model size (tying into #1), hotkeys, and the audio device. This would dramatically improve the user experience.
