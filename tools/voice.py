"""Voice transcription - server-side speech-to-text using faster-whisper.

Runs 100% locally. No audio data leaves the machine.
Falls back gracefully if faster-whisper is not installed.

Install: pip install faster-whisper
Ref: https://github.com/SYSTRAN/faster-whisper
"""

import os
import tempfile
from logging_utils import log_panel

# -- Lazy load: don't crash the app if faster-whisper isn't installed --
_model = None
_model_size = None


def _is_available() -> bool:
    """Check if faster-whisper is installed."""
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _get_model(size: str = "auto"):
    """Load or reuse the whisper model. Auto-selects size based on RAM.

    Model sizes:
      tiny   - ~75MB  RAM, fastest, least accurate
      base   - ~140MB RAM, good balance for quick commands
      small  - ~460MB RAM, best quality for general use
      medium - ~1.5GB RAM, high quality
      large  - ~3GB  RAM, highest quality
    """
    global _model, _model_size

    if size == "auto":
        try:
            import psutil
            ram_gb = psutil.virtual_memory().total / (1024 ** 3)
            if ram_gb < 12:
                size = "tiny"
            elif ram_gb < 20:
                size = "small"
            else:
                size = "small"
        except ImportError:
            size = "tiny"

    if _model is not None and _model_size == size:
        return _model

    from faster_whisper import WhisperModel

    log_panel(f"Loading whisper model: {size}", title="Voice - Init")

    # -- Use CPU with int8 quantization for speed --
    _model = WhisperModel(size, device="cpu", compute_type="int8")
    _model_size = size
    log_panel(f"Whisper model '{size}' ready", title="Voice - Ready")
    return _model


def transcribe(audio_path: str, model_size: str = "auto") -> dict:
    """Transcribe an audio file to text.

    Args:
        audio_path: Path to the audio file (wav, mp3, m4a, webm, ogg).
        model_size: Whisper model size (tiny/base/small/medium/large/auto).

    Returns:
        Dict with 'text', 'language', and 'duration' keys.
    """
    if not _is_available():
        return {
            "error": "faster-whisper not installed. "
                     "Install with: pip install faster-whisper",
            "text": "",
        }

    if not os.path.exists(audio_path):
        return {"error": f"Audio file not found: {audio_path}", "text": ""}

    model = _get_model(model_size)
    segments, info = model.transcribe(
        audio_path,
        beam_size=5,
        vad_filter=True,
    )

    text_parts = []
    for segment in segments:
        text_parts.append(segment.text.strip())

    text = " ".join(text_parts)
    log_panel(f"Transcribed {info.duration:.1f}s of audio", title="Voice - Done")

    return {
        "text": text,
        "language": info.language,
        "duration": round(info.duration, 2),
    }


def voice_status() -> dict:
    """Check voice transcription availability and model info."""
    available = _is_available()
    return {
        "available": available,
        "model_loaded": _model is not None,
        "model_size": _model_size,
        "install_hint": "pip install faster-whisper" if not available else None,
    }
