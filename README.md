<div align="center">

# 🧠 Devin's Younger Brother

### ⚡ Autonomous AI Software Engineer — Powered by LangGraph & Groq

**Plan → Code → Validate → Execute → Self-Heal**

[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![Groq](https://img.shields.io/badge/Groq-Llama_3.3_70B-F55036?logo=meta&logoColor=white)](https://groq.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.6-1C3C3C?logo=langchain&logoColor=white)](https://langchain-ai.github.io/langgraph/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.50-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io)
[![Docker](https://img.shields.io/badge/Docker-Sandbox-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

*A fully autonomous, multi-agent software engineering system that plans, writes, validates, executes, and self-heals Python code inside an isolated Docker sandbox — powered by Groq's lightning-fast Llama 3.3 70B inference engine.*

---

</div>

## 🔥 Key Features

| Feature | Description |
|---------|-------------|
| 🧠 **Llama 3.3 70B on Groq** | Lightning-fast code generation via Groq's inference engine — sub-second tool calling with zero Protobuf serialization issues |
| 🐳 **Docker Sandbox Execution** | All generated code runs inside ephemeral `python:3.11-slim` containers with 10s timeouts — your host machine is never at risk |
| ⚡ **WebSocket Live Terminal** | Real-time streaming of Docker sandbox output directly to the UI, providing an interactive terminal experience |
| 🔬 **AST-Powered Validator** | Self-healing code pipeline — an `ast.NodeVisitor` statically analyzes every generated script for unsafe operations, hardcoded secrets, and missing `try/except` blocks *before* execution |
| 🐙 **GitHub Integration** | Autonomous repository navigation — the Coder can browse directories and read files from any GitHub repo using built-in `PyGithub` tools |
| 🔍 **Tavily Web Search** | Real-time API documentation lookup via Tavily — with strict intent-routing to prevent tool over-triggering |
| 🔄 **Self-Healing Debugger** | If code crashes in the sandbox, tracebacks are automatically fed back to a Debugger agent that rewrites stdlib-only fixes in a closed loop |
| 💾 **Persistent Memory** | PostgreSQL-backed checkpointing — conversation state survives page reloads with sliding-window context injection |
| 🖥️ **Pro IDE Frontend** | 3-pane Streamlit layout with live pipeline graph, syntax-highlighted code editor, real-time terminal, and chat history |

---

## 🏗️ Architecture — The ReAct Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LangGraph State Machine                          │
│                                                                     │
│  START ──▸ Router ──┬──▸ Planner ──▸ Coder ──▸ Validator ──┬──▸ Terminal  │
│                     │         ▲              │               │      │      │
│                     │         └──────────────┘  (reject)     │      │      │
│                     │         (self-reflection loop)         │      ▼      │
│                     │                                        │  Debugger   │
│                     │                                        │      │      │
│                     │                                        └──────┘      │
│                     ├──▸ Research Agent ──▸ END                            │
│                     └──▸ Knowledge Agent ──▸ END                           │
└─────────────────────────────────────────────────────────────────────┘
                                     │
                   ┌─────────────────▼─────────────────┐
                   │     Docker Sandbox (ephemeral)      │
                   │     python:3.11-slim · 10s timeout  │
                   └────────────────────────────────────┘
```

### 🔁 How the Pipeline Works

1. **🧭 Router** — Classifies user intent (`coding` / `research` / `generic`) to avoid unnecessary Docker spin-ups
2. **📋 Planner** — Generates a mission brief with artifact targeting and strategy selection
3. **💻 Coder** — Groq Llama 3.3 generates Python code using a ReAct tool-calling loop (GitHub + Tavily)
4. **✅ Validator** — AST-based static analysis catches dangerous ops, secrets, and missing error handling
5. **🐳 Terminal** — Executes validated code inside an ephemeral Docker container
6. **🔧 Debugger** — Feeds tracebacks back for autonomous self-healing repairs (up to 5 attempts)

---

## 📋 Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **Python** | 3.9+ | Runtime |
| **Docker Desktop** | Latest | Sandboxed code execution |
| **PostgreSQL** | 16+ (via Docker Compose) | LangGraph state persistence |
| **Groq API Key** | — | 🧠 Primary LLM engine ([get one free](https://console.groq.com)) |
| **Tavily API Key** | — | 🔍 Web search tool ([get one free](https://tavily.com)) |
| **GitHub Token** | — | 🐙 Repository access (optional) |

---

## 🚀 Quick Start

### 1️⃣ Clone & Install

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

### 2️⃣ Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
GROQ_API_KEY=gsk_your_groq_api_key_here
TAVILY_API_KEY=tvly-your_tavily_key_here
GITHUB_ACCESS_TOKEN=ghp_your_github_token_here

# Database (auto-configured by Docker Compose)
DATABASE_URL=postgresql://devin:devin@localhost:5432/devin_brother?sslmode=disable
DYB_API_URL=http://localhost:8005
NEXT_PUBLIC_API_URL=http://localhost:8005
```

### 3️⃣ Start Infrastructure

```bash
# Start PostgreSQL database
docker compose up -d
```

> ⚠️ Make sure **Docker Desktop** is running before this step.

### 4️⃣ Launch the Application

Open **two separate terminals**:

**Terminal 1 — 🖥️ FastAPI Backend:**
```bash
cd backend
python -m uvicorn src.api.server:app --host 127.0.0.1 --port 8005
```

**Terminal 2 — 🎨 Next.js Frontend:**
```bash
cd frontend
npm run dev
```

Alternatively, run everything via Docker:
```bash
docker compose up -d --build
```

### 5️⃣ Open the IDE

Navigate to **http://localhost:3005**, enter a coding prompt, and click **🚀 Execute Pipeline**.

---

## 🤖 Multi-Agent System

| Agent | Responsibility |
|-------|---------------|
| **🧭 Router** | Intent classification — `coding` / `research` / `generic` — before any expensive work |
| **📋 Planner** | Mission brief, artifact targeting, and strategy selection |
| **💻 Coder** | Groq Llama 3.3 code synthesis with ReAct tool-calling loop and multi-file workspace output |
| **✅ Validator** | Pre-sandbox AST-based static analysis (dangerous ops, secrets, error handling) |
| **🐳 Terminal** | Docker sandbox execution with 10-second timeout |
| **🔧 Debugger** | Traceback-driven self-healing repair loop (stdlib-only rewrites) |
| **📚 Research** | Technical research answers (no sandbox) |
| **💡 Knowledge** | Generic Q&A (no sandbox) |

---

## 🔒 Cyclic Loop Safeguards

| Loop | Cap | Exit Condition |
|------|-----|---------------|
| Coder ↔ Validator | 3 attempts | Pass validation, or force Terminal |
| Coder ↔ ToolNode | 3 rounds | Max tool-calling rounds reached |
| Terminal ↔ Debugger | 5 attempts | `is_verified=True`, empty errors, or cap reached |
| LangGraph global | `recursion_limit=50` | Hard ceiling on total node invocations |

---

## 📡 API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | System health: Postgres status, API key status, telemetry |
| `POST` | `/api/v1/session/new` | Generate a new backend-authoritative `thread_id` |
| `GET` | `/api/v1/history/{thread_id}` | Retrieve conversation history for a session |
| `POST` | `/api/v1/execute` | Execute the LangGraph pipeline (SSE streaming response) |

---

## 📁 Project Structure

Devin/
├── docker-compose.yml              # Full stack: Postgres + Backend + Frontend
├── .env.example                    # Environment template
├── backend/
│   ├── main.py                     # CLI LangGraph entry point
│   ├── Dockerfile                  # FastAPI backend image
│   ├── requirements.txt            # Python dependencies
│   └── src/
│       ├── api/
│       │   └── server.py           # FastAPI backend — SSE streaming, endpoints
│       ├── core/
│       ├── agents/
│       └── tools/
├── frontend/
│   ├── Dockerfile                  # Next.js frontend image
│   ├── package.json                # Node dependencies
│   └── src/                        # Next.js App Router code
└── legacy/
    └── app.py                      # Archived Streamlit Pro IDE frontend

---

## ⚙️ Configuration Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | ✅ | Groq API key — powers Llama 3.3 70B |
| `TAVILY_API_KEY` | ⚠️ Recommended | Tavily web search for real-time docs |
| `GITHUB_ACCESS_TOKEN` | ❌ Optional | GitHub repository access |
| `DATABASE_URL` | ✅ | PostgreSQL connection string |
| `DYB_API_URL` | ✅ | FastAPI backend URL (`http://localhost:8000`) |
| `HUGGINGFACEHUB_API_TOKEN` | ❌ Optional | HuggingFace Hub token for failover LLM |

---

## 🎯 Example Prompts

| Type | Example | Pipeline Path |
|------|---------|--------------|
| **💻 Coding** | *Write a Python script that fetches JSON from an API and handles a missing `items` key.* | Router → Planner → Coder → Validator → Terminal ↔ Debugger |
| **🐙 GitHub** | *Read the README from `langchain-ai/langchain` and summarize it.* | Router → Planner → Coder (GitHub tools) → Validator → Terminal |
| **📚 Research** | *Explain how LangGraph conditional routing works.* | Router → Research → END |
| **💡 Generic** | *What are the trade-offs between monoliths and microservices?* | Router → Knowledge → END |

---

## 🔐 Security Model

| Control | Status |
|---------|--------|
| Ephemeral containers (auto-removed) | ✅ |
| Read-only volume mount for scripts | ✅ |
| 10-second execution timeout | ✅ |
| AST-based Validator (static analysis) | ✅ |
| API error payload interception | ✅ |
| Dangerous pattern detection (`eval`, `exec`, `os.remove`) | ✅ |
| Hardcoded credential detection | ✅ |

> **Threat model:** Suitable for **trusted developer workflows** and portfolio demonstrations.

---

## 📄 License

MIT

---

<div align="center">

**Built with ❤️ by [Harsh Sharma](https://github.com/Harsh-Sharma29)**

*Powered by 🧠 Groq · 🦜 LangGraph · 🐳 Docker · 🐙 PyGithub · 🔍 Tavily*

</div>
