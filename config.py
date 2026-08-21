"""Model and database configuration."""

import json
import os
import urllib.request
from dataclasses import dataclass
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel


# --- Paths and URLs ---

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "ecommerce.db")
CONTEXT_WINDOW = 8192
OLLAMA_URL = "http://127.0.0.1:11434"


# --- Model config ---

@dataclass
class ModelConfig:
    name: str
    temperature: float


FALLBACK_MODEL = ModelConfig(name="qwen2.5-coder:14b", temperature=0)


# --- Model creation ---

def create_model(config: ModelConfig, num_ctx: int = CONTEXT_WINDOW) -> BaseChatModel:
    """Instantiate a ChatOllama model from a ModelConfig.

    -- num_ctx is passed at call time so the UI can override CONTEXT_WINDOW. --
    """
    return ChatOllama(
        model=config.name,
        temperature=config.temperature,
        num_ctx=num_ctx,
        base_url=OLLAMA_URL,
    )


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
