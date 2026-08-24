# QueryMaster
A local AI agent platform using Python, HTML/CSS/JS and [Ollama](https://ollama.com) for fully offline LLM inference. Multiple agents, tool usage, knowledge base, streaming responses, voice input, file analysis, memory profiling. Everything runs on your machine.

---

## Note:
This Project has been developed using the help of [ClaudeAI](https://claude.ai/), especially on the Website Interface. <br><br>This is just the base for a local AI prompting interface, working together with Ollama API, in order to use local Chatbots inside a Web interface made out of Python, open source and fully modular. The design of the website has been inspired by [ClaudeAI](https://claude.ai/) website.

---

## What do I need?
1. Install [Ollama](https://ollama.com) from their official WebSite.<br>
2. Clone the repository<br>
3. Install the python libraries via the command `pip install -r requirements.txt` (make sure you have [pip installed](https://pip.pypa.io/en/stable/installation/))<br>
4. Open a terminal and type `ollama pull [model name]`. You can get models from [HuggingFace](https://huggingface.co) or from the [Ollama Website](https://ollama.com/search)<br>
5. Start `server.py`

### Optional installs:
```bash
pip install python-docx openpyxl     # DOCX and Excel file support
pip install faster-whisper            # Server-side voice transcription
winget install UB-Mannheim.TesseractOCR   # Image OCR (Windows)
```

---

## To add a new agent:
1. Create a new agent file under `agents/agent_name.py`
2. Copy/Paste the current Architecture from an already existing agent.
3. Modify your `SYSTEM_PROMPT` to your liking inside each Agent class
4. The agent gets auto-discovered

---

## Features:

### Search and Knowledge
- **Web Search**: All agents can search the internet via DuckDuckGo. No API key needed.<br>
- **GitHub Integration**: Agents can search GitHub repos, browse file trees, and fetch source code directly.<br>
- **Internet Toggle**: A button in the composer bar lets you enable/disable internet access. When OFF, agents work with local files and knowledge only.<br>
- **Wissensdatenbank (Knowledge Base)**: Agents save and retrieve learned information across sessions. Uses FTS5 full-text search with deduplication. Pre-load with `python scripts/populate_knowledge.py --all`.<br>
- **Smart Search Priority**: Agents first check the knowledge base, then local files, then the internet. Useful findings get saved automatically for next time.

### Agents and Pipeline
- **Multi-Agent Pipeline**: The Planner agent analyzes tasks, delegates to Coder/SQL/Reviewer agents, and assembles reviewed results through a 5-stage pipeline (analyze, plan, execute, review, report).<br>
- **Code Review Agent**: Standalone reviewer that checks code for correctness, security, performance, readability, error handling, and best practices.<br>
- **Agent Delegation**: Any agent can hand off tasks to another specialist. The Planner orchestrates complex multi-step work across agents.<br>
- **Auto-Discovery**: Drop a new agent file in `agents/` and it just works. No manual registration.

### Streaming and Thinking
- **Streaming Responses**: Token-by-token output via Server-Sent Events. Tool calls show in real-time as the agent works.<br>
- **Thinking Mode**: Chain-of-thought reasoning for models that support it. The toggle auto-disables for models without thinking support. If toggled on with an unsupported model, the server silently falls back to normal mode and shows a warning. See the [Thinking Models](#thinking-models) section below for compatible models.<br>
- **Thought Process Panel**: A collapsible panel on each response showing every tool call, reasoning, arguments, results, and severity badges (green/yellow/red).<br>
- **Retry on Error**: Error messages include a Retry button to re-send the last prompt without retyping it.

### Files and Voice
- **File Upload**: Upload files via the button or drag-and-drop them into the chat area.<br>
- **File Type Support**: Agents can read PDF, DOCX, XLSX, CSV, JSON, images (OCR), and plain text. Large files get truncated automatically.<br>
- **Voice Input**: Mic button in the composer bar uses the browser's built-in speech recognition (Chrome/Edge). Optional server-side transcription with faster-whisper for other browsers.<br>
- **Code Copy Buttons**: One-click copy on all code blocks in agent responses.

### Performance and Diagnostics
- **Resource Profiles**: Auto-detects your hardware (RAM, CPU) and suggests lite/standard/full profile. You can also pick manually in settings. Each profile sets context window size, model limits, and feature availability.<br>
- **Confirmation Mode**: A toggle that makes agents ask before executing write/modify operations. Shows what will change and waits for approval.<br>
- **History Trimming**: Automatically drops oldest messages when the conversation gets too long for the context window. Always keeps the system prompt and last 2 messages.<br>
- **Tool Retry**: If a tool call fails, the agent retries up to 2 times with the error fed back so it can self-correct.<br>
- **Memory Profiler**: Built-in tracemalloc profiler tracks Python allocations. Takes snapshots after each request, stores trend data in `diagnostics.db`. Agents can check their own memory usage. Debug API at `/api/debug/memory`.

---

## Agent Hierarchy:

| Agent | Role | Recommended Model | Stage |
|-------|------|-------------------|-------|
| Planner | Analyzes tasks, builds execution plans, delegates | 14b+ | Orchestrator |
| Coder | Writes, edits, and debugs code | 14b+ | Execute |
| Code Reviewer | Reviews code for bugs, security, quality | 14b+ | Review |
| SQL Assistant | Queries databases using natural language | 7b+ | Execute |
| Translator | Translates text between languages | 7b+ | Execute |

For complex tasks, use the **Planner** agent. It will delegate to the right specialists and have the Reviewer check the output.

---

## Thinking Models:

Not all models support thinking/reasoning mode. The toggle in the composer bar auto-disables for unsupported models. If you want thinking, pull one of these:

```bash
ollama pull qwen3:8b         # Good balance of speed and quality
ollama pull qwen3:14b        # Better reasoning, needs more RAM
ollama pull qwen3:30b        # Best quality, needs 32GB+ RAM
ollama pull deepseek-r1:8b   # Alternative thinking model
ollama pull qwq:32b          # Alibaba's reasoning model, heavy
```

Links:
- [Qwen3](https://ollama.com/library/qwen3) (recommended, multiple sizes from 0.6b to 235b)
- [DeepSeek-R1](https://ollama.com/library/deepseek-r1) (distilled versions available)
- [QwQ](https://ollama.com/library/qwq) (32b only)

Models like `qwen2.5-coder`, `granite`, `llama3` do NOT support thinking. The app detects this automatically and skips the reasoning parameter.

---

## Wissensdatenbank (Knowledge Base):

Pre-load the knowledge base so your agents have reference material from the start:

```bash
python scripts/populate_knowledge.py --all           # Load all built-in packs (35 entries)
python scripts/populate_knowledge.py --pack python    # Load a specific pack
python scripts/populate_knowledge.py --huggingface    # Import from HuggingFace (needs: pip install datasets)
python scripts/populate_knowledge.py --list           # Show available packs
python scripts/populate_knowledge.py --stats          # Show knowledge base stats
```

Available packs: python (10), sql (7), javascript (5), security (4), design_patterns (4), testing (3), fastapi (2).

---

## Resource Profiles:

The system checks your hardware on startup and picks a profile. You can override it in settings.

| Profile | RAM | Context | Models | Thinking | Notes |
|---------|-----|---------|--------|----------|-------|
| Lite | <12GB | 2048 | up to 3b | off | For old laptops, no GPU needed |
| Standard | 12-24GB | 4096 | up to 7b | on | Balanced, works on most machines |
| Full | 24GB+ | 8192 | 14b+ | on | Best quality, needs decent hardware |

---

## Debug API:

Memory profiling endpoints for tracking down leaks or high usage:

| Endpoint | Method | What it does |
|----------|--------|-------------|
| `/api/debug/memory` | GET | Current status, health check, last 10 snapshots |
| `/api/debug/memory/snapshot` | POST | Take a named snapshot (`{"label": "after_pdf_load"}`) |
| `/api/debug/memory/compare` | GET | Diff the two most recent snapshots |
| `/api/debug/memory/history` | GET | All snapshots from DB |

---

## Project structure:

```
agents/           # Agent definitions (auto-discovered)
  base.py         # Shared logic, tool retry, streaming, thinking, trimming
  coder_agent.py
  sql_agent.py
  reviewer_agent.py
  planner_agent.py
  translator_agent.py
tools/            # Tool modules (file, search, knowledge, voice, diagnostics)
  memory_profiler.py   # tracemalloc wrapper + diagnostics DB
  extractors.py        # PDF, DOCX, XLSX, CSV, image, JSON extraction
  voice.py             # faster-whisper transcription
scripts/          # Utility scripts (knowledge population)
static/           # Frontend (HTML, CSS, JS)
data/             # SQLite databases (knowledge, diagnostics, ecommerce)
config.py         # Models, profiles, Ollama API
server.py         # FastAPI backend
```

---

## Frameworks and libraries:
`langchain`, `langchain-ollama`, `langchain-community`, `duckduckgo-search`, `pydantic`, `rich`, `fastapi`, `uvicorn`, `psutil`, `pymupdf`, `Pillow`<br>
Optional: `python-docx`, `openpyxl`, `faster-whisper`, `datasets`
