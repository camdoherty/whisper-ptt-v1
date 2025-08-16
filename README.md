## Whisper PTT v1.3
A high-performance, push-to-talk (PTT) voice transcription app for Linux desktops. It uses `faster-whisper` for fast, local, and accurate on-device speech-to-text. Output is typed directly into your active window or saved to a user-defined note file.

This project is a Python wrapper for a community implementation of OpenAI's Whisper model, offering a powerful offline alternative to cloud-based STT services.

### Configuration
`whisper-ptt` is configured with a simple `config.toml` file.

```toml
# config.toml
[model]
# Run on GPU or CPU
device = "cuda" # "cuda" or "cpu"
# Model size and precision
path = "models/faster-whisper-small.en-int8/"
compute_type = "int8"

[ui]
# Set your preferred hotkeys
hotkeys = ["ctrl_r", "shift_r"]
hotkey_voicenote = ["ctrl_r", "alt_r"]
```

### Features
- **Dual Hotkey Actions**: Use one hotkey for direct text input and another to save transcriptions to a file.
- **High-Performance & Local**: Leverages `faster-whisper` with GPU or CPU acceleration for fast, private, and accurate results.
- **Pre-roll Audio Buffer**: Captures audio *before* you press the hotkey, so you never miss the start of a sentence.
- **Robust Error Recovery**: Automatically recovers from audio device disconnections and system suspend/resume cycles.
- **Voice Notes**: Append timestamped transcriptions to a designated file, perfect for logging ideas.
- **Stable & Responsive**: A multi-threaded design ensures the app remains responsive and reliable.

### Setup Instructions
#### 1. Prerequisites
-   Python 3.10+
-   A working microphone.
-   The `git` command-line tool.
-   An NVIDIA GPU is recommended for best performance but **not required**. The app runs efficiently on CPU.
-   For Debian/Ubuntu-based systems, GTK development libraries are required for the user interface:
    ```bash
    sudo apt install libgirepository1.0-dev libcairo2-dev pkg-config python3-dev python3-gi gir1.2-gtk-3.0 libgtk-3-dev
    ```

#### 2. Installation
A setup script automates the entire installation process.

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/camdoherty/whisper-ptt-v1.git
    cd whisper-ptt-v1
    ```

2.  **Run the Setup Script**
    ```bash
    chmod +x setup_venv.sh
    ./setup_venv.sh
    ```
    This script creates a virtual environment, installs dependencies, and downloads the default transcription model.

### Usage
The included `run.sh` script ensures the environment is set up correctly.

```bash
./run.sh
```

### Autostart on Login
To start the application automatically on login, create a `.desktop` file at `~/.config/autostart/whisper-ptt.desktop`.

Replace `/path/to/your/project` with the absolute path to the `whisper-ptt-v1` directory.
```ini
[Desktop Entry]
Type=Application
Name=Whisper PTT
Exec=/path/to/your/project/run.sh
Icon=/path/to/your/project/icon-idle.png
Comment=Push-to-talk voice transcription
Terminal=false
```

### Full Configuration
All settings are in `config.toml`.

#### Hotkey Actions
- **`hotkeys`**: The primary push-to-talk hotkey. Records audio and types the transcribed text into the active window. *Default: Right Ctrl + Right Shift*
- **`hotkey_voicenote`**: Records audio and appends the transcription to a file. *Default: Right Ctrl + Right Alt*

Valid key names are from the `pynput` library (e.g., `ctrl_l`, `shift_r`, `alt_r`, `f1`, `/`).

#### Voice Note File Path
- **`voicenote_file`**: The destination file for the voice note feature. The `~` character is expanded to your home directory.

### Troubleshooting
#### `libcudnn_ops_infer.so.8: cannot open shared object file`
This error means the dynamic linker cannot find the NVIDIA cuDNN library. The `run.sh` script sets the required `LD_LIBRARY_PATH` to prevent this. **Always use `./run.sh` to start the application if you are using a GPU.**

### Architecture
`whisper-ptt` uses a multi-threaded architecture to ensure stability and responsiveness:
-   **Main Thread (GTK)**: Runs the UI event loop.
-   **Keyboard Listener (`pynput`)**: Detects hotkeys.
-   **Audio Worker**: Manages the microphone input stream.
-   **Transcription Worker**: A new thread is spawned for each transcription job.
