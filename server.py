"""QueryMaster - FastAPI backend serving the chat API and static frontend.

Ref: https://fastapi.tiangolo.com/
Ref: https://fastapi.tiangolo.com/tutorial/static-files/
"""

import json
import os
import sqlite3
import tempfile
import uuid

from pathlib import PurePosixPath

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from langchain_core.messages import AIMessage, HumanMessage

from config import (
    DB_PATH, CONTEXT_WINDOW, UPLOAD_DIR, PROFILES,
    ModelConfig, create_model, list_ollama_models,
    detect_profile, get_system_info,
)
from agents import AGENTS
from chat_store import (
    init_db, create_chat, list_chats, get_chat,
    update_chat, delete_chat, add_message, get_messages,
)
from knowledge_store import (
    init_knowledge_db, save_entry, search_entries,
    list_entries, get_entry, delete_entry,
)
from tools.memory_profiler import (
    init_diagnostics_db, start_profiling, take_snapshot,
    compare_snapshots, get_memory_summary, get_snapshot_history,
    get_snapshot_detail, check_memory_health, is_profiling,
)


# --- App setup ---

app = FastAPI(title="QueryMaster")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


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
    internet_enabled: bool = True
    confirmation_mode: bool = False
    thinking_enabled: bool | None = None


# --- Helpers ---

def _auto_title(text: str) -> str:
    """First message becomes the chat title (max 30 chars)."""
    title = text.strip().replace("\n", " ")
    return title[:30] + ("..." if len(title) > 30 else "")


def _rebuild_langchain_history(agent_name: str,
                               messages: list[dict],
                               query: str = "",
                               include_internet: bool = True,
                               confirmation_mode: bool = False,
                               thinking_enabled: bool | None = None) -> list:
    """Build a LangChain message list from stored messages.

    Starts with the agent's SystemMessage, then converts each stored
    row into HumanMessage / AIMessage.  The latest user message is
    NOT included - agent.ask() appends it itself.
    Ref: https://python.langchain.com/docs/concepts/messages
    """
    agent = AGENTS[agent_name](
        include_internet=include_internet,
        confirmation_mode=confirmation_mode,
        thinking_enabled=thinking_enabled,
    )
    history = agent.create_history(query=query)
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


# --- Initialize DBs + profiler on startup ---

init_db()
init_knowledge_db()
init_diagnostics_db()
start_profiling(nframes=10)
take_snapshot(label="server_start", snapshot_type="baseline", save_to_db=True)


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

    # -- Read default model from the agent class --
    agent_cls = AGENTS[body.agent]
    model_name = body.model or agent_cls.DEFAULT_MODEL

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
            updates["model"] = AGENTS[body.agent].DEFAULT_MODEL

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
    lc_history = _rebuild_langchain_history(
        chat["agent"], history_msgs,
        query=body.content,
        include_internet=body.internet_enabled,
        confirmation_mode=body.confirmation_mode,
        thinking_enabled=body.thinking_enabled,
    )

    # -- Run the agent --
    try:
        agent = AGENTS[chat["agent"]](
            include_internet=body.internet_enabled,
            confirmation_mode=body.confirmation_mode,
            thinking_enabled=body.thinking_enabled,
        )
        temperature = AGENTS[chat["agent"]].DEFAULT_TEMPERATURE

        # -- Set reasoning param based on thinking toggle --
        reasoning = agent.thinking_enabled if agent.thinking_enabled else None

        model = create_model(
            ModelConfig(
                name=chat["model"],
                temperature=temperature,
                reasoning=reasoning,
            ),
            num_ctx=body.context_window,
        )
        model_with_tools = agent.bind_tools(model)
        response = agent.ask(
            query=body.content,
            history=lc_history,
            model=model_with_tools,
            num_ctx=body.context_window,
        )
    except Exception as exc:
        response = f"Error: {exc}"

    # -- Collect tool events before overwrite on error --
    tool_events = getattr(agent, "tool_events", [])

    # -- Persist assistant response --
    add_message(chat_id, "assistant", response)

    return {
        "role": "assistant",
        "content": response,
        "tool_events": tool_events,
        "chat": get_chat(chat_id),
    }


# --- API: Streaming messages (SSE) ---
# Ref: https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events

@app.post("/api/chats/{chat_id}/messages/stream")
def api_send_message_stream(chat_id: str, body: SendMessageBody):
    """Stream agent response via Server-Sent Events.

    Tool calls appear as events in real-time. The final answer
    streams token by token. Saves to DB when complete.
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

    history_msgs = all_msgs[:-1]
    lc_history = _rebuild_langchain_history(
        chat["agent"], history_msgs,
        query=body.content,
        include_internet=body.internet_enabled,
        confirmation_mode=body.confirmation_mode,
        thinking_enabled=body.thinking_enabled,
    )

    agent = AGENTS[chat["agent"]](
        include_internet=body.internet_enabled,
        confirmation_mode=body.confirmation_mode,
        thinking_enabled=body.thinking_enabled,
    )
    temperature = AGENTS[chat["agent"]].DEFAULT_TEMPERATURE
    reasoning = agent.thinking_enabled if agent.thinking_enabled else None

    model = create_model(
        ModelConfig(
            name=chat["model"],
            temperature=temperature,
            reasoning=reasoning,
        ),
        num_ctx=body.context_window,
    )
    model_with_tools = agent.bind_tools(model)

    def event_generator():
        try:
            for event in agent.ask_stream(
                query=body.content,
                history=lc_history,
                model=model_with_tools,
                num_ctx=body.context_window,
            ):
                # -- Save to DB when done --
                if event["type"] == "done":
                    add_message(chat_id, "assistant", event["content"])
                    event["chat"] = get_chat(chat_id)
                    # -- Post-request memory snapshot (lightweight) --
                    try:
                        take_snapshot(
                            label=f"req:{chat['agent']}",
                            snapshot_type="request",
                            save_to_db=True,
                        )
                    except Exception:
                        pass

                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            error_event = {"type": "error", "content": f"Error: {exc}"}
            add_message(chat_id, "assistant", f"Error: {exc}")
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- API: Agents ---

@app.get("/api/agents")
def api_list_agents():
    """All registered agents with display info, tools, and defaults.

    Reads everything from the agent class - no separate display-name
    or model-config dicts needed.
    """
    result = []
    for key, agent_cls in AGENTS.items():
        agent = agent_cls()
        tools = [t.name for t in agent.get_all_tools()]
        result.append({
            "key": key,
            "name": agent_cls.DISPLAY_NAME,
            "description": agent_cls.DESCRIPTION,
            "tools": tools,
            "default_model": agent_cls.DEFAULT_MODEL,
            "temperature": agent_cls.DEFAULT_TEMPERATURE,
            "thinking_default": agent_cls.THINKING_DEFAULT,
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


# --- API: System info + profiles ---

@app.get("/api/system-info")
def api_system_info():
    """System hardware info and detected resource profile."""
    return get_system_info()


@app.get("/api/profiles")
def api_profiles():
    """Available resource profiles with descriptions."""
    return {
        "profiles": {
            k: {
                "name": p.name,
                "label": p.label,
                "max_model_size": p.max_model_size,
                "default_ctx": p.default_ctx,
                "thinking_allowed": p.thinking_allowed,
                "full_pipeline": p.full_pipeline,
                "description": p.description,
            }
            for k, p in PROFILES.items()
        },
        "detected": detect_profile(),
    }


# --- API: Memory diagnostics ---
# Ref: https://docs.python.org/3/library/tracemalloc.html


class SnapshotBody(BaseModel):
    label: str = "manual"


@app.get("/api/debug/memory")
def api_memory_status():
    """Current memory usage, health check, and recent trend."""
    return {
        "summary": get_memory_summary(),
        "health": check_memory_health(),
        "history": get_snapshot_history(limit=10),
    }


@app.post("/api/debug/memory/snapshot")
def api_take_snapshot(body: SnapshotBody):
    """Take a named memory snapshot and store it."""
    if not is_profiling():
        start_profiling()
    result = take_snapshot(label=body.label, snapshot_type="manual")
    return result


@app.get("/api/debug/memory/compare")
def api_compare_snapshots():
    """Compare the two most recent memory snapshots.

    Take at least two snapshots first (POST /api/debug/memory/snapshot).
    Shows which allocations grew, shrank, or appeared.
    """
    return compare_snapshots()


@app.get("/api/debug/memory/history")
def api_memory_history(limit: int = 30):
    """Snapshot history from diagnostics.db for trend analysis."""
    return get_snapshot_history(limit=limit)


@app.get("/api/debug/memory/snapshot/{snapshot_id}")
def api_get_snapshot(snapshot_id: int):
    """Single snapshot with full allocation details."""
    result = get_snapshot_detail(snapshot_id)
    if not result:
        raise HTTPException(404, "Snapshot not found")
    return result


# --- API: File uploads ---
# Ref: https://fastapi.tiangolo.com/tutorial/request-files/

def _safe_filename(name: str) -> str:
    """Strip directory components to prevent path traversal.
    Ref: https://docs.python.org/3/library/pathlib.html#pathlib.PurePosixPath
    """
    return PurePosixPath(name).name


@app.post("/api/uploads", status_code=201)
async def api_upload_file(file: UploadFile = File(...)):
    """Save an uploaded file to workspace/uploads/."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    safe_name = _safe_filename(file.filename or "unnamed")
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)
    return {"name": safe_name, "size": len(content)}


@app.get("/api/uploads")
def api_list_uploads():
    """List all files in workspace/uploads/."""
    if not os.path.exists(UPLOAD_DIR):
        return []
    files = []
    for name in sorted(os.listdir(UPLOAD_DIR)):
        path = os.path.join(UPLOAD_DIR, name)
        if os.path.isfile(path):
            files.append({"name": name, "size": os.path.getsize(path)})
    return files


@app.delete("/api/uploads/{filename}")
def api_delete_upload(filename: str):
    """Remove an uploaded file."""
    safe_name = _safe_filename(filename)
    filepath = os.path.join(UPLOAD_DIR, safe_name)
    if not os.path.exists(filepath):
        raise HTTPException(404, "File not found")
    os.remove(filepath)
    return {"ok": True}


# --- API: Voice transcription ---
# Ref: https://github.com/SYSTRAN/faster-whisper

@app.post("/api/transcribe")
async def api_transcribe(file: UploadFile = File(...)):
    """Transcribe uploaded audio to text using faster-whisper.

    Accepts wav, mp3, m4a, webm, ogg audio files.
    Returns transcribed text, detected language, and duration.
    Falls back with install instructions if faster-whisper isn't available.
    """
    from tools.voice import transcribe, voice_status

    status = voice_status()
    if not status["available"]:
        return {
            "text": "",
            "error": "Server-side transcription not available. "
                     "Install with: pip install faster-whisper",
            "fallback": "browser",
        }

    # -- Save uploaded audio to temp file --
    ext = os.path.splitext(file.filename or "audio.webm")[1]
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = transcribe(tmp_path)
    finally:
        os.unlink(tmp_path)

    return result


@app.get("/api/voice-status")
def api_voice_status():
    """Check if server-side voice transcription is available."""
    from tools.voice import voice_status
    return voice_status()


# --- API: Knowledge base (Wissensdatenbank) ---
# Ref: https://docs.python.org/3/library/sqlite3.html


class SaveKnowledgeBody(BaseModel):
    topic: str
    content: str
    source: str = "manual"


@app.get("/api/knowledge")
def api_list_knowledge(limit: int = 50):
    """Most recent knowledge entries."""
    return list_entries(limit=limit)


@app.get("/api/knowledge/search")
def api_search_knowledge(q: str = ""):
    """Search knowledge by keyword."""
    if not q.strip():
        return []
    return search_entries(q.strip())


@app.post("/api/knowledge", status_code=201)
def api_save_knowledge(body: SaveKnowledgeBody):
    """Manually add a knowledge entry."""
    return save_entry(body.topic, body.content, source=body.source)


@app.get("/api/knowledge/{entry_id}")
def api_get_knowledge(entry_id: int):
    """Single knowledge entry by ID."""
    entry = get_entry(entry_id)
    if not entry:
        raise HTTPException(404, "Knowledge entry not found")
    return entry


@app.delete("/api/knowledge/{entry_id}")
def api_delete_knowledge(entry_id: int):
    """Delete a knowledge entry."""
    if not delete_entry(entry_id):
        raise HTTPException(404, "Knowledge entry not found")
    return {"ok": True}


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
