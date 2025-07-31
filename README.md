# Whisper PTT v1
A high-performance, push-to-talk (PTT) voice transcription script that uses `faster-whisper` for GPU-accelerated speech-to-text and types the output directly into your active window.

## Features
- **Dual Hotkey Actions**: Configure one hotkey for direct text input (typing) and a separate hotkey to save transcriptions directly to a file.
- **Voice Notes**: Append timestamped transcriptions to a designated file, perfect for logging ideas or taking notes.
- **Clickable Desktop Notifications**: Get instant, clickable feedback when a voice note is saved. Clicking the notification opens the voice note file directly in your default editor (requires `libnotify`).
- **Low Latency**: End-to-end latency from key release to output is minimal.
- **Pre-roll Audio Buffer**: Captures audio *before* you press the hotkey, so you never miss the start of a sentence.
- **High-Performance Transcription**: Leverages `faster-whisper` with GPU acceleration for fast and accurate results.
- **Direct Text Input**: Reliably types the final text into any active application window.
- **Stable & Responsive**: A non-blocking, multi-threaded design ensures the application remains responsive.

## Architecture Overview
The stability and performance of `whisper-ptt-v1` come from its clean, multi-threaded design that separates concerns:

1.  **Main Thread**: Handles application startup, shutdown, and runs the `pynput` keyboard listener to detect hotkey presses and releases.
2.  **Audio Worker Thread**: Runs in the background, continuously capturing audio from the microphone into a small, efficient ring buffer. This ensures audio is always available for the pre-roll.
3.  **Transcription Worker Thread**: A new, short-lived thread is spawned each time the PTT key is released. This thread takes the captured audio, sends it to the Whisper model for processing, and types the result.

This architecture prevents the user interface (keyboard listener) from freezing during the transcription process and eliminates the race conditions and audio buffering issues that plagued earlier versions.

## Setup Instructions
### 1. Prerequisites
-   Python 3.10+
-   An NVIDIA GPU with CUDA Toolkit and cuDNN installed (tested with driver 535+).
-   A working microphone.
-   The `git` command-line tool.
-   For Debian/Ubuntu-based systems, the GTK development and notification libraries are required:
    ```bash
    sudo apt-get install libgirepository1.0-dev libcairo2-dev libnotify-bin
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
    This script will create the virtual environment, install all dependencies, and apply necessary configuration fixes for the GTK interface and CUDA libraries.

4.  **Download the Transcription Model**
    The script is configured to use the `medium.en` model quantized to INT8. You need to download it and place it in the correct directory.

    We will use `git` to download the model files from Hugging Face.
    ```bash
    # Ensure you have Git LFS installed: git lfs install
    mkdir -p models
    git clone https://huggingface.co/Systran/faster-whisper-medium.en models/faster-whisper-medium.en-int8
    ```
    *Note: The command above clones the FP16 model. `faster-whisper` will automatically convert it to INT8 on first load if `compute_type` is set to `int8` or `int8_float16`/`int8_float32`.*

## Usage
With your virtual environment activated, simply run the script:

```bash
python whisper-ptt-v1.py
```

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
You can specify the destination file for the voice note feature. The `~` character is automatically expanded to your home directory.

*Example:*
```toml
voicenote_file = "~/ObsidianVault/🎙️VoiceNotes.md"
```

## Troubleshooting
### `libcudnn_ops_infer.so.8: cannot open shared object file` Error on Linux
If you encounter this error when running the script with `device = "cuda"`, it means the dynamic linker cannot find the required NVIDIA cuDNN library. This can happen even if `torch` and `cudnn` were installed correctly via `pip`.

The recommended solution is to add the library's path to the `LD_LIBRARY_PATH` environment variable automatically when you activate the virtual environment.
1.  **Find the library path**: The path is typically inside your virtual environment:
    `<project_directory>/.venv/lib/python3.11/site-packages/nvidia/cudnn/lib/`

2.  **Edit the activation script**: Open the `.venv/bin/activate` file and add the following line at the very end:
    ```bash
    export LD_LIBRARY_PATH="/path/to/your/project/.venv/lib/python3.11/site-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH"
    ```
    Replace `/path/to/your/project/` with the absolute path to the `whisper-ptt-v1` directory.

3.  **Re-activate the environment**: Run `deactivate` and then `source .venv/bin/activate`. The script should now run correctly.
