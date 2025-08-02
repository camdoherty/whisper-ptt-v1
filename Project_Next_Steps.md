# Whisper PTT - Next Steps

This document outlines the recommended next steps for improving the `whisper-ptt-v1` project, focusing on stability, functionality, and user experience.

---

## 1. Long-Term Stability (Hotkey Timeout Issue) - ✅ COMPLETED

**Problem:** The application's hotkeys would become unresponsive after approximately 5 minutes of use.

**Diagnosis:** The root cause was identified as a state corruption issue in the hotkey detection logic. Occasionally, a key-release event was missed, causing "stale" keys to remain in the `pressed_keys` set. The application was performing a strict equality check (`==`) which would then fail because the set of pressed keys contained these extra stale keys.

**Solution:** The hotkey detection logic in the `_on_press` method was changed from a strict equality check to a subset check (`issubset()`). This ensures that the hotkey combination is detected as long as the required keys are pressed, even if other stale keys are present in the state. This change makes the detection far more robust and permanently resolves the timeout issue.

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
