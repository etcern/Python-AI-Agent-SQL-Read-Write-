# Python-SQL-AI-Agent
This project contains a WireFrame for an/many AI agent/s using a mix of Python, HTML/CSS/JS and the Frameworks [langchain, langchain-ollama, langchain-community, duckduckgo-search, pydantic, rich, fastapi, uvicorn[standard]].

---

## Note:
This Project has been developed using the help of [ClaudeAI](https://claude.ai/), especially on the Website Interface. <br><br>This is just the base for an standard local AI prompting interface, that is working together with ollama API, in order to be able to Use local Chatbots inside a Web interface made out of python, open source and fully modular. The design of the website has been inspired by [ClaudeAI](https://claude.ai/) website. 

---

## What do I need?
1. Install [Ollama](https://ollama.com) from their official WebSite.<br>
2. Clone the repository<br>
3. Install the python libraries via the command  `pip install -r requirements.txt`(make sure you have [pip installed](https://pip.pypa.io/en/stable/installation/))<br>
4. Start `server.py`

---

## To add a new agent:
  1. Create a new agent file under `agents/agent_name.py`
  2. Copy/Paste the current Arhitecture form an already existing agent.
  3. Modify your `SYSTEM_PROMPT` to your liking
  4. The agent gets auto-discovered — no need to register it anywhere

---

## Features:
- **Web Search**: All agents can search the internet via DuckDuckGo. No API key needed.<br>
- **Wissensdatenbank (Knowledge Base)**: Agents can save and retrieve learned information across sessions, so they get smarter over time.<br>
- **File Upload**: Upload files via the button or drag-and-drop them directly into the chat area. Agents can read and list uploaded files.<br>
- **Modular Tools**: Each agent gets read-only file access, knowledge base, and web search by default. Add more tools (database, file write) per agent as needed.<br>
- **Auto-Discovery**: Drop a new agent file in `agents/` and it just works. No manual registration.