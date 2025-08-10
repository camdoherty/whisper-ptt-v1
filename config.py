import logging
import pathlib
from dataclasses import dataclass, field

import tomli

#region Configuration Loading
@dataclass
class AudioConfig:
    device: str | int | None = None
    sample_rate: int = 16000
    block_duration_ms: int = 30
    ring_buffer_duration_s: float = 3.0
    pre_roll_s: float = 0.7
    post_roll_s: float = 0.3

@dataclass
class ModelConfig:
    path: str = "models/faster-whisper-medium.en-int8/"
    compute_type: str = "int8_float32"
    device: str = "cuda"
    beam_size: int = 5
    repetition_penalty: float = 1.2
    log_prob_threshold: float | None = -1.0
    vad_min_silence_ms: int = 500

@dataclass
class UIConfig:
    hotkeys: list[str] = field(default_factory=lambda: ["ctrl_r", "shift_r"])
    hotkey_voicenote: list[str] = field(default_factory=lambda: ["ctrl_r", "alt_r"])
    voicenote_file: str = "~/ObsidianVault/🎙️VoiceNotes.md"
    enable_audio_cues: bool = True

@dataclass
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    ui: UIConfig = field(default_factory=UIConfig)


def load_or_create_config(path: str = "config.toml") -> AppConfig:
    config_path = pathlib.Path(path)
    if not config_path.exists():
        logging.info(f"Config file not found. Creating a default '{path}'.")
        default_config_str = f"""
[audio]
device = "default"
sample_rate = 16000

[model]
path = "models/faster-whisper-medium.en-int8/"
compute_type = "int8_float32"
device = "cuda"

[ui]
hotkeys = ["ctrl_r", "shift_r"]
hotkey_voicenote = ["ctrl_r", "alt_r"]
voicenote_file = "~/ObsidianVault/🎙️VoiceNotes.md"
enable_audio_cues = true
"""
        config_path.write_text(default_config_str.strip())
    with open(config_path, "rb") as f:
        toml_data = tomli.load(f)
    app_conf = AppConfig()
    app_conf.audio = AudioConfig(**toml_data.get("audio", {}))
    app_conf.model = ModelConfig(**toml_data.get("model", {}))
    app_conf.ui = UIConfig(**toml_data.get("ui", {}))
    return app_conf
#endregion
