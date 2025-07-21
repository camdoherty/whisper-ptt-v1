# Whisper PTT v1

A high-performance, push-to-talk (PTT) voice transcription script that uses `faster-whisper` for GPU-accelerated speech-to-text and types the output directly into your active window.

This project is a complete rewrite of an earlier version, designed from the ground up for stability, low latency, and readability. It solves previous issues with transcription repetition and race conditions by implementing a robust, multi-threaded architecture.

## Features

- **Push-to-Talk Operation**: Audio is captured only while a hotkey combination (e.g., `Left-Ctrl` + `Left-Shift`) is held down.
- **Low Latency**: End-to-end latency from key release to typed text is minimal (typically under 1.5 seconds).
- **Pre-roll Audio Buffer**: The script captures a short duration of audio *before* you press the hotkey, ensuring you never miss the beginning of an utterance.
- **High-Performance Transcription**: Leverages `faster-whisper` with an NVIDIA GPU and INT8 quantization for fast and accurate results.
- **Direct Text Input**: Uses `pynput` to reliably type the final text into any active application window, avoiding external dependencies like `xdotool`.
- **Stable & Responsive**: A non-blocking, multi-threaded design ensures the application remains responsive, even during transcription.

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

### 2. Installation

1.  **Clone the Repository**
    ```bash
    git clone <your-repo-url>
    cd whisper-ptt
    ```

2.  **Create a Python Virtual Environment**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3.  **Install Python Dependencies**
    First, install `torch` with CUDA support. Find the correct version for your CUDA installation on the [PyTorch website](https://pytorch.org/get-started/locally/). For CUDA 12.1, the command is:
    ```bash
    pip install torch --index-url https://download.pytorch.org/whl/cu121
    ```
    Then, install the remaining packages from `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```

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

You can easily customize the script by editing the constants at the top of `whisper-ptt-v1.py`.

### Hotkey

The push-to-talk hotkey can be configured by modifying the `HOTKEY_COMBO` variable. It is a `set` that can contain one or more keys from `pynput.keyboard.Key`.

**Example: Single Key (Left Ctrl)**
```python
HOTKEY_COMBO: Final[set] = {keyboard.Key.ctrl_l}
```

**Example: Key Combination (Left Ctrl + Left Shift)**
```python
HOTKEY_COMBO: Final[set] = {keyboard.Key.ctrl_l, keyboard.Key.shift_l}
```
