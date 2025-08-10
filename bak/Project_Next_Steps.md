# Whisper PTT - Next Steps

This document outlines the recommended next steps for improving the `whisper-ptt-v1` project, focusing on stability, functionality, and user experience.

---

## 1. Long-Term Stability (Hotkey Timeout Issue) - ✅ COMPLETED

**Problem:** The application's hotkeys would become unresponsive after approximately 5 minutes of use.

**Diagnosis:** The root cause was identified as a state corruption issue in the hotkey detection logic. Occasionally, a key-release event was missed, causing "stale" keys to remain in the `pressed_keys` set. The application was performing a strict equality check (`==`) which would then fail because the set of pressed keys contained these extra stale keys.

**Solution:** The hotkey detection logic in the `_on_press` method was changed from a strict equality check to a subset check (`issubset()`). This ensures that the hotkey combination is detected as long as the required keys are pressed, even if other stale keys are present in the state. This change makes the detection far more robust and permanently resolves the timeout issue.

---

## 2. Foundational Improvements - ✅ COMPLETED

The following foundational improvements have been completed in v1.3:

1.  **Systemd Service for Autostart - ✅ COMPLETED**
    *   A `systemd` user service (`whisper-ptt.service`) was created and is now the recommended way to run the application for automatic startup on login.

2.  **Graceful Handling of Audio Device Errors - ✅ COMPLETED**
    *   The application no longer crashes when the audio device is disconnected. It now shows an error state and periodically attempts to reconnect, making it far more resilient for daily use.

3.  **Code Refactoring to Modules - ✅ COMPLETED**
    *   The original monolithic script was refactored into a clean, modular structure (`config.py`, `tray.py`, `whisper_ptt.py`), making the codebase more stable and easier to maintain.

---

## 3. Future Functionality and User Experience

With a stable foundation, here are the recommended next steps for future versions:

1.  **Dynamic Model Loading and Configuration:**
    *   **Problem:** The model path is hard-coded in the `config.toml` default and requires a manual, multi-step download process.
    *   **Solution:** Modify the `_load_model` function to accept a model name (e.g., "base.en", "small.en"). The script would then automatically download the specified model from Hugging Face into the `./models` directory if it doesn't already exist. This would simplify setup and allow users to easily switch models to balance speed and accuracy for their hardware.

2.  **Implement a "Settings" Dialog in the Tray Menu:**
    *   **Problem:** All configuration requires manually editing the `config.toml` file.
    *   **Solution:** Add a "Settings" option to the GTK tray icon's right-click menu. This would open a simple dialog window allowing the user to change key settings on the fly, such as the model size (tying into #1), hotkeys, and the audio device. This would dramatically improve the user experience.

3.  **Refactor `setup_venv.sh` for Idempotency and Robustness:**
    *   **Problem:** The current setup script is a simple, one-shot tool. It doesn't handle existing installations or potential failures gracefully.
    *   **Solution:** Enhance the `setup_venv.sh` script to be idempotent (safe to run multiple times). It should check for existing dependencies, verify the success of each step, and provide clearer instructions. It could also automatically detect the OS to recommend the correct `apt` packages and offer to create the `run.sh` script.
