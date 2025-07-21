# verify_stack.py
# A minimal script to test the compatibility of the core ML stack.

import numpy as np
import torch
from faster_whisper import WhisperModel
import ctranslate2
import sys
import os

# --- Configuration (match it to your main script) ---
MODEL_PATH = os.path.expanduser("~/dev/whisper/whisper-ptt/models/medium.en-int8/faster-whisper-medium.en-int8/")
COMPUTE_TYPE = "int8_float32"
DEVICE = "cuda"

def run_verification():
    """Tests the core components of the transcription stack."""
    print("--- Starting Environment Verification ---")

    # 1. Verify Python and Library Versions
    print(f"Python Version: {sys.version}")
    print(f"PyTorch Version: {torch.__version__}")
    print(f"ctranslate2 Version: {ctranslate2.__version__}")
    
    # 2. Verify CUDA and GPU Availability
    try:
        if not torch.cuda.is_available():
            print("\n[FATAL] PyTorch reports CUDA is NOT available.")
            return False
        
        gpu_name = torch.cuda.get_device_name(0)
        print(f"\n[OK] PyTorch CUDA is available.")
        print(f"[OK] Found GPU: {gpu_name}")

        if "1080" not in gpu_name:
            print(f"[WARN] Expected a GTX 1080, but found {gpu_name}.")

    except Exception as e:
        print(f"\n[FATAL] Error during CUDA check: {e}")
        return False

    # 3. Verify Model Loading and Quantization
    print("\n--- Testing Model Load and Quantization ---")
    try:
        print(f"Loading model '{MODEL_PATH}' with compute_type='{COMPUTE_TYPE}'...")
        model = WhisperModel(MODEL_PATH, device=DEVICE, compute_type=COMPUTE_TYPE)
        print("[OK] Model loaded successfully.")
        print("[INFO] On-the-fly quantization to INT8 (if needed) was successful.")
    except Exception as e:
        print(f"\n[FATAL] Failed to load the model: {e}")
        return False
    
    # 4. Verify Transcription
    print("\n--- Testing Transcription ---")
    try:
        # Create a dummy 5-second audio clip of silence with a beep
        sample_rate = 16000
        duration = 5
        t = np.linspace(0., 1., int(sample_rate * 1.0))
        amplitude = np.iinfo(np.int16).max * 0.2
        # A simple 440Hz sine wave (note 'A')
        beep = (amplitude * np.sin(2. * np.pi * 440. * t)).astype(np.float32)
        
        # Create a silent audio array and place the beep in the middle
        dummy_audio = np.zeros(sample_rate * duration, dtype=np.float32)
        dummy_audio[sample_rate:sample_rate+len(beep)] = beep
        
        print("Transcribing a dummy 5-second audio clip...")
        segments, _ = model.transcribe(dummy_audio, beam_size=5, language="en")
        
        transcription = " ".join([s.text for s in segments])
        print(f"[OK] Transcription finished. Result: '{transcription.strip()}'")
        # Note: The result may be empty or gibberish, which is fine. We just want it to not crash.

    except Exception as e:
        print(f"\n[FATAL] Transcription failed: {e}")
        return False

    print("\n--- Verification Complete ---")
    print("✅ Your environment appears to be correctly configured.")
    return True

if __name__ == "__main__":
    run_verification()
