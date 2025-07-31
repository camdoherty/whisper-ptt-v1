#!/bin/bash

# Get the absolute path to the project directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Set the library path to the one inside the virtual environment
export LD_LIBRARY_PATH="$DIR/.venv/lib/python3.11/site-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH"

# Activate the virtual environment and run the application
source "$DIR/.venv/bin/activate"
python "$DIR/whisper-ptt-v1.py"
