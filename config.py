"""QueryMaster - Central Configuration
=====================================================================
Everything you need to customize is in this file.
Each section has comments explaining what the values do and why.

To get started after cloning:
  1. Install Ollama (https://ollama.com)
  2. Pull a model: ollama pull qwen2.5-coder:7b
  3. pip install -r requirements.txt
  4. python server.py

Sections:
  - Paths           Where data, logs, and user files live
  - Server          Host, port, reload mode
  - Ollama          LLM backend connection
  - Default Models  Which model each agent uses
  - Thinking Models Models that support chain-of-thought reasoning
  - Resource Profiles Hardware-based presets (lite/standard/full)
  - Agent Behavior  Iteration limits, retries, delegation
  - Tool Limits     Search depth, file size caps, web reading
  - Diagnostics     Memory profiler thresholds
=====================================================================
Ref: https://github.com/ollama/ollama/blob/main/docs/api.md
Ref: https://psutil.readthedocs.io/
"""

import json
import os
import urllib.request
from dataclasses import dataclass


# ===================================================================
# Paths
# ===================================================================
# All paths are relative to this file's directory (the project root).
# Change these if you want data stored elsewhere.

_ROOT_DIR = os.path.dirname(__file__)

# -- Data directory (SQLite databases) --
DATA_DIR = os.path.join(_ROOT_DIR, "data")

# -- Individual database paths --
DB_PATH = os.path.join(DATA_DIR, "ecommerce.db")         # sample e-commerce data for the SQL agent
CHAT_DB_PATH = os.path.join(DATA_DIR, "chat_history.db")  # conversation history
KNOWLEDGE_DB_PATH = os.path.join(DATA_DIR, "knowledge.db")  # agent knowledge base (Wissensdatenbank)
DIAGNOSTICS_DB_PATH = os.path.join(DATA_DIR, "diagnostics.db")  # memory profiler snapshots

# -- Workspace (where agents save files for the user) --
WORKSPACE_DIR = os.path.join(_ROOT_DIR, "workspace")
UPLOAD_DIR = os.path.join(WORKSPACE_DIR, "uploads")

# -- Logs --
LOG_DIR = os.path.join(_ROOT_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "actions.txt")


# ===================================================================
# Server
# ===================================================================
# The FastAPI server binds to these. Change the port if 8501 is taken.

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8501
SERVER_RELOAD = True  # auto-restart on code changes (disable in production)


# ===================================================================
# Ollama (LLM Backend)
# ===================================================================
# If Ollama is running on a different machine or port, change the URL.
# Ref: https://github.com/ollama/ollama/blob/main/docs/faq.md

OLLAMA_URL = "http://127.0.0.1:11434"


# ===================================================================
# Default Models
# ===================================================================
# Each agent has a DEFAULT_MODEL set in its own file (agents/*.py).
# This fallback is used when an agent's default is not available.
# Temperature 0 = deterministic, higher = more creative.

@dataclass
class ModelConfig:
    name: str
    temperature: float
    reasoning: bool | None = None

FALLBACK_MODEL = ModelConfig(name="qwen2.5-coder:14b", temperature=0)

# Default context window (tokens). Overridden per-profile and per-request.
CONTEXT_WINDOW = 8192


# ===================================================================
# Thinking Models
# ===================================================================
# Only certain model families support the reasoning/thinking parameter.
# Add new model families here as they become available.
# The check is substring-based: "qwen3" matches "qwen3:8b", "qwen3:14b", etc.
# Ref: https://ollama.com/search?c=thinking

THINKING_MODEL_PATTERNS = [
    "qwen3",
    "qwq",
    "deepseek-r1",
    "marco-o1",
    "phi-4-reasoning",
    "phi-4-mini-reasoning",
]


# ===================================================================
# Resource Profiles
# ===================================================================
# Hardware-based presets. The system auto-detects RAM and picks one,
# but the user can override in the frontend settings panel.
#
# To add a profile: add a new entry to PROFILES below.
# The frontend reads these via GET /api/profiles.

@dataclass
class ResourceProfile:
    name: str
    label: str
    max_model_size: str       # display only, not enforced
    default_ctx: int          # default context window for this tier
    thinking_allowed: bool    # show the thinking toggle in the UI
    full_pipeline: bool       # enable multi-agent delegation
    whisper_model: str        # faster-whisper model size (tiny/small/medium)
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


# ===================================================================
# Agent Behavior
# ===================================================================
# These control how agents work. Higher values = more thorough but slower.

# Max tool-call iterations per request before the agent gives up.
# 15 is enough for research + create + review workflows.
MAX_ITERATIONS = 15

# How many times a failed tool call is retried with the error fed back.
MAX_TOOL_RETRIES = 2

# Maximum delegation depth (agent A -> agent B -> agent C).
# 3 allows planner -> coder -> reviewer chains.
MAX_DELEGATION_DEPTH = 3

# Max iterations for a DELEGATED agent (can be lower than the top-level).
MAX_DELEGATION_ITERATIONS = 12

# How many knowledge entries to inject into the agent's system prompt.
KNOWLEDGE_INJECTION_LIMIT = 3

# Max chars per injected knowledge entry (longer = more context but costs tokens).
KNOWLEDGE_INJECTION_MAX_CHARS = 500


# ===================================================================
# Tool Limits
# ===================================================================
# Control how much data tools return. Higher = more thorough research
# but uses more tokens and slows down responses.

# -- Web search (DuckDuckGo) --
WEB_SEARCH_NUM_RESULTS = 6         # number of search results returned

# -- Web page reader --
WEB_READ_MAX_CHARS = 12000         # max chars extracted from a web page

# -- GitHub file reader --
GITHUB_FILE_MAX_CHARS = 15000      # max chars when fetching a GitHub file

# -- GitHub API --
GITHUB_USER_AGENT = "QueryMaster/1.0"


# ===================================================================
# Diagnostics (Memory Profiler)
# ===================================================================
# tracemalloc-based memory tracking. Runs automatically on server start.

# How many snapshots to keep in memory for quick comparison.
PROFILER_MAX_SNAPSHOTS = 20

# tracemalloc frame depth (higher = more detail, more overhead).
PROFILER_NFRAMES = 10

# RSS thresholds for health checks (in MB).
PROFILER_RSS_WARN_MB = 512         # yellow warning
PROFILER_RSS_ALERT_MB = 1024       # red alert

# Traced memory growth that triggers a "possible leak" warning (in MB).
PROFILER_GROWTH_WARN_MB = 10


# ===================================================================
# Utility Functions
# ===================================================================
# Runtime helpers. You probably don't need to change these unless you're
# modifying the model layer or adding new LLM backends.


def model_supports_thinking(model_name: str) -> bool:
    """Check if a model supports reasoning/thinking mode.

    Compares the base name (before the colon tag) against known
    thinking-capable model families listed in THINKING_MODEL_PATTERNS.
    """
    base = model_name.lower().split(":")[0].strip()
    # -- Also strip hf.co/ prefix and any path --
    if "/" in base:
        base = base.rsplit("/", 1)[-1]
    return any(p in base for p in THINKING_MODEL_PATTERNS)


def create_model(
    config: ModelConfig,
    num_ctx: int = CONTEXT_WINDOW,
):
    """Instantiate a ChatOllama model from a ModelConfig.

    num_ctx is passed at call time so the UI can override CONTEXT_WINDOW.
    reasoning enables/disables thinking mode for supported models.
    Ref: https://reference.langchain.com/python/langchain-ollama/chat_models/ChatOllama
    """
    from langchain_ollama import ChatOllama

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


def create_model_for_agent(agent_name: str):
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


def detect_profile() -> str:
    """Auto-detect the best resource profile based on available hardware.

    Checks RAM to suggest lite / standard / full.
    Ref: https://psutil.readthedocs.io/en/latest/
    """
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        ram_gb = 16  # assume mid-range if psutil not available

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


def list_ollama_models() -> list[str]:
    """GET /api/tags from the Ollama REST API. Returns sorted model names.
    Ref: https://github.com/ollama/ollama/blob/main/docs/api.md#list-local-models
    """
    try:
        req = urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=3)
        data = json.loads(req.read())
        return sorted(m["name"] for m in data.get("models", []))
    except Exception:
        return []
