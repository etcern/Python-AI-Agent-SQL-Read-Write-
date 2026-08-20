# QueryMaster - Local AI SQL Agent
## Complete Presentation & Learning Guide

---

# PART 1: THE BIG PICTURE - What Is This?

## What We Built

QueryMaster is a **local AI agent** that lets you talk to a SQL database in plain English.
Instead of writing SQL queries by hand, you type something like:

> "Who is my best customer?"

...and the AI figures out which tables to look at, writes the SQL, runs it, and gives you
a clean answer like "Nicole Bond with 12 orders totaling $1,847.50".

## Why Does This Matter?

- **No cloud needed** - Everything runs on YOUR machine. Your data never leaves your computer.
- **No API keys** - No OpenAI bill, no usage limits, no subscriptions.
- **No SQL knowledge needed** - Business analysts can query databases without learning SQL.
- **Customizable** - You control the model, the database, the tools, and the behavior.

## The Technology Stack (What Makes It Work)

```
 YOU (browser)
  |
  v
 Streamlit        --> The web interface (chat UI)
  |
  v
 LangChain        --> The framework that connects AI to tools
  |
  v
 Ollama           --> Runs the AI model locally on your GPU
  |
  v
 qwen2.5-coder    --> The actual AI brain (14 billion parameters)
  |
  v
 SQLite           --> The database with your data
```

| Component          | What It Is                           | Why We Use It                        |
|--------------------|--------------------------------------|--------------------------------------|
| **Ollama**         | Local AI model server                | Runs LLMs on your GPU, no cloud     |
| **qwen2.5-coder**  | A 14B parameter coding LLM          | Good at understanding code & SQL     |
| **LangChain**      | AI application framework             | Connects AI to tools in a standard way |
| **SQLite**         | Lightweight file-based database      | No server needed, just a .db file    |
| **Streamlit**      | Python web app framework             | Fast way to build chat UIs           |
| **Rich**           | Terminal formatting library          | Pretty debug output in the console   |

---

# PART 2: HOW THE AI AGENT WORKS

## What Is an AI Agent?

An AI agent is different from a regular chatbot. A chatbot just generates text.
An **agent** can:

1. **Think** about what steps it needs to take
2. **Use tools** to interact with its environment
3. **React** to the results of those tools
4. **Decide** what to do next
5. **Loop** until it has a complete answer

This is called the **ReAct pattern** (Reason + Act).

## The Agent Loop - Step by Step

Here's exactly what happens when you ask "Who is my best customer?":

```
Step 1: USER asks "Who is my best customer?"
    |
    v
Step 2: AI THINKS "I need to find customer and order tables"
    |
    v
Step 3: AI CALLS tool: list_tables()
    |   Result: "customers, orders, order_items, products"
    v
Step 4: AI THINKS "I need to understand the orders table structure"
    |
    v
Step 5: AI CALLS tool: describe_table("orders")
    |   Result: "id, customer_id, order_date, status, total_amount"
    v
Step 6: AI THINKS "Now I can write a query to find the top customer"
    |
    v
Step 7: AI CALLS tool: execute_sql("SELECT c.first_name, c.last_name,
    |       COUNT(*) as order_count, SUM(o.total_amount) as total_spent
    |       FROM customers c JOIN orders o ON c.id = o.customer_id
    |       GROUP BY c.id ORDER BY total_spent DESC LIMIT 1")
    |   Result: "Nicole Bond, 12 orders, $1847.50"
    v
Step 8: AI RESPONDS "Your best customer is Nicole Bond with 12 orders
         totaling $1,847.50"
```

**Key insight**: The AI decided on its own to do steps 3-7. Nobody told it "first list
the tables, then describe them." It planned the approach itself.

## How This Looks in Code

The entire agent loop is in `agent.py` and it's surprisingly simple:

```python
def ask(query, history, model, max_iterations=15):
    # Add the user's question to chat history
    history.append(HumanMessage(content=query))

    iteration = 0
    while iteration < max_iterations:
        # Send the full conversation to the AI
        response = model.invoke(history)

        # If the AI didn't call any tools, it's done - return the answer
        if not tool_calls:
            return str(response.content)

        # Otherwise, execute each tool the AI requested
        for tool_call in tool_calls:
            tool_response = call_tool(tool_call)  # Run the actual function
            history.append(tool_response)          # Add result to history

        iteration += 1
```

The `max_iterations=15` is a safety net - if the AI gets stuck in a loop calling tools
forever, it stops after 15 rounds.

---

# PART 3: PROJECT FILES EXPLAINED

## File Structure

```
query_master/
  |-- config.py          # Model settings (which AI, how it behaves)
  |-- agent.py           # The agent brain (loop + system prompt)
  |-- tools.py           # Database tools the AI can use
  |-- logging_utils.py   # Pretty console output
  |-- app.py             # The web interface (Streamlit)
  |-- setup_db.py        # Creates the sample database
  |-- requirements.txt   # Python packages needed
  |-- data/
       |-- ecommerce.db  # The SQLite database (108 KB)
```

---

## FILE 1: config.py - Model Configuration

**Purpose**: Defines which AI model to use and how to connect to it.

```python
CONTEXT_WINDOW = 8192  # How much text the AI can "remember" at once

@dataclass
class ModelConfig:
    name: str          # Model name in Ollama (e.g., "qwen2.5-coder:14b")
    temperature: float # 0 = deterministic, 1 = creative/random
    provider: str      # "ollama" (could add "openai", "anthropic" etc.)

def create_model(config: ModelConfig) -> BaseChatModel:
    return ChatOllama(
        model=config.name,
        temperature=config.temperature,
        num_ctx=CONTEXT_WINDOW,
        base_url="http://127.0.0.1:11434",  # Ollama's local address
    )
```

### Things You Can Change

| Setting | Current Value | What Changing It Does |
|---------|--------------|----------------------|
| `CONTEXT_WINDOW` | `8192` | **Increase to 16384 or 32768** = AI remembers more of the conversation but uses more VRAM and responds slower. **Decrease to 4096** = faster but may forget earlier parts of conversation. |
| `temperature` | `0` | **Set to 0.3-0.7** = more varied/creative answers. **Keep at 0** = same question always gets same answer (best for SQL accuracy). |
| `name` | `"qwen2.5-coder:14b"` | Change to any model you have in Ollama. See "Swapping Models" section below. |
| `base_url` | `"http://127.0.0.1:11434"` | Only change if Ollama runs on a different port or machine. |

### Example: Adding a Second Model

```python
MODELS = {
    "qwen2.5-coder:14b": ModelConfig(
        name="qwen2.5-coder:14b",
        temperature=0,
        provider="ollama",
    ),
    # ADD THIS:
    "devstral-small-2": ModelConfig(
        name="devstral-small-2:latest",
        temperature=0,
        provider="ollama",
    ),
}

# Change which one is used by default:
DEFAULT_MODEL = "devstral-small-2"  # was "qwen2.5-coder:14b"
```

---

## FILE 2: tools.py - The AI's Hands

**Purpose**: These are the 4 functions the AI can call to interact with the database.
Without tools, the AI can only talk — with tools, it can DO things.

### Tool 1: list_tables

```python
@tool(parse_docstring=True)
def list_tables(reasoning: str) -> str:
    """List all tables available in the database."""
    with sqlite_cursor() as cursor:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        return ", ".join(t[0] for t in tables)
```

**What the AI sees**: "There's a tool called `list_tables` that returns all table names."
**What it returns**: `"customers, orders, order_items, products"`

### Tool 2: describe_table

```python
@tool(parse_docstring=True)
def describe_table(reasoning: str, table_name: str) -> str:
    """Describe the structure of a specific table."""
    with sqlite_cursor() as cursor:
        cursor.execute(f"PRAGMA table_info([{table_name}]);")
        # Returns column names and their types
```

**What it returns**:
```
id (INTEGER)
first_name (TEXT) NOT NULL
last_name (TEXT) NOT NULL
email (TEXT) NOT NULL
...
```

### Tool 3: sample_table

```python
@tool(parse_docstring=True)
def sample_table(reasoning: str, table_name: str, row_count: int = 5) -> str:
    """Get a sample of rows from a specific table."""
    with sqlite_cursor() as cursor:
        cursor.execute(f"SELECT * FROM [{table_name}] LIMIT ?;", (row_count,))
```

**Why this exists**: Sometimes the AI needs to see what the actual data looks like
before it can write a good query. Column names alone aren't enough.

### Tool 4: execute_sql

```python
@tool(parse_docstring=True)
def execute_sql(reasoning: str, query: str) -> str:
    """Execute a SQL query against the database and return the results."""
    with sqlite_cursor() as cursor:
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
```

**This is the most powerful tool** - it can run ANY SQL query. The AI writes the SQL
based on its understanding of the table structure.

### The "reasoning" Parameter - Poor Man's Chain of Thought

Every tool has a `reasoning` parameter. This forces the AI to explain WHY it's calling
that tool before it does. This is useful for:

- **Debugging**: You can see the AI's thought process in the terminal
- **Transparency**: You know WHY a query was run, not just WHAT was run
- **Better results**: Forcing the AI to reason improves its decisions

```
+--------------- describe_table(orders) - Reasoning ----------------+
| Understand the structure of the orders table including its        |
| relationship with the customer table so I can write a JOIN query  |
+-------------------------------------------------------------------+
```

### How to Add a New Tool

Want the AI to be able to insert data? Add a new tool:

```python
@tool(parse_docstring=True)
def insert_customer(reasoning: str, first_name: str, last_name: str, email: str) -> str:
    """Insert a new customer into the database.

    Args:
        reasoning: Why you are inserting this customer.
        first_name: The customer's first name.
        last_name: The customer's last name.
        email: The customer's email address.

    Returns:
        Confirmation message with the new customer ID.
    """
    log_panel(reasoning, title="insert_customer - Reasoning")
    with sqlite_cursor() as cursor:
        cursor.execute(
            "INSERT INTO customers (first_name, last_name, email, created_at) VALUES (?, ?, ?, datetime('now'))",
            (first_name, last_name, email),
        )
        return f"Customer {first_name} {last_name} inserted with ID {cursor.lastrowid}"
```

Then register it:

```python
def get_available_tools() -> list:
    return [list_tables, sample_table, describe_table, execute_sql, insert_customer]
    #                                                                ^^^^^^^^^^^^^^
```

Now you can say: "Add a new customer named John Doe with email john@example.com"

---

## FILE 3: agent.py - The Brain

**Purpose**: Contains the system prompt (the AI's personality and instructions) and the
main loop that orchestrates tool calls.

### The System Prompt

This is the most important piece of text in the whole project. It tells the AI:
- **Who it is**: "You are QueryMaster, an expert SQL database analyst"
- **What to do**: Step-by-step instructions for handling queries
- **How to respond**: Markdown format, tables for data, no raw SQL unless asked
- **Who the audience is**: Business analysts who don't know SQL

```python
SYSTEM_PROMPT = """You are QueryMaster, an expert SQL database analyst agent...

## Instructions
1. First understand which tables are relevant by listing available tables.
2. Examine table structure using describe_table.
3. Sample rows to understand the data format.
4. Write and execute SQL queries to answer the question.
5. If a query fails, analyze the error and try again.
...
"""
```

### What Happens If You Change the Prompt

| Change | Effect |
|--------|--------|
| Remove "Format your final response in Markdown" | Answers become plain text, no tables |
| Change "target audience is business analysts" to "target audience is SQL experts" | Answers include more technical detail and raw SQL |
| Add "Always show the SQL query you used" | Every answer includes the SQL code |
| Add "Respond in Romanian" | All answers come in Romanian |
| Add "If the user asks to delete or modify data, refuse" | Read-only safety guardrail |
| Increase `MAX_ITERATIONS` from 15 to 30 | AI can take more steps for complex queries |

### Example: Making the Agent Read-Only Safe

Add this to the system prompt:

```python
SYSTEM_PROMPT = f"""...
## Safety Rules
- NEVER execute INSERT, UPDATE, DELETE, DROP, ALTER, or CREATE statements.
- Only run SELECT queries. If the user asks to modify data, explain that
  you are a read-only analyst and cannot make changes.
..."""
```

### The Tool Call Fallback Parser

Some local models (including qwen2.5-coder) output tool calls as JSON text instead of
using the structured format that LangChain expects. Our agent handles this with a
fallback parser:

```python
# The AI outputs this as plain text:
'{"name": "list_tables", "arguments": {"reasoning": "..."}}'

# Our parser detects it, extracts the JSON, and converts it into
# a proper tool call that the system can execute.
```

This is a real-world lesson: **local models don't always behave like cloud APIs**.
You need to handle edge cases.

---

## FILE 4: app.py - The User Interface

**Purpose**: The Streamlit web app that creates the chat interface.

### Key Parts

**Model initialization** (runs once, cached):

```python
@st.cache_resource  # Only runs once, then reuses the result
def get_model():
    config = MODELS[DEFAULT_MODEL]
    llm = create_model(config)
    llm_with_tools = llm.bind_tools(get_available_tools())  # Give AI access to tools
    return llm_with_tools
```

**Sidebar** (shows database info):

```python
with st.sidebar:
    st.markdown(f"**File:** `{os.path.basename(DB_PATH)}`")
    st.markdown(f"**Size:** {size_mb:.2f} MB")
    for table_name, row_count in get_table_info():
        st.markdown(f"- `{table_name}` - {row_count:,} rows")
```

**Chat loop** (handles user input and AI responses):

```python
if prompt := st.chat_input("Ask a question about your data..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Get AI response
    with st.spinner("Analyzing your question..."):
        response = ask(query=prompt, history=st.session_state.history, model=model)

    # Show AI response
    st.markdown(response)
    st.session_state.messages.append({"role": "assistant", "content": response})
```

---

## FILE 5: setup_db.py - Database Generator

**Purpose**: Creates the SQLite database with realistic sample data.

### Database Schema (4 tables):

```
products (97 rows)          customers (100 rows)
+-------------+             +-------------+
| id          |             | id          |
| name        |             | first_name  |
| description |             | last_name   |
| price       |             | email       |
| category    |             | phone       |
| in_stock    |             | address     |
+-------------+             | city        |
                            | country     |
orders (500 rows)           | created_at  |
+-------------+             +-------------+
| id          |
| customer_id |----> customers.id
| order_date  |
| status      |    order_items (~1400 rows)
| total_amount|    +-------------+
+-------------+    | id          |
                   | order_id    |----> orders.id
                   | product_id  |----> products.id
                   | quantity    |
                   | unit_price  |
                   +-------------+
```

### The Relationships

- One **customer** can have many **orders** (one-to-many)
- One **order** can have many **order_items** (one-to-many)
- One **product** can appear in many **order_items** (one-to-many)
- This means customers and products have a **many-to-many** relationship through orders

### How to Change the Database

**Add more data** - edit `setup_db.py` and change the counts:

```python
num_customers = seed_customers(cursor, count=100)   # Change 100 to 1000
num_orders = seed_orders(cursor, num_customers, num_orders=500)  # Change 500 to 5000
```

Then regenerate:
```
E:\Python3\python.exe setup_db.py
```

**Add a new table** - add to `create_tables()`:

```python
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    customer_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
    review_text TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(id),
    FOREIGN KEY (customer_id) REFERENCES customers(id)
);
```

**Use your own database** - change `DB_PATH` in `config.py`:

```python
DB_PATH = r"C:\path\to\your\real\database.db"
```

The AI will automatically discover the tables and structure. No other code changes needed.

---

# PART 4: WHAT CAN YOU CHANGE? (WITH EXAMPLES)

## 1. Swap the AI Model

Any Ollama model that supports tool calling works. Models currently installed on this machine:

| Model | Size | Good For |
|-------|------|----------|
| `qwen2.5-coder:14b` (current) | 9 GB | SQL/code tasks, best tool calling |
| `devstral-small-2:latest` | 15 GB | General coding, Mistral-based |

To try a different model:

```python
# In config.py, change:
DEFAULT_MODEL = "devstral-small-2"

# And add it to MODELS:
MODELS = {
    "qwen2.5-coder:14b": ModelConfig(name="qwen2.5-coder:14b", temperature=0, provider="ollama"),
    "devstral-small-2": ModelConfig(name="devstral-small-2:latest", temperature=0, provider="ollama"),
}
```

To pull a new model from Ollama's library:
```
ollama pull llama3.1:8b
ollama pull qwen2.5:7b
ollama pull mistral:7b
```

## 2. Connect to a Different Database

### SQLite (any .db file)

Just change the path in `config.py`:

```python
DB_PATH = r"X:\path\to\your\database.db"
```

### PostgreSQL, MySQL, etc.

Replace the `sqlite_cursor()` in `tools.py`:

```python
import psycopg2  # pip install psycopg2-binary

@contextmanager
def postgres_cursor():
    conn = psycopg2.connect(
        host="localhost",
        database="mydb",
        user="myuser",
        password="mypassword"
    )
    cursor = conn.cursor()
    try:
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
```

You'd also update the `list_tables` and `describe_table` SQL queries since PostgreSQL
uses different system tables than SQLite.

## 3. Add More Tools

The agent's capabilities are limited only by what tools you give it. Examples:

### A "chart" tool that creates visualizations

```python
@tool(parse_docstring=True)
def create_chart(reasoning: str, query: str, chart_type: str = "bar") -> str:
    """Run a SQL query and create a chart from the results.

    Args:
        reasoning: Why you are creating this chart.
        query: SQL query that returns data to chart.
        chart_type: Type of chart - bar, line, or pie.
    """
    # Execute query, create chart with matplotlib, save as image
    ...
```

### A "web search" tool

```python
@tool(parse_docstring=True)
def search_web(reasoning: str, query: str) -> str:
    """Search the web for additional context."""
    # Call a search API
    ...
```

### A "send email" tool

```python
@tool(parse_docstring=True)
def send_report(reasoning: str, to_email: str, subject: str, body: str) -> str:
    """Send the analysis results as an email report."""
    # Use smtplib to send email
    ...
```

## 4. Change the System Prompt for Different Use Cases

The system prompt changes the AI's entire personality and approach:

**Financial analyst mode**:
```python
SYSTEM_PROMPT = """You are a financial analyst AI. When users ask about data,
focus on financial metrics: revenue, profit margins, growth rates, YoY comparisons.
Always include monetary values with proper formatting ($1,234.56).
Flag any unusual patterns or anomalies in the data."""
```

**Customer support mode**:
```python
SYSTEM_PROMPT = """You are a customer support assistant. Help agents look up
customer information, order history, and resolve issues. Be empathetic and
solution-oriented. When showing customer data, always redact email addresses
and phone numbers for privacy."""
```

## 5. Make It Remember Conversations (Persistent Memory)

Currently, chat history is lost when you restart. To persist it:

```python
# In app.py, save history to a JSON file:
import json

HISTORY_FILE = "chat_history.json"

def save_history(messages):
    with open(HISTORY_FILE, "w") as f:
        json.dump(messages, f)

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE) as f:
            return json.load(f)
    return []
```

---

# PART 5: HOW IT RUNS - THE FULL FLOW

## Starting the System

```
1. Ollama must be running (it starts automatically on system boot)
   - It loads the AI model into your GPU's VRAM (16 GB on your RX 9060 XT)
   - The model stays in memory until Ollama is stopped

2. You start Streamlit:
   > E:\Python3\python.exe -m streamlit run app.py

3. Streamlit:
   - Starts a local web server on http://localhost:8501
   - Loads the model config and binds the 4 tools
   - Shows the chat UI in your browser
```

## What Happens Per Question

```
Browser                    Streamlit                 Agent                  Ollama              Database
   |                          |                        |                      |                    |
   |-- "Who spent the most?"->|                        |                      |                    |
   |                          |-- ask(query) --------->|                      |                    |
   |                          |                        |-- invoke(history) -->|                    |
   |                          |                        |                      |-- GPU inference    |
   |                          |                        |<- tool_call ---------|                    |
   |                          |                        |                      |                    |
   |                          |                        |-- list_tables() -----|-------- SQL ------>|
   |                          |                        |                      |                    |
   |                          |                        |<- "customers, ..." --|<--- result --------|
   |                          |                        |                      |                    |
   |                          |                        |-- invoke(history) -->|                    |
   |                          |                        |                      |-- GPU inference    |
   |                          |                        |<- tool_call ---------|                    |
   |                          |                        |                      |                    |
   |                          |                        |-- execute_sql() -----|-------- SQL ------>|
   |                          |                        |<- results -----------|<--- result --------|
   |                          |                        |                      |                    |
   |                          |                        |-- invoke(history) -->|                    |
   |                          |                        |                      |-- GPU inference    |
   |                          |                        |<- final text --------|                    |
   |                          |                        |                      |                    |
   |                          |<- "Nicole Bond..." ----|                      |                    |
   |<- render markdown -------|                        |                      |                    |
```

## Resource Usage

| Resource | Usage |
|----------|-------|
| **GPU VRAM** | ~9 GB for qwen2.5-coder:14b (out of 16 GB available) |
| **System RAM** | ~500 MB for Python + Streamlit + LangChain |
| **Disk** | 108 KB for the database, 9 GB for the model |
| **CPU** | Minimal (GPU does the heavy lifting) |
| **Network** | Zero - everything is local |

---

# PART 6: CAPABILITIES AND LIMITATIONS

## What It Can Do Well

- **Simple lookups**: "How many products are in stock?"
- **Aggregations**: "What's the average order value?"
- **Joins**: "Which customer spent the most money?" (joins customers + orders)
- **Filtering**: "Show cancelled orders from 2024"
- **Grouping**: "Revenue breakdown by product category"
- **Time-based**: "Orders from the last 30 days" (knows today's date)
- **Multi-step**: "Who bought the most expensive product, and what else did they buy?"
- **Follow-up questions**: "Show me their contact details" (remembers previous context)

## Example Questions to Try

```
Basic:
  "List all product categories"
  "How many customers are from the US?"
  "What's the most expensive product?"

Intermediate:
  "Top 5 customers by total spending"
  "Which product category generates the most revenue?"
  "Show me the order status distribution"

Advanced:
  "Which customers placed orders in both January and February 2024?"
  "What's the average number of items per order?"
  "Find customers who have never placed an order"
  "Compare revenue between the first and second half of 2024"

Follow-ups (test memory):
  First: "Who is the top customer?"
  Then:  "Show me all their orders"
  Then:  "What products did they buy the most?"
```

## Limitations

| Limitation | Why | Workaround |
|------------|-----|------------|
| **Slow responses** (5-30 sec) | Local GPU inference is slower than cloud APIs | Use a smaller model (7B) or reduce context window |
| **Context window** (8192 tokens) | Limited conversation memory | Increase `CONTEXT_WINDOW` (uses more VRAM) |
| **No real-time data** | Database is a static snapshot | Connect to a live database instead |
| **Can hallucinate SQL** | AI might guess wrong column names | The describe_table tool helps, but it's not perfect |
| **Single user** | Streamlit runs one session | Use Streamlit's multi-user features for production |
| **No authentication** | Anyone with the URL can query | Add Streamlit authentication for production |

---

# PART 7: WHERE TO GO FROM HERE

## Learning Path

### Concepts to Study

1. **LLM Basics** - What are tokens, temperature, context windows, and parameters?
2. **Prompt Engineering** - How do system prompts shape AI behavior?
3. **Tool Calling / Function Calling** - How do LLMs know which tools to use?
4. **LangChain** - Framework for connecting LLMs to tools and data sources
5. **AI Agents vs Workflows** - When to let the AI decide vs hard-coding steps
6. **RAG (Retrieval Augmented Generation)** - Feed documents to AI for context
7. **Vector Databases** - Store and search text by meaning, not keywords

### Search Terms for Deeper Learning

- "LangChain tool calling tutorial"
- "Ollama tool use local LLM"
- "AI agent ReAct pattern explained"
- "LangChain SQL agent"
- "prompt engineering for SQL generation"
- "local LLM function calling"
- "Streamlit chatbot tutorial"

## Project Extension Ideas

### Easy (1-2 hours each)

- **Add a model selector** in the Streamlit sidebar to switch models at runtime
- **Export results** to CSV when the AI returns tabular data
- **Add query history** log to a file so you can review past questions
- **Dark mode** toggle for the Streamlit UI

### Medium (half day each)

- **Chart generation** - have the AI create matplotlib charts from query results
- **Multiple databases** - let the user switch between different .db files
- **Scheduled reports** - run predefined queries on a timer
- **Query explanation mode** - always show the SQL alongside the answer

### Advanced (full day+)

- **RAG integration** - combine SQL data with document search (PDF reports, etc.)
- **Multi-agent system** - one agent for SQL, one for charts, one for reports
- **Voice interface** - use Whisper for speech-to-text, ask questions by talking
- **PostgreSQL / MySQL** - connect to production databases
- **Fine-tuning** - train the model on your specific database schema for better SQL
- **Guardrails** - add input validation, output filtering, and SQL safety checks
- **Authentication** - add user login and role-based access control

---

# PART 8: KEY CONCEPTS GLOSSARY

| Term | Simple Explanation |
|------|-------------------|
| **LLM** | Large Language Model - an AI that understands and generates text (like GPT, Claude, Qwen) |
| **Parameters** | The "knowledge" stored in the model. 14B = 14 billion numbers that encode what the AI learned |
| **Tokens** | How AI reads text. Roughly 1 token = 3/4 of a word. "Hello world" = 2 tokens |
| **Context Window** | How much text the AI can see at once. 8192 tokens ~ 6000 words |
| **Temperature** | Randomness control. 0 = always same answer, 1 = creative but unpredictable |
| **Inference** | When the AI generates a response. This is what uses your GPU |
| **VRAM** | Video RAM on your GPU. The model must fit in VRAM to run on GPU |
| **Quantization** | Compressing a model to use less memory (e.g., 28 GB model -> 9 GB at Q4) |
| **Tool Calling** | The AI's ability to request that external functions be executed |
| **System Prompt** | Hidden instructions that define the AI's behavior and personality |
| **Chat History** | The full conversation so far, sent to the AI each turn for context |
| **Embedding** | Converting text to numbers so AI can understand meaning and similarity |
| **RAG** | Retrieval Augmented Generation - feeding relevant documents to AI before it answers |
| **Agent** | An AI that can plan steps, use tools, and work iteratively toward a goal |
| **Workflow** | A fixed sequence of steps (unlike an agent, which decides its own steps) |
| **LangChain** | A Python framework that makes it easy to connect LLMs to tools, databases, and APIs |
| **Ollama** | A program that runs AI models locally on your computer |
| **Streamlit** | A Python library for building web apps with minimal code |
| **SQLite** | A database stored as a single file, no server needed |

---

# PART 9: TROUBLESHOOTING

| Problem | Cause | Fix |
|---------|-------|-----|
| `ConnectError: [WinError 10049]` | Ollama uses IPv6 but code expects IPv4 | Set `base_url="http://127.0.0.1:11434"` in config.py (already done) |
| `ModuleNotFoundError` | Wrong Python installation | Use `E:\Python3\python.exe` not just `python` |
| `streamlit run` says "TARGET not found" | Wrong directory | `cd "X:\AI TRAINING\Claude Code template\query_master"` first (with quotes!) |
| AI outputs JSON instead of calling tools | Model doesn't produce structured tool calls | The fallback parser in agent.py handles this (already done) |
| Slow responses | Large model + small GPU | Reduce `CONTEXT_WINDOW` or use a smaller 7B model |
| AI gets stuck in a loop | Complex query, model confused | `MAX_ITERATIONS` stops it after 15 rounds |
| `Session state does not function` | Ran with `python app.py` instead of `streamlit run` | Always use `E:\Python3\python.exe -m streamlit run app.py` |
| Chat history lost on restart | History is in-memory only | See "Persistent Memory" section in Part 4 |

---

# PART 10: QUICK REFERENCE - RUNNING THE PROJECT

## First Time Setup

```powershell
# 1. Navigate to the project
cd "X:\AI TRAINING\Claude Code template\query_master"

# 2. Install dependencies (already done)
E:\Python3\python.exe -m pip install -r requirements.txt

# 3. Generate the database (already done)
E:\Python3\python.exe setup_db.py

# 4. Verify Ollama is running and model is available
ollama list
```

## Running the App

```powershell
# Navigate to project (paths with spaces need quotes!)
cd "X:\AI TRAINING\Claude Code template\query_master"

# Start the app
E:\Python3\python.exe -m streamlit run app.py

# Opens automatically at http://localhost:8501
```

## Regenerating the Database

```powershell
E:\Python3\python.exe setup_db.py
# Then restart the Streamlit app
```

## Stopping the App

Press `Ctrl+C` in the terminal where Streamlit is running.


Question, can I train this AI based on own data of how it should behave or what possibilities do I have? Can I scale?

● Great question. There are several levels of "teaching the AI", from easiest to hardest. You don't need to jump
  straight to training — the easier options cover most use cases.

  Level 1: Prompt Engineering (What You Already Have)

  The system prompt in agent.py is already a form of "training." You tell the AI its role, rules, and behavior. This is
  free, instant, and surprisingly powerful.

  # You can make it behave completely differently just by changing text:
  SYSTEM_PROMPT = """You are a Romanian-speaking financial analyst.
  Always respond in Romanian. Focus on revenue metrics.
  Never show raw SQL. Format all currency as RON."""

  Limitation: The AI doesn't actually learn — it follows instructions each time. If you restart, nothing is retained
  beyond what's in the prompt.

  Level 2: Few-Shot Examples (Easy)

  Add examples of correct behavior directly in the prompt:

  SYSTEM_PROMPT = """...
  ## Examples of good responses:

  User: "How many orders last month?"
  Good approach: First list_tables, then describe_table(orders),
  then execute_sql with a date filter using strftime.

  User: "Revenue by category"
  Good approach: JOIN products with order_items, GROUP BY category,
  SUM(quantity * unit_price).
  ..."""

  This steers the AI toward patterns you want without any actual training.

  Level 3: RAG — Feed It Your Own Documents (Medium)

  RAG (Retrieval Augmented Generation) lets the AI search through your documents before answering. Instead of training
  the model, you give it a searchable knowledge base.

  Your documents (PDFs, manuals, wiki pages, etc.)
          |
          v
      Chunked into pieces and stored as embeddings
          |
          v
      When user asks a question, relevant chunks
      are retrieved and injected into the prompt
          |
          v
      AI answers using your documents as context

  This would let you do things like:
  - "What does our company policy say about refund thresholds?" (searches your policy docs)
  - "Summarize the sales report from Q2" (searches your reports)
  - Combine SQL results WITH document context

  You'd add a vector database like ChromaDB (runs locally, free) and an embedding model via Ollama.

  Level 4: Ollama Modelfile Customization (Easy, but Limited)

  Ollama lets you create custom model variants with baked-in system prompts and parameters:

  # Save as Modelfile
  FROM qwen2.5-coder:14b
  SYSTEM "You are QueryMaster, a SQL expert for our e-commerce database..."
  PARAMETER temperature 0
  PARAMETER num_ctx 8192

  ollama create querymaster -f Modelfile

  Now querymaster is its own model in Ollama with your personality baked in. But this is still just prompt engineering —
   the model weights don't change.

  Level 5: Fine-Tuning (Actual Training)

  This is where you actually modify the model's weights using your own data. The most practical approach for local
  hardware:

  LoRA / QLoRA fine-tuning — trains a small "adapter" layer on top of the base model instead of retraining all 14
  billion parameters.

  ┌─────────────┬───────────────────────────────────────────────────────────────────────────────────────────────────┐
  │  What You   │                                              Details                                              │
  │    Need     │                                                                                                   │
  ├─────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Training    │ 100-10,000 examples in Q&A or instruction format                                                  │
  │ data        │                                                                                                   │
  ├─────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Tool        │ Unsloth (https://github.com/unslothai/unsloth) (fastest, free) or Axolotl                         │
  │             │ (https://github.com/OpenAccess-AI-Collective/axolotl)                                             │
  ├─────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Hardware    │ Your RX 9060 XT 16GB VRAM can fine-tune 7B models. 14B would be tight.                            │
  ├─────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Time        │ Hours to days depending on dataset size                                                           │
  ├─────────────┼───────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ Format      │ Export to GGUF, then import into Ollama                                                           │
  └─────────────┴───────────────────────────────────────────────────────────────────────────────────────────────────┘

  Training data looks like this (JSONL format):

  {"instruction": "How many orders were cancelled?", "output": "I'll query the orders table filtering by
  status='cancelled'. SELECT COUNT(*) FROM orders WHERE status='cancelled';"}
  {"instruction": "Top customer by spending", "output": "I'll join customers with orders and sum the totals. SELECT
  c.first_name, c.last_name, SUM(o.total_amount) ..."}

  Is it worth it? For most use cases, prompt engineering + RAG gets you 90% there. Fine-tuning is worth it when:
  - You need the AI to follow a very specific output format every time
  - You have domain-specific jargon it keeps getting wrong
  - You want to distill a large model's behavior into a smaller/faster model
  - Response speed matters and you want a smaller model that performs like a big one

  Scaling — What Are Your Options?

  ┌────────────────┬─────────────────────────────┬─────────────────────────────────────────────────────────────────┐
  │  Scale Level   │        What It Means        │                               How                               │
  ├────────────────┼─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ More data      │ Bigger databases, more      │ Just point DB_PATH at a bigger database. No code changes. Works │
  │                │ tables                      │  with millions of rows.                                         │
  ├────────────────┼─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ More users     │ Multiple people using it    │ Put Streamlit behind a reverse proxy (nginx). Ollama handles    │
  │                │                             │ concurrent requests.                                            │
  ├────────────────┼─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ More tools     │ AI can do more things       │ Add tools (charts, email, file export, web search). Each is     │
  │                │                             │ just a Python function.                                         │
  ├────────────────┼─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ More models    │ Different models for        │ Add a model selector in the UI. Smaller model for simple        │
  │                │ different tasks             │ queries, bigger for complex ones.                               │
  ├────────────────┼─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ More databases │ Switch between databases    │ Add a database selector dropdown. Each DB gets its own path.    │
  ├────────────────┼─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ Remote Ollama  │ GPU on another machine      │ Change base_url to point at a remote server. Ollama supports    │
  │                │                             │ network access.                                                 │
  ├────────────────┼─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ Multiple       │ Agents that collaborate     │ One agent for SQL, one for charts, one for reports. They pass   │
  │ agents         │                             │ results to each other.                                          │
  ├────────────────┼─────────────────────────────┼─────────────────────────────────────────────────────────────────┤
  │ Production     │ Real users, real data       │ Replace Streamlit with FastAPI, add auth, logging, rate         │
  │ deploy         │                             │ limiting, and error handling.                                   │
  └────────────────┴─────────────────────────────┴─────────────────────────────────────────────────────────────────┘

  My Recommendation for Your Stage

  NOW:        Prompt engineering (tweak the system prompt)
                  |
  NEXT:       RAG with ChromaDB (search your own docs)
                  |
  LATER:      Fine-tune a 7B model with Unsloth on your own Q&A pairs
                  |
  MUCH LATER: Multi-agent systems, production deployment

  The biggest bang for your buck right now is RAG — it lets the AI work with your actual business documents without any
  training at all. Want me to add RAG support to this project as a next step?