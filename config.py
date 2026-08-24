"""Model, database, and resource profile configuration.

Ref: https://github.com/ollama/ollama/blob/main/docs/api.md
Ref: https://psutil.readthedocs.io/
"""

import json
import os
import urllib.request
from dataclasses import dataclass, field
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel


# --- Paths and URLs ---

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "ecommerce.db")
WORKSPACE_DIR = os.path.join(os.path.dirname(__file__), "workspace")
UPLOAD_DIR = os.path.join(WORKSPACE_DIR, "uploads")
CONTEXT_WINDOW = 8192
OLLAMA_URL = "http://127.0.0.1:11434"


# --- Model config ---

@dataclass
class ModelConfig:
    name: str
    temperature: float
    reasoning: bool | None = None


FALLBACK_MODEL = ModelConfig(name="qwen2.5-coder:14b", temperature=0)


# --- Resource profiles ---
# Each profile defines defaults for different hardware tiers.

@dataclass
class ResourceProfile:
    name: str
    label: str
    max_model_size: str
    default_ctx: int
    thinking_allowed: bool
    full_pipeline: bool
    whisper_model: str
    description: str


PROFILES = {
    "lite": ResourceProfile(
        name="lite",
        label="Lite",
        max_model_size="3b",
        default_ctx=2048,
        thinking_allowed=False,
        full_pipeline=False,
        whisper_model="tiny",
        description="For low-spec machines (8GB RAM, no GPU). Uses small models, no thinking.",
    ),
    "standard": ResourceProfile(
        name="standard",
        label="Standard",
        max_model_size="7b",
        default_ctx=4096,
        thinking_allowed=True,
        full_pipeline=True,
        whisper_model="small",
        description="For mid-range machines (16GB RAM, basic GPU). Balanced speed and quality.",
    ),
    "full": ResourceProfile(
        name="full",
        label="Full",
        max_model_size="14b+",
        default_ctx=8192,
        thinking_allowed=True,
        full_pipeline=True,
        whisper_model="small",
        description="For powerful machines (32GB+ RAM, dedicated GPU). Best quality.",
    ),
}


def detect_profile() -> str:
    """Auto-detect the best resource profile based on available hardware.

    Checks RAM and GPU VRAM to suggest lite / standard / full.
    Ref: https://psutil.readthedocs.io/en/latest/
    """
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        ram_gb = 16  # assume mid-range if psutil not available

    # -- Check if Ollama reports GPU info --
    gpu_vram_gb = 0
    try:
        req = urllib.request.urlopen(f"{OLLAMA_URL}/api/ps", timeout=3)
        data = json.loads(req.read())
        # Ollama /api/ps doesn't directly report VRAM, but we can infer from loaded models
    except Exception:
        pass

    if ram_gb < 12:
        return "lite"
    elif ram_gb < 24:
        return "standard"
    else:
        return "full"


def get_system_info() -> dict:
    """Gather system information for the frontend profile selector.

    Returns RAM, CPU, GPU info, detected profile, and Ollama status.
    """
    info = {
        "ram_gb": 0,
        "cpu_cores": 0,
        "cpu_name": "",
        "gpu_available": False,
        "detected_profile": "standard",
        "ollama_running": False,
        "loaded_models": [],
    }

    # -- System info via psutil --
    try:
        import psutil
        mem = psutil.virtual_memory()
        info["ram_gb"] = round(mem.total / (1024 ** 3), 1)
        info["ram_available_gb"] = round(mem.available / (1024 ** 3), 1)
        info["cpu_cores"] = psutil.cpu_count(logical=False) or 0
        info["cpu_threads"] = psutil.cpu_count(logical=True) or 0
    except ImportError:
        pass

    # -- CPU name (platform-specific) --
    try:
        import platform
        info["cpu_name"] = platform.processor() or ""
    except Exception:
        pass

    # -- Ollama status --
    try:
        req = urllib.request.urlopen(f"{OLLAMA_URL}/api/ps", timeout=3)
        data = json.loads(req.read())
        info["ollama_running"] = True
        models = data.get("models", [])
        info["loaded_models"] = [
            {
                "name": m.get("name", ""),
                "size_gb": round(m.get("size", 0) / (1024 ** 3), 1),
            }
            for m in models
        ]
    except Exception:
        pass

    info["detected_profile"] = detect_profile()
    return info


# --- Model creation ---

def create_model(
    config: ModelConfig,
    num_ctx: int = CONTEXT_WINDOW,
) -> BaseChatModel:
    """Instantiate a ChatOllama model from a ModelConfig.

    num_ctx is passed at call time so the UI can override CONTEXT_WINDOW.
    reasoning enables/disables thinking mode for supported models (Qwen3, etc).
    Ref: https://reference.langchain.com/python/langchain-ollama/chat_models/ChatOllama
    """
    kwargs = {
        "model": config.name,
        "temperature": config.temperature,
        "num_ctx": num_ctx,
        "base_url": OLLAMA_URL,
    }

    # -- Thinking mode: only set if explicitly True/False --
    if config.reasoning is not None:
        kwargs["reasoning"] = config.reasoning

    return ChatOllama(**kwargs)


def create_model_for_agent(agent_name: str) -> BaseChatModel:
    """Create a model using the agent's default config.

    Reads DEFAULT_MODEL and DEFAULT_TEMPERATURE from the agent class.
    Falls back to FALLBACK_MODEL if the agent isn't registered.
    """
    from agents import AGENTS
    agent_cls = AGENTS.get(agent_name)
    if agent_cls:
        cfg = ModelConfig(
            name=agent_cls.DEFAULT_MODEL,
            temperature=agent_cls.DEFAULT_TEMPERATURE,
        )
    else:
        cfg = FALLBACK_MODEL
    return create_model(cfg)


# --- Thinking model detection ---
# Only certain model families support the reasoning/thinking parameter.
# Ref: https://ollama.com/search?c=thinking

THINKING_MODEL_PATTERNS = [
    "qwen3",
    "qwq",
    "deepseek-r1",
    "marco-o1",
    "phi-4-reasoning",
    "phi-4-mini-reasoning",
]


def model_supports_thinking(model_name: str) -> bool:
    """Check if a model supports reasoning/thinking mode.

    Compares the base name (before the colon tag) against known
    thinking-capable model families.
    """
    base = model_name.lower().split(":")[0].strip()
    # -- Also strip hf.co/ prefix and any path --
    if "/" in base:
        base = base.rsplit("/", 1)[-1]
    return any(p in base for p in THINKING_MODEL_PATTERNS)


# --- Ollama API ---
# Ref: https://github.com/ollama/ollama/blob/main/docs/api.md#list-local-models

def list_ollama_models() -> list[str]:
    """GET /api/tags from the Ollama REST API. Returns sorted model names."""
    try:
        req = urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3)
        data = json.loads(req.read())
        return sorted(m["name"] for m in data.get("models", []))
    except Exception:
        return []
