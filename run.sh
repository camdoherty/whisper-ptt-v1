#!/bin/bash

# Get the absolute path to the project directory
DIR=$(dirname "$(readlink -f "$0")")

# Set the library path to the one inside the virtual environment
export LD_LIBRARY_PATH="$DIR/.venv/lib/python3.11/site-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH"

# Activate the virtual environment and run the application
cd "$DIR"
source "$DIR/.venv/bin/activate"
python "$DIR/whisper-ptt.py"
