# Sources

Code references used in this project.

## FastAPI

| File | What | Source |
|------|------|--------|
| server.py | FastAPI app, endpoints, request/response models | https://fastapi.tiangolo.com/ |
| server.py | Static file serving (`StaticFiles`, `FileResponse`) | https://fastapi.tiangolo.com/tutorial/static-files/ |
| server.py | Path parameters, request body, HTTP exceptions | https://fastapi.tiangolo.com/tutorial/path-params/ |
| server.py | Pydantic models for request validation | https://fastapi.tiangolo.com/tutorial/body/ |
| server.py | Uvicorn ASGI server | https://www.uvicorn.org/ |

## Chat Persistence

| File | What | Source |
|------|------|--------|
| chat_store.py | SQLite3 for chat + message CRUD | https://docs.python.org/3/library/sqlite3.html |
| chat_store.py | `sqlite3.Row` for dict-like row access | https://docs.python.org/3/library/sqlite3.html#sqlite3.Row |
| chat_store.py | `PRAGMA foreign_keys` + `ON DELETE CASCADE` | https://www.sqlite.org/foreignkeys.html |

## Ollama

| File | What | Source |
|------|------|--------|
| config.py | `list_ollama_models()` — GET /api/tags | https://github.com/ollama/ollama/blob/main/docs/api.md#list-local-models |
| config.py | ChatOllama integration | https://python.langchain.com/docs/integrations/chat/ollama |

## LangChain

| File | What | Source |
|------|------|--------|
| agents/base.py | Tool calling loop (`model.invoke`, `tool_calls`) | https://python.langchain.com/docs/how_to/tool_calling |
| agents/base.py | Message types (SystemMessage, HumanMessage, etc.) | https://python.langchain.com/docs/concepts/messages |
| agents/base.py | `bind_tools()` for tool registration | https://python.langchain.com/docs/how_to/tool_calling |
| server.py | Rebuild LangChain history from stored messages | https://python.langchain.com/docs/concepts/messages |

## Frontend Libraries (CDN)

| File | What | Source |
|------|------|--------|
| static/index.html | marked.js — Markdown to HTML rendering | https://marked.js.org/ |
| static/index.html | DOMPurify — HTML sanitization to prevent XSS | https://github.com/cure53/DOMPurify |
| static/index.html | highlight.js — Syntax highlighting for code blocks | https://highlightjs.org/ |
| static/index.html | Google Material Symbols Rounded — icon font | https://fonts.google.com/icons |
| static/index.html | Google Fonts (Roboto, Inter, Source Sans 3, Nunito, JetBrains Mono) | https://fonts.google.com/ |

## CSS / Frontend

| File | What | Source |
|------|------|--------|
| static/style.css | CSS custom properties for theme switching | https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties |
| static/style.css | Flexbox layout (sidebar + main, composer bar) | https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_flexible_box_layout |
| static/style.css | Custom scrollbar styling | https://developer.mozilla.org/en-US/docs/Web/CSS/::-webkit-scrollbar |
| static/style.css | `color-mix()` for transparent accent tints | https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/color-mix |
| static/style.css | Responsive breakpoints with media queries | https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_media_queries |
| static/style.css | `text-overflow: ellipsis` for chat titles | https://developer.mozilla.org/en-US/docs/Web/CSS/text-overflow |
| static/style.css | `box-sizing: border-box` reset | https://developer.mozilla.org/en-US/docs/Web/CSS/box-sizing |

## JavaScript

| File | What | Source |
|------|------|--------|
| static/app.js | Fetch API for all backend communication | https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch |
| static/app.js | localStorage for persisting user settings | https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage |
| static/app.js | `getBoundingClientRect()` for dropdown positioning | https://developer.mozilla.org/en-US/docs/Web/API/Element/getBoundingClientRect |
| static/app.js | Textarea auto-grow via `scrollHeight` | https://developer.mozilla.org/en-US/docs/Web/API/HTMLElement/scrollHeight |

## Python stdlib

| File | What | Source |
|------|------|--------|
| config.py | `urllib.request` for Ollama API calls | https://docs.python.org/3/library/urllib.request.html |
| server.py | `uuid.uuid4()` for chat IDs | https://docs.python.org/3/library/uuid.html |
| chat_store.py | `datetime` for timestamps | https://docs.python.org/3/library/datetime.html |
