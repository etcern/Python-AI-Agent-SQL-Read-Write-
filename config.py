"""Model configuration - change these to swap AI models.

Each agent uses its own model. To change a model:
  1. Run: ollama pull <model_name>
  2. Update the name in AGENT_MODELS below.
  3. Restart the app.
"""

import os
from dataclasses import dataclass
from langchain_ollama import ChatOllama
from langchain_core.language_models import BaseChatModel

# --- Constants ---
# Path to the SQLite database file used by the SQL agent.
# If you change this, also update the path in app.py.
# Update context window and Ollama URL if necessary. The default context window is 8192 tokens, which is sufficient for most use cases.
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "ecommerce.db")
CONTEXT_WINDOW = 8192
OLLAMA_URL = "http://127.0.0.1:11434"


@dataclass
class ModelConfig:
    name: str
    temperature: float


# --- CHANGE MODELS HERE ---
# To use specialized models, pull them first:
#   ollama pull qwen2.5-coder:7b    (fast SQL, 4.7GB)
#   ollama pull qwen2.5:7b          (multilingual/translation, 4.7GB)
#
# Update the names below if necessary after a model change and restart.
AGENT_MODELS = {
    "sql":        ModelConfig(name="qwen2.5-coder:7b", temperature=0),
    "translator": ModelConfig(name="qwen2.5:7b", temperature=0.3),
    "coder":      ModelConfig(name="qwen2.5-coder:14b", temperature=0),
}

FALLBACK_MODEL = ModelConfig(name="qwen2.5-coder:14b", temperature=0)


def create_model(config: ModelConfig) -> BaseChatModel:
    return ChatOllama(
        model=config.name,
        temperature=config.temperature,
        num_ctx=CONTEXT_WINDOW,
        base_url=OLLAMA_URL,
    )


def create_model_for_agent(agent_name: str) -> BaseChatModel:
    config = AGENT_MODELS.get(agent_name, FALLBACK_MODEL)
    return create_model(config)
