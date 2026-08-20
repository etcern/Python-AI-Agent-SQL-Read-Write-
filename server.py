"""QueryMaster — FastAPI backend serving the chat API and static frontend.

Ref: https://fastapi.tiangolo.com/
Ref: https://fastapi.tiangolo.com/tutorial/static-files/
"""

import os
import sqlite3
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_core.messages import AIMessage, HumanMessage

from config import (
    DB_PATH, CONTEXT_WINDOW, AGENT_MODELS,
    ModelConfig, create_model, list_ollama_models,
)
from agents import AGENTS
from chat_store import (
    init_db, create_chat, list_chats, get_chat,
    update_chat, delete_chat, add_message, get_messages,
)


# --- App setup ---

app = FastAPI(title="QueryMaster")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


# --- Agent display names ---

AGENT_DISPLAY = {
    "sql":        {"name": "SQL Assistant",
                   "description": "Queries databases using natural language."},
    "translator": {"name": "Translator",
                   "description": "Translates text between languages."},
    "coder":      {"name": "Coder",
                   "description": "Writes, explains, and debugs code."},
}


# --- Request / response models ---
# Ref: https://fastapi.tiangolo.com/tutorial/body/

class CreateChatBody(BaseModel):
    agent: str = "sql"
    model: str | None = None


class UpdateChatBody(BaseModel):
    title: str | None = None
    agent: str | None = None
    model: str | None = None


class SendMessageBody(BaseModel):
    content: str
    context_window: int = CONTEXT_WINDOW


# --- Helpers ---

def _auto_title(text: str) -> str:
    """First message becomes the chat title (max 30 chars)."""
    title = text.strip().replace("\n", " ")
    return title[:30] + ("..." if len(title) > 30 else "")


def _rebuild_langchain_history(agent_name: str,
                               messages: list[dict]) -> list:
    """Build a LangChain message list from stored messages.

    Starts with the agent's SystemMessage, then converts each stored
    row into HumanMessage / AIMessage.  The latest user message is
    NOT included — agent.ask() appends it itself.
    Ref: https://python.langchain.com/docs/concepts/messages
    """
    agent = AGENTS[agent_name]()
    history = agent.create_history()
    for msg in messages:
        if msg["role"] == "user":
            history.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            history.append(AIMessage(content=msg["content"]))
    return history


def _get_table_info() -> list[dict]:
    """Table names + row counts from ecommerce.db.
    Ref: https://docs.python.org/3/library/sqlite3.html
    """
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
    )
    tables = [r[0] for r in cur.fetchall()]
    result = []
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM [{t}];")
        result.append({"name": t, "rows": cur.fetchone()[0]})
    conn.close()
    return result


# --- Initialize DB on startup ---

init_db()


# --- API: Chats ---
# Ref: https://fastapi.tiangolo.com/tutorial/path-params/

@app.get("/api/chats")
def api_list_chats():
    """All chats, newest first."""
    return list_chats()


@app.post("/api/chats", status_code=201)
def api_create_chat(body: CreateChatBody):
    """Create a new chat with a given agent (defaults to sql)."""
    if body.agent not in AGENTS:
        raise HTTPException(400, f"Unknown agent: {body.agent}")

    model_name = body.model
    if model_name is None:
        cfg = AGENT_MODELS.get(body.agent)
        model_name = cfg.name if cfg else "qwen2.5-coder:7b"

    chat_id = uuid.uuid4().hex[:8]
    return create_chat(chat_id, body.agent, model_name)


@app.delete("/api/chats/{chat_id}")
def api_delete_chat(chat_id: str):
    if not delete_chat(chat_id):
        raise HTTPException(404, "Chat not found")
    return {"ok": True}


@app.patch("/api/chats/{chat_id}")
def api_update_chat(chat_id: str, body: UpdateChatBody):
    chat = get_chat(chat_id)
    if not chat:
        raise HTTPException(404, "Chat not found")

    updates: dict = {}
    if body.title is not None:
        updates["title"] = body.title
    if body.model is not None:
        updates["model"] = body.model

    # -- When agent changes, switch to the new agent's default model --
    if body.agent is not None:
        if body.agent not in AGENTS:
            raise HTTPException(400, f"Unknown agent: {body.agent}")
        updates["agent"] = body.agent
        if body.model is None:
            cfg = AGENT_MODELS.get(body.agent)
            updates["model"] = cfg.name if cfg else chat["model"]

    return update_chat(chat_id, **updates)


# --- API: Messages ---

@app.get("/api/chats/{chat_id}/messages")
def api_get_messages(chat_id: str):
    chat = get_chat(chat_id)
    if not chat:
        raise HTTPException(404, "Chat not found")
    return get_messages(chat_id)


@app.post("/api/chats/{chat_id}/messages")
def api_send_message(chat_id: str, body: SendMessageBody):
    """Save user message, run the agent, save + return the response.

    Rebuilds LangChain history from SQLite on every call so no in-memory
    state is needed between requests.
    """
    chat = get_chat(chat_id)
    if not chat:
        raise HTTPException(404, "Chat not found")

    # -- Persist user message --
    add_message(chat_id, "user", body.content)

    # -- Auto-title on first user message --
    all_msgs = get_messages(chat_id)
    user_msgs = [m for m in all_msgs if m["role"] == "user"]
    if len(user_msgs) == 1:
        update_chat(chat_id, title=_auto_title(body.content))

    # -- Rebuild history WITHOUT the message we just saved
    #    (agent.ask() appends it internally) --
    history_msgs = all_msgs[:-1]
    lc_history = _rebuild_langchain_history(chat["agent"], history_msgs)

    # -- Run the agent --
    try:
        agent = AGENTS[chat["agent"]]()
        cfg = AGENT_MODELS.get(chat["agent"])
        temperature = cfg.temperature if cfg else 0

        model = create_model(
            ModelConfig(name=chat["model"], temperature=temperature),
            num_ctx=body.context_window,
        )
        model_with_tools = agent.bind_tools(model)
        response = agent.ask(
            query=body.content,
            history=lc_history,
            model=model_with_tools,
        )
    except Exception as exc:
        response = f"Error: {exc}"

    # -- Persist assistant response --
    add_message(chat_id, "assistant", response)

    return {
        "role": "assistant",
        "content": response,
        "chat": get_chat(chat_id),
    }


# --- API: Agents ---

@app.get("/api/agents")
def api_list_agents():
    """All registered agents with display info, tools, and defaults."""
    result = []
    for key in AGENTS:
        info = AGENT_DISPLAY.get(key, {"name": key, "description": ""})
        agent = AGENTS[key]()
        tools = [t.name for t in agent.get_all_tools()]
        cfg = AGENT_MODELS.get(key)
        result.append({
            "key": key,
            "name": info["name"],
            "description": info["description"],
            "tools": tools,
            "default_model": cfg.name if cfg else None,
            "temperature": cfg.temperature if cfg else 0,
        })
    return result


# --- API: Models + DB info ---

@app.get("/api/models")
def api_list_models():
    """List locally-available Ollama models.
    Ref: https://github.com/ollama/ollama/blob/main/docs/api.md#list-local-models
    """
    return {"models": list_ollama_models()}


@app.get("/api/db-info")
def api_db_info():
    """Table names + row counts from ecommerce.db."""
    return {"tables": _get_table_info()}


# --- Static files + SPA fallback ---
# Ref: https://fastapi.tiangolo.com/tutorial/static-files/

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_index():
    """Serve the single-page frontend."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))


# --- Run ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8501, reload=True)
