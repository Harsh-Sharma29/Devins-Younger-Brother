<div align="center">

# 🤖 Devin's Younger Brother

### Autonomous Software Engineering Agent

**Plan → Code → Validate → Execute → Self-Heal**

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.50-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.6-1C3C3C?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Sandbox-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*An agentic software engineering system that plans, writes, validates, executes, and autonomously repairs Python code inside an isolated Docker sandbox — with a decoupled FastAPI backend and Streamlit Pro IDE frontend.*

---

</div>

## ⚡ Why This Project Exists

Static LLM prompts fail in production because they lack **state**, **guardrails**, and **closed-loop verification**. This system treats software engineering as a **state machine**:

1. **Classify** user intent before expensive execution
2. **Remember** recent conversation context without unbounded token growth
3. **Validate** generated code before it ever touches a runtime
4. **Execute** in an ephemeral, isolated Docker container
5. **Self-heal** by feeding tracebacks back to a Debugger agent until verification passes

The result is a pipeline that behaves more like an engineering workflow than a chat completion.

---

## 🏗️ System Architecture

The system is **fully decoupled** into a FastAPI backend (`:8000`) and Streamlit frontend (`:8501`), communicating via **HTTP** and **Server-Sent Events (SSE)** for real-time streaming.

### High-Level Communication Flow

```mermaid
sequenceDiagram
    participant UI as Streamlit Frontend<br/>(:8501)
    participant API as FastAPI Backend<br/>(:8000)
    participant PG as PostgreSQL<br/>(Checkpointer)
    participant LG as LangGraph<br/>(State Machine)
    participant DK as Docker Sandbox<br/>(Ephemeral)

    UI->>API: POST /api/v1/execute {prompt, thread_id}
    API->>PG: Restore checkpoint state
    API->>LG: stream(input_state, config)

    loop For each graph node
        LG->>API: Node update (code, logs, errors)
        API-->>UI: SSE event: node_update
        Note over UI: Live pipeline graph + terminal update
    end

    opt Coding intent detected
        LG->>DK: Execute in python:3.11-slim
        DK-->>LG: stdout/stderr (10s timeout)
    end

    LG->>PG: Save checkpoint
    API-->>UI: SSE event: complete {final_state}
    UI->>API: GET /api/v1/history/{thread_id}
    API->>PG: Retrieve conversation history
    API-->>UI: JSON conversation_history
```

### LangGraph Pipeline Architecture

```
                              ┌─────────────────────────────┐
                              │   Streamlit Pro IDE (UI)     │
                              │   3-Pane Layout · SSE Client │
                              │   Chat History · Live Graph  │
                              └──────────────┬──────────────┘
                                             │ HTTP / SSE
                              ┌──────────────▼──────────────┐
                              │   FastAPI Backend (:8000)    │
                              │   SSE Streaming · Telemetry  │
                              └──────────────┬──────────────┘
                                             │
┌────────────────────────────────────────────────────────────────────────────┐
│                     LangGraph State Machine (graph.py)                     │
│                                                                            │
│  START ──▸ Router ──┬──▸ Planner ──▸ Coder ──▸ Validator ──┬──▸ Terminal  │
│                     │         ▲              │               │      │      │
│                     │         └──────────────┘  (reject)     │      │      │
│                     │                                        │      ▼      │
│                     │                                        │  Debugger   │
│                     │                                        │      │      │
│                     │                                        └──────┘      │
│                     ├──▸ Research Agent ──▸ END                            │
│                     └──▸ Knowledge Agent ──▸ END                           │
└────────────────────────────────────────────────────────────────────────────┘
                                             │
                          ┌──────────────────▼──────────────────┐
                          │     Docker Sandbox (ephemeral)       │
                          │     python:3.11-slim · RO volume     │
                          │     10s timeout · auto-remove        │
                          └─────────────────────────────────────┘
```

---

## ✨ Core Features

### 🧠 Intelligent Multi-Agent Pipeline

| Agent | Responsibility |
|-------|---------------|
| **Router** | Intent classification — `coding` / `research` / `generic` — before any expensive work |
| **Planner** | Mission brief, artifact targeting, and strategy selection |
| **Coder** | LLM code synthesis with markdown sanitization and multi-file workspace output |
| **Validator** | Pre-sandbox static analysis (dangerous ops, secrets, error handling) |
| **Terminal** | Docker sandbox execution with 10-second timeout |
| **Debugger** | Traceback-driven self-healing repair loop (stdlib-only rewrites) |
| **Research / Knowledge** | LLM-only answers for non-execution queries |

### 🔄 Multi-Model LLM Failover

Two-tier strategy managed by `src/core/llm_fallback.py`:

| Tier | Model | Trigger |
|------|-------|---------|
| **Primary** | Google Gemini 2.5 Flash | Default |
| **Fallback** | Meta Llama-3-8B-Instruct (HuggingFace) | `429` / `RESOURCE_EXHAUSTED` / `503` |

API error JSON is intercepted before it can pollute the code buffer or sandbox.

### 🔒 Cyclic Loop Safeguards

| Loop | Cap | Exit Condition |
|------|-----|---------------|
| Coder ↔ Validator | 3 attempts | Pass validation, or force Terminal |
| Terminal ↔ Debugger | 5 attempts | `is_verified=True`, empty errors, or cap reached |
| LangGraph global | `recursion_limit=50` | Hard ceiling on total node invocations |

### 💾 Persistent Multi-Turn Memory

- **PostgreSQL checkpointing** via `langgraph-checkpoint-postgres` — state survives page reloads
- **Sliding-window conversation history** — last 5 exchanges (10 messages) injected into Planner/Coder prompts
- **Thread-scoped sessions** — each `thread_id` maintains independent state

### 🖥️ Pro IDE Frontend

- **3-Pane layout** — Telemetry & Files (20%) | Code Editor (50%) | Live Terminal (30%)
- **`streamlit-ace` editor** — Python syntax highlighting, Monokai theme, line numbers
- **Multi-file workspace** — file tabs, selector dropdown, and visual explorer
- **Animated pipeline graph** — real-time glowing node transitions via SSE
- **Chat history panel** — conversation persistence from Postgres checkpoints
- **Live terminal** — true black background, Consolas font, green text streaming Docker stdout/stderr

---

## 📋 Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | 3.10+ | Runtime |
| **Docker Desktop** | Latest | Sandboxed code execution |
| **PostgreSQL** | 16+ (via Docker Compose) | LangGraph state persistence |
| **Gemini API Key** | — | Primary LLM |
| **HuggingFace Token** | — | Failover LLM (recommended) |

---

## 🚀 Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Harsh-Sharma29/Devin-s.git
cd Devin-s

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
GEMINI_API_KEY=your_gemini_api_key_here
HUGGINGFACEHUB_API_TOKEN=your_hf_token_here
DYB_API_URL=http://localhost:8000
```

### 3. Start Docker Desktop

Ensure Docker is running. The Terminal agent will fail gracefully with a descriptive error if Docker is unavailable.

### 4. Run (choose one)

#### Option A: Docker Compose (recommended — full stack)

```bash
docker compose up --build
```

This starts **Postgres** (`:5432`), **FastAPI backend** (`:8000`), and **Streamlit UI** (`:8501`) together.

#### Option B: Local Development (manual services)

```bash
# Terminal 1 — Start Postgres (if not using compose)
docker run -d --name dyb-postgres \
  -e POSTGRES_USER=devin -e POSTGRES_PASSWORD=devin -e POSTGRES_DB=devin_brother \
  -p 5432:5432 postgres:16-alpine

# Terminal 2 — FastAPI Backend
uvicorn src.api.server:app --host 0.0.0.0 --port 8000

# Terminal 3 — Streamlit Frontend
streamlit run app.py
```

#### Option C: CLI (no UI)

```bash
python main.py
```

### 5. Open the IDE

Navigate to **http://localhost:8501**, enter a prompt, and click **🚀 Execute Pipeline**.

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | System health: Postgres status, API key status, telemetry |
| `POST` | `/api/v1/session/new` | Generate a new backend-authoritative `thread_id` |
| `GET` | `/api/v1/history/{thread_id}` | Retrieve conversation history for a session |
| `POST` | `/api/v1/execute` | Execute the LangGraph pipeline (SSE streaming response) |

### Execute Request Body

```json
{
  "prompt": "Write a Python script that fetches JSON from an API",
  "thread_id": "550e8400-e29b-41d4-a716-446655440000",
  "recursion_limit": 50
}
```

### SSE Event Types

| Event | Payload | Description |
|-------|---------|-------------|
| `node_update` | `{node_name, transition, new_logs, code_buffer, workspace_files, telemetry}` | Incremental state from each graph node |
| `complete` | `{workspace_files, terminal_output, is_verified, conversation_history, telemetry}` | Final accumulated state |
| `error` | `{error, phase}` | Exception details |

---

## 📁 Project Structure

```
Devin/
├── app.py                          # Streamlit Pro IDE frontend (SSE client)
├── main.py                         # CLI LangGraph entry point
├── Dockerfile                      # Multi-purpose container image (Python 3.10)
├── docker-compose.yml              # Full stack: Postgres + API + UI
├── requirements.txt                # Pinned dependencies
├── .env.example                    # Environment template
├── README.md
└── src/
    ├── api/
    │   └── server.py               # FastAPI backend — SSE streaming, endpoints
    ├── core/
    │   ├── checkpointer.py         # Postgres ↔ MemorySaver connection pool
    │   ├── config.py               # Central config (DATABASE_URL, limits)
    │   ├── graph.py                # LangGraph state machine & conditional routing
    │   ├── llm_fallback.py         # Gemini + HuggingFace failover + sanitization
    │   ├── memory.py               # Sliding-window conversation history
    │   └── telemetry.py            # CPU/RAM metrics, token estimates, transitions
    ├── agents/
    │   ├── router.py               # Intent classification (no LLM call)
    │   ├── planner.py              # Mission planning
    │   ├── coder.py                # Code generation + multi-file parsing
    │   ├── validator.py            # Pre-sandbox security static analysis
    │   ├── terminal.py             # Docker sandbox execution
    │   ├── debugger.py             # Self-healing traceback repair
    │   ├── research.py             # Technical research (no sandbox)
    │   └── knowledge.py            # Generic Q&A (no sandbox)
    ├── state/                      # Pydantic state schema (DevinBrotherState)
    ├── sandbox/                    # Docker execution utilities
    └── tools/
        └── file_ops.py             # Workspace I/O + Docker runner
```

---

## ⚙️ Configuration Reference

| Variable | Default | Required | Description |
|----------|---------|----------|-------------|
| `GEMINI_API_KEY` | — | ✅ | Google Gemini API key (primary LLM) |
| `GOOGLE_API_KEY` | — | ❌ | Alternate Gemini key name |
| `HUGGINGFACEHUB_API_TOKEN` | — | ⚠️ Recommended | HuggingFace Hub token for failover LLM |
| `DYB_API_URL` | `http://localhost:8000` | ✅ | FastAPI backend URL for the Streamlit frontend |
| `DATABASE_URL` | `postgresql://devin:devin@localhost:5432/devin_brother` | ✅ | Postgres connection string |
| `POSTGRES_USER` | `devin` | ❌ | Postgres username (Docker Compose) |
| `POSTGRES_PASSWORD` | `devin` | ❌ | Postgres password (Docker Compose) |
| `POSTGRES_DB` | `devin_brother` | ❌ | Postgres database name (Docker Compose) |
| `POSTGRES_PORT` | `5432` | ❌ | Postgres host port (Docker Compose) |
| `DYB_SANDBOX_DIR` | OS temp dir | ❌ | Host path for generated scripts |
| `STREAMLIT_PORT` | `8501` | ❌ | Streamlit host port (Docker Compose) |
| `DYB_THREAD_ID` | Auto-generated | ❌ | Stable thread ID for CLI invocations |

---

## 🔐 Security Model

| Control | Status |
|---------|--------|
| Ephemeral containers (auto-removed) | ✅ |
| Read-only volume mount for scripts | ✅ |
| 10-second execution timeout | ✅ |
| Pre-execution Validator (static analysis) | ✅ |
| API error payload interception | ✅ |
| Network isolation (`--network none`) | ⚠️ Not enforced |
| CPU / memory / PID limits | ⚠️ Not configured |
| Non-root container user | ⚠️ Not configured |
| Debugger path bypasses Validator | ⚠️ Known gap |

> **Threat model:** Suitable for **trusted developer workflows** and portfolio demonstrations. Not hardened for arbitrary untrusted code execution without additional container hardening.

---

## 🎯 Example Prompts

| Type | Example | Pipeline Path |
|------|---------|--------------|
| **Coding** (full pipeline) | *Write a Python script that fetches JSON from an API and handles a missing `items` key.* | Router → Planner → Coder → Validator → Terminal ↔ Debugger |
| **Research** (no sandbox) | *Explain how LangGraph conditional routing works.* | Router → Research → END |
| **Generic** (no sandbox) | *What are the trade-offs between monoliths and microservices?* | Router → Knowledge → END |

---

## 🏛️ Design Decisions

- **Decoupled architecture** — FastAPI owns all LangGraph/Postgres/Docker logic; Streamlit is a pure HTTP/SSE client
- **SSE over WebSockets** — simpler protocol, native browser support, one-directional streaming fits the pipeline model
- **Thread-pool executor** — synchronous LangGraph `.stream()` runs off the asyncio event loop via `ThreadPoolExecutor`
- **Python 3.9+ compatibility** — `Optional[...]` type hints; `importlib.metadata` monkey-patch for older runtimes
- **Router-first execution** — prevents unnecessary Docker spin-up for research/generic queries
- **Validator-before-sandbox** — catches dangerous patterns and missing error handling before runtime failures

---

## 📄 License

MIT

---

<div align="center">

**Built with ❤️ by [Harsh Sharma](https://github.com/Harsh-Sharma29)**

</div>
