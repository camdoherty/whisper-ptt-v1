import logging
import pathlib
from dataclasses import dataclass, field

# tomllib on 3.11+, fallback to tomli if needed
try:
    import tomllib as tomli
except ModuleNotFoundError:
    import tomli

# region Configuration Loading
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
    # Model & runtime
    path: str = "models/faster-whisper-medium.en-int8/"
    compute_type: str = "int8_float32"
    device: str = "cuda"

    # Decoding/search
    beam_size: int = 5
    repetition_penalty: float = 1.2
    log_prob_threshold: float | None = -1.0
    temperature: float | list[float] | None = None
    patience: float | None = None
    length_penalty: float | None = None
    best_of: int | None = None

    # Accuracy/filters
    compression_ratio_threshold: float | None = None
    no_speech_threshold: float | None = None
    condition_on_previous_text: bool | None = None
    initial_prompt: str | None = None
    word_timestamps: bool | None = None
    language: str | None = None  # app defaults to "en" if not set

    # VAD extras
    vad_min_silence_ms: int = 500
    vad_threshold: float | None = None
    vad_speech_pad_ms: int | None = None

    # CPU/loader hints (applied if provided & supported)
    cpu_threads: int | None = None
    num_workers: int | None = None

    # Env caps (applied before importing numpy/BLAS)
    omp_num_threads: int | None = None
    mkl_num_threads: int | None = None
    openblas_num_threads: int | None = None


@dataclass
class UIConfig:
    hotkeys: list[str] = field(default_factory=lambda: ["ctrl_r", "shift_r"])
    hotkey_voicenote: list[str] = field(default_factory=lambda: ["ctrl_r", "alt_r"])
    voicenote_file: str = "~/ObsidianVault1/🎙️VoiceNotes.md"
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
block_duration_ms = 30
ring_buffer_duration_s = 6.5
pre_roll_s = 0.85
post_roll_s = 0.20

[model]
path = "models/faster-whisper-small.en-int8/"
compute_type = "int8"
device = "cpu"

# latency/quality
beam_size = 1
repetition_penalty = 1.2
log_prob_threshold = -1.0

# stability & filters
language = "en"
temperature = 0.0
compression_ratio_threshold = 2.4
no_speech_threshold = 0.6
condition_on_previous_text = false
word_timestamps = false

# VAD
vad_min_silence_ms = 300
vad_speech_pad_ms = 30

# CPU hints
cpu_threads = 4
num_workers = 1

# Env caps (applied before numpy/BLAS import)
omp_num_threads = 4
mkl_num_threads = 1
openblas_num_threads = 1

[ui]
hotkeys = ["ctrl_r", "shift_r"]
hotkey_voicenote = ["ctrl_r", "alt_r"]
voicenote_file = "~/ObsidianVault1/🎙️VoiceNotes.md"
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
# endregion
