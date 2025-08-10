# Technical Debugging Guide for Whisper PTT

This guide provides high-level troubleshooting steps for developers working on this project. It covers the two most complex and sensitive areas of the application: the NVIDIA CUDA environment and the GTK graphical interface dependencies.

---

## 1. CUDA Environment and GPU Acceleration

This project uses `faster-whisper`, which relies on `ctranslate2` and `PyTorch` for GPU acceleration. The interaction between the NVIDIA driver, the CUDA toolkit, and the Python libraries is extremely sensitive.

### Symptoms of a Problem:
- `RuntimeError: CUDA failed with error unknown error`
- `UserWarning: CUDA initialization: CUDA unknown error`
- `False` being returned from `torch.cuda.is_available()`
- `libcudnn_ops_infer.so.8: cannot open shared object file`

### Debugging Workflow:

1.  **Verify the Base Driver:**
    Always start with the ground truth. This command shows the installed driver version and the maximum CUDA version it supports.
    ```bash
    nvidia-smi
    ```

2.  **Isolate the Python Environment:**
    The most crucial test. Run this from within the activated virtual environment.
    ```bash
    python -c "import torch; print(torch.cuda.is_available())"
    ```
    If this returns `False`, the problem is with PyTorch's ability to initialize. Do not proceed until this works.

3.  **Check for Environment Contamination:**
    The `CUDA unknown error` is often caused by incorrect environment variables. Check for any custom settings of `LD_LIBRARY_PATH` or `CUDA_VISIBLE_DEVICES` in your shell's startup files (e.g., `~/.zshrc`, `~/.bashrc`). **An incorrectly set `LD_LIBRARY_PATH` is a primary cause of PyTorch CUDA initialization failure.**

4.  **The "Stuck Driver" Problem:**
    If all configurations appear correct but the error persists, the NVIDIA driver state may be corrupted in memory. This was the ultimate solution in our debugging session.
    *   **Solution:** A full system reboot. This forces the OS to reload the driver from a clean state.

5.  **The `libcudnn` Library Path Issue:**
    Once `torch.cuda.is_available()` returns `True`, the application may still fail with a `cannot open shared object file` error. This means the `ctranslate2` backend needs `LD_LIBRARY_PATH` to be set, but setting it globally can break PyTorch.
    *   **Solution:** Use the provided `run.sh` script. It sets the variable correctly for the application's execution context only, which is the most robust solution.

**Relevant Documentation:**
- [PyTorch - Get Started (Local)](https://pytorch.org/get-started/locally/)

---

## 2. GTK Interface (PyGObject) Dependencies

The system tray icon relies on GTK, accessed via `PyGObject`. This library has critical system-level dependencies.

### Symptoms of a Problem:
- `FATAL: PyGObject is not installed.`
- During `pip install PyGObject`: `ERROR: Dependency 'girepository-2.0' is required but not found.`

### Debugging Workflow:

1.  **Understand the Root Cause:**
    `PyGObject` can be installed in two ways: compiled from source by `pip`, or by using the version provided by the system's package manager. Compiling from source is fragile and requires many development headers. Using the system's version is more reliable.

2.  **The Correct Solution: Symlinking**
    This project is configured to use the stable, pre-compiled `PyGObject` provided by the OS. This avoids the complex build process entirely.
    *   **Step 1 - Install System Package:** Ensure the correct GTK bindings and development files are installed via `apt`. For Debian 12 "Bookworm", the comprehensive command is:
        ```bash
        sudo apt install libgirepository1.0-dev libcairo2-dev pkg-config python3-dev python3-gi gir1.2-gtk-3.0 libgtk-3-dev
        ```
    *   **Step 2 - Create the Symlink:** Link the system's `gi` module into the project's virtual environment. This makes it available to the application.
        ```bash
        ln -s /usr/lib/python3/dist-packages/gi .venv/lib/python3.11/site-packages/gi
        ```

This symlink method is the **intended and most stable** way to resolve GTK dependencies for this project.

**Relevant Documentation:**
- [PyGObject - Getting Started](https://pygobject.readthedocs.io/en/latest/getting_started.html)

---

## 3. Autostart and Runtime Issues

If the application fails to start automatically or stops working correctly after the system has been running for a while (especially after resuming from suspend), follow these steps.

### Symptoms of a Problem:
- The tray icon does not appear after logging in.
- The tray icon is visible, but transcription fails silently.

### Debugging Workflow:

1.  **Check the Autostart Configuration:**
    The application is launched via an XDG Autostart file. First, ensure this file is correctly configured:
    ```bash
    cat ~/.config/autostart/whisper-ptt.desktop
    ```
    Verify that the `Exec` and `Icon` paths are correct and absolute.

2.  **Check for a Stale Process:**
    If the application is in a bad state, a stale process might still be running. Find and kill it before attempting to debug further.
    ```bash
t    kill $(pgrep -f "python /home/cad/dev/whisper-ptt-v1/whisper-ptt.py")
    ```

3.  **Run Manually for Live Logs:**
    The most effective way to diagnose a runtime issue is to run the application manually from a terminal. This provides a live view of all log messages, including any errors that occur during transcription or recovery.
    ```bash
    /home/cad/dev/whisper-ptt-v1/run.sh
    ```
    After running this command, try to reproduce the issue (e.g., by suspending and resuming the system). Any errors will be printed directly to your terminal.
