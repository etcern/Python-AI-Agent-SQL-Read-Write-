"""Streamlit UI - chat interface with agent selector.

To add a new agent: create it in agents/ and register it in agents/__init__.py.
"""

import os
import random
import sqlite3
import streamlit as st
from config import DB_PATH, AGENT_MODELS, create_model_for_agent
from agents import AGENTS

WAITING_MESSAGES = [
    "Analyzing your question...",
    "Thinking it through...",
    "Working on it...",
    "Processing...",
]


@st.cache_resource
def get_model(agent_name: str):
    return create_model_for_agent(agent_name)


def get_table_info() -> list[tuple[str, int]]:
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    result = []
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM [{table}];")
        count = cursor.fetchone()[0]
        result.append((table, count))
    conn.close()
    return result


# --- Page config ---
st.set_page_config(page_title="QueryMaster", page_icon="Q")
st.header("QueryMaster")

# --- Sidebar ---
with st.sidebar:
    selected = st.radio(
        "Agent",
        options=list(AGENTS.keys()),
        format_func=lambda k: k.upper(),
        horizontal=True,
    )

    agent = AGENTS[selected]()
    model_name = AGENT_MODELS.get(selected)
    if model_name:
        st.caption(f"Model: {model_name.name}")

    tools = agent.get_all_tools()
    if tools:
        tool_names = ", ".join(f"`{t.name}`" for t in tools)
        st.caption(f"Tools: {tool_names}")

    st.divider()

    if selected == "sql" and os.path.exists(DB_PATH):
        for table_name, row_count in get_table_info():
            st.caption(f"{table_name} - {row_count:,} rows")
        st.divider()

    if st.button("Clear Chat"):
        if selected in st.session_state.get("agent_messages", {}):
            st.session_state.agent_messages[selected] = []
            st.session_state.agent_histories[selected] = agent.create_history()
        st.rerun()

# --- Per-agent session storage ---
if "agent_messages" not in st.session_state:
    st.session_state.agent_messages = {}

if "agent_histories" not in st.session_state:
    st.session_state.agent_histories = {}

if selected not in st.session_state.agent_messages:
    st.session_state.agent_messages[selected] = []
    st.session_state.agent_histories[selected] = agent.create_history()

messages = st.session_state.agent_messages[selected]
history = st.session_state.agent_histories[selected]

# --- Chat display ---
for msg in messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Chat input ---
if prompt := st.chat_input("Ask a question..."):
    messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner(random.choice(WAITING_MESSAGES)):
            base_model = get_model(selected)
            model_with_tools = agent.bind_tools(base_model)
            response = agent.ask(
                query=prompt,
                history=history,
                model=model_with_tools,
            )
        st.markdown(response)

    messages.append({"role": "assistant", "content": response})
