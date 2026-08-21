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
  4. The agent gets auto-discovered - no need to register it anywhere

---

## Features:
- **Web Search**: All agents can search the internet via DuckDuckGo. No API key needed.<br>
- **GitHub Integration**: Agents can search GitHub repos, browse file trees, and fetch source code directly. They learn from the best public repositories.<br>
- **Internet Toggle**: A button in the composer bar lets you manually enable/disable internet access (web search + GitHub). When OFF, agents work with local files and knowledge only.<br>
- **Confirmation Mode**: A toggle that makes agents ask before executing write/modify operations. Shows what will change and waits for approval.<br>
- **Thought Process**: A collapsible panel on each response showing every tool call, reasoning, arguments, results, and severity badges (green/yellow/red).<br>
- **Code Copy Buttons**: One-click copy on all code blocks in agent responses.<br>
- **Wissensdatenbank (Knowledge Base)**: Agents can save and retrieve learned information across sessions, so they get smarter over time. Pre-load with `python scripts/populate_knowledge.py --all`.<br>
- **HuggingFace Import**: Optionally import coding patterns from HuggingFace datasets with `python scripts/populate_knowledge.py --huggingface`.<br>
- **Smart Search Priority**: Agents first check the knowledge base, then local files, then the internet. Useful findings get saved automatically for next time.<br>
- **Multi-Agent Pipeline**: The Planner agent analyzes tasks, delegates to Coder/SQL/Reviewer agents, and assembles reviewed results through a 5-stage pipeline (analyze - plan - execute - review - report).<br>
- **Code Review Agent**: Standalone reviewer that checks code for correctness, security, performance, readability, error handling, and best practices.<br>
- **Agent Delegation**: Any agent can hand off tasks to another specialist. The Planner orchestrates complex multi-step work across agents.<br>
- **File Upload**: Upload files via the button or drag-and-drop them directly into the chat area. Agents can read and list uploaded files.<br>
- **Modular Tools**: Each agent gets read-only file access, knowledge base, and web search by default. Add more tools (database, file write) per agent as needed.<br>
- **Auto-Discovery**: Drop a new agent file in `agents/` and it just works. No manual registration.

---

## Agent Hierarchy and Model Recommendations:

| Agent | Role | Recommended Model | Stage |
|-------|------|-------------------|-------|
| Planner | Analyzes tasks, builds execution plans, delegates | 14b+ | Orchestrator |
| Coder | Writes, edits, and debugs code | 14b+ | Execute |
| Code Reviewer | Reviews code for bugs, security, quality | 14b+ | Review |
| SQL Assistant | Queries databases using natural language | 7b+ | Execute |
| Translator | Translates text between languages | 7b+ | Execute |

For complex tasks, use the **Planner** agent - it will automatically delegate to the right specialists and have the Reviewer check the output.

---

## Wissensdatenbank (Knowledge Base):

Pre-load the knowledge base so your agents write better code from the start:

```bash
python scripts/populate_knowledge.py --all           # Load all built-in packs (35 entries)
python scripts/populate_knowledge.py --pack python    # Load a specific pack
python scripts/populate_knowledge.py --huggingface    # Import from HuggingFace (needs: pip install datasets)
python scripts/populate_knowledge.py --list           # Show available packs
python scripts/populate_knowledge.py --stats          # Show knowledge base stats
```

Available packs: python (10), sql (7), javascript (5), security (4), design_patterns (4), testing (3), fastapi (2).