#!/bin/bash
#
# setup_venv.sh
#
# This script automates the setup of the Python virtual environment for the
# whisper-ptt-v1 project. It handles the following:
#
# 1. Deletes any existing virtual environment to ensure a clean start.
# 2. Creates a new Python virtual environment named '.venv'.
# 3. Symlinks the system's 'gi' (PyGObject) package into the virtual
#    environment. This is necessary for the GTK interface to work.
# 4. Installs all required Python packages from requirements.txt.
# 5. Appends the LD_LIBRARY_PATH export to the venv's activate script
#    to ensure CUDA libraries are found.
#

set -e

VENV_DIR=".venv"
SYSTEM_GI_PATH="/usr/lib/python3/dist-packages/gi"
VENV_SITE_PACKAGES_PATH="$VENV_DIR/lib/python3.11/site-packages"

echo "--- Setting up Python virtual environment for Whisper PTT ---"

# 1. Remove existing venv if it exists
if [ -d "$VENV_DIR" ]; then
    echo "Removing existing virtual environment..."
    rm -rf "$VENV_DIR"
fi

# 2. Create a new virtual environment
echo "Creating new virtual environment..."
python3 -m venv "$VENV_DIR"

# 3. Activate the virtual environment for the current script's context
source "$VENV_DIR/bin/activate"

# 4. Symlink the system 'gi' package
if [ -d "$SYSTEM_GI_PATH" ]; then
    echo "Symlinking system 'gi' package..."
    ln -s "$SYSTEM_GI_PATH" "$VENV_SITE_PACKAGES_PATH/gi"
else
    echo "WARNING: System 'gi' package not found at $SYSTEM_GI_PATH."
    echo "The GTK interface may not work."
fi

# 5. Install Python dependencies
echo "Installing Python packages from requirements.txt..."
pip install -r requirements.txt

# 6. Add CUDA library path to the activate script
echo "Configuring CUDA library path..."
CUDA_LIB_PATH_EXPORT="export LD_LIBRARY_PATH=\"$VIRTUAL_ENV/lib/python3.11/site-packages/nvidia/cudnn/lib:\$LD_LIBRARY_PATH\""
echo -e "\n# Add CUDA libraries to the path\n$CUDA_LIB_PATH_EXPORT" >> "$VENV_DIR/bin/activate"

echo "--- Setup complete! ---"
echo "To activate the environment, run: source $VENV_DIR/bin/activate"
