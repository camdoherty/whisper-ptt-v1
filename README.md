# Whisper PTT v1.3
A high-performance, push-to-talk (PTT) voice transcription script that uses `faster-whisper` for GPU-accelerated speech-to-text and types the output directly into your active window or a user-defined file.

## Features
- **Dual Hotkey Actions**: Configure one hotkey for direct text input (typing) and a separate hotkey to save transcriptions directly to a file.
- **Robust Error Recovery**: Automatically recovers from audio device disconnections and system suspend/resume cycles without crashing.
- **XDG Autostart**: Natively integrates with the standard Linux desktop startup process.
- **Voice Notes**: Append timestamped transcriptions to a designated file, perfect for logging ideas or taking notes.
- **Clickable Desktop Notifications**: Get instant, clickable feedback when a voice note is saved. For Obsidian users, clicking the notification opens the note directly in your vault.
- **Low Latency**: End-to-end latency from key release to output is minimal.
- **Pre-roll Audio Buffer**: Captures audio *before* you press the hotkey, so you never miss the start of a sentence.
- **High-Performance Transcription**: Leverages `faster-whisper` with GPU acceleration for fast and accurate results.
- **Stable & Responsive**: A non-blocking, multi-threaded design with robust hotkey detection ensures the application remains responsive and reliable over long periods.

## Architecture Overview
The stability and performance of `whisper-ptt` come from its clean, modular design that separates concerns:

-   **`config.py`**: Manages configuration loading and dataclasses.
-   **`tray.py`**: Handles all GTK user interface components, including the system tray icon and notifications.
-   **`whisper_ptt.py`**: The main application entry point, containing the core `WhisperPTT` class and its multi-threaded architecture:
    1.  **Main Thread (GTK)**: Runs the GTK main loop for the UI.
    2.  **Keyboard Listener Thread (`pynput`)**: Detects hotkey presses globally.
    3.  **Audio Worker Thread**: Manages the microphone input stream and handles device errors.
    4.  **Transcription Worker Thread**: A new, short-lived thread is spawned for each transcription job.

This architecture prevents the user interface from freezing during transcription and ensures high stability.

## Setup Instructions
### 1. Prerequisites
-   Python 3.10+
-   An NVIDIA GPU with CUDA Toolkit and cuDNN installed (tested with driver 535+).
-   A working microphone.
-   The `git` command-line tool.
-   For Debian/Ubuntu-based systems, the GTK development and notification libraries are required. This is a critical step for the user interface.
    ```bash
    sudo apt install libgirepository1.0-dev libcairo2-dev pkg-config python3-dev python3-gi gir1.2-gtk-3.0 libgtk-3-dev
    ```

### 2. Installation
This project includes a setup script that automates the entire installation process.

1.  **Clone the Repository**
    ```bash
    git clone <your-repo-url>
    cd whisper-ptt-v1
    ```

2.  **Run the Setup Script**
    Make the script executable and run it:
    ```bash
    chmod +x setup_venv.sh
    ./setup_venv.sh
    ```
    This script will create the virtual environment, install all dependencies, and apply necessary configuration fixes for the GTK interface and CUDA libraries. The required transcription model will be downloaded automatically on first run.

## Usage
The recommended way to run the application is by using the provided `run.sh` script, which ensures the environment is set up correctly.

```bash
./run.sh
```

## Autostart on Login
To have the application start automatically when you log in, you can use the standard XDG Autostart method.

1.  **Create the Autostart Directory**:
    If it doesn't already exist, create the directory where desktop startup files are stored:
    ```bash
    mkdir -p ~/.config/autostart
    ```

2.  **Create the `.desktop` File**:
    Create a new file at `~/.config/autostart/whisper-ptt.desktop` with the following content. Make sure to replace `/path/to/your/project` with the actual, absolute path to the `whisper-ptt-v1` directory.
    ```ini
    [Desktop Entry]
    Type=Application
    Name=Whisper PTT
    Exec=/path/to/your/project/run.sh
    Icon=/path/to/your/project/icon-idle.png
    Comment=Voice to text application
    Terminal=false
    ```

The application will now launch automatically the next time you log into your desktop session.

## Configuration
Configuration is handled in the `config.toml` file, allowing you to customize hotkeys and file paths.

### Hotkey Actions
You can configure two separate hotkey actions in the `[ui]` section:

**1. Type Out Transcription (`hotkeys`)**
This is the primary push-to-talk hotkey. When held, it records audio, and upon release, it types the transcribed text into the active window.

*Default: Right Ctrl + Right Shift*
```toml
hotkeys = ["ctrl_r", "shift_r"]
```

**2. Save Transcription to File (`hotkey_voicenote`)**
This hotkey records audio and, upon release, appends the transcription as a new line in a specified file.

*Default: Right Ctrl + Right Alt*
```toml
hotkey_voicenote = ["ctrl_r", "alt_r"]
```

Valid key names are derived from the `pynput` library (e.g., `ctrl_l`, `shift_r`, `alt_r`, `f1`, `/`).

### Voice Note File Path
You can specify the destination file for the voice note feature. New notes are prepended to the top of the file. The `~` character is automatically expanded to your home directory.

*Example:*
```toml
voicenote_file = "~/ObsidianVault/🎙️VoiceNotes.md"
```
If the file is located within an Obsidian vault, clicking the notification will open it directly in Obsidian.

## Troubleshooting
### `libcudnn_ops_infer.so.8: cannot open shared object file` Error on Linux
If you encounter this error, it means the dynamic linker cannot find the required NVIDIA cuDNN library.

The provided `setup_venv.sh` script attempts to handle this, but if the problem persists, the solution is to use the `run.sh` launcher script. This script correctly sets the `LD_LIBRARY_PATH` environment variable before starting the application.

**Always use `./run.sh` to start the application to avoid this issue.**
