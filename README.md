# Hermes v3

A personal AI agent with ReAct-style planning, hybrid retrieval, and a local LLM backend.

## Architecture

**Backend** — FastAPI (`backend/main.py`)

- **Agent** (`backend/agent/`)
  - `planner.py` — ReAct-style reasoning/action loop
  - `tools.py` — tool definitions available to the agent

- **Memory system** (`backend/memory/`) — layered, each backed by its own store in `backend/data/`
  - `episodic.py` → `episodic.db` — event/interaction history
  - `semantic.py` → `semantic.db` — factual/conceptual knowledge
  - `procedural.py` → `procedural.db` — learned procedures/skills
  - `working.py` → `working_memory.json` — active context window
  - `graph.py` → `graph.db` — relational/entity graph
  - `lexicon.py` → `lexicon.db` — vocabulary/term store
  - `consolidation.py` → `consolidation.db` — periodic memory consolidation between layers
  - `retrieval.py` — hybrid retrieval orchestration (BM25 + dense)
  - `manager.py` — unified interface across all memory layers

- **Retrieval engine** (`backend/engine/`)
  - `embeddings.py` — BGE-M3 dense embeddings, indexed in ChromaDB (`backend/data/chroma/`)
  - `llm.py` — Ollama client (`qwen2.5-coder:7b`)
  - `scheduler.py` — background task scheduling (e.g. consolidation runs)

- **Media/conversation ingestion** (`backend/media/`)
  - `conversation.py`, `entry.py`, `patterns.py` — parsing and structuring ingested conversation logs

- **Connectors** (`backend/connectors/`)
  - `portal_scraper.py` — external data ingestion

- **API routers** (`backend/routers/`) — `chat`, `memory`, `goals`, `ingest`, `lexicon`, `media`, `models`, `profile`

**Frontend** — React + Vite (`frontend/`)
  - Pages: Chat, Dashboard, Goals, Ingest, Lexicon, Media, Memories, Models, Profile

## Setup

### Prerequisites
- Python 3.12+
- Node.js (for the frontend)
- An LLM backend — either [Ollama](https://ollama.ai) running locally (default: `qwen2.5-coder:7b`) or an API key for another AI provider
- If using Ollama: `ollama pull qwen2.5-coder:7b`

### Installation

```bash
git clone https://github.com/rjvishal080/hermes-v3.git
cd hermes-v3

# Backend
cd backend
pip install -r requirements.txt --break-system-packages
cp .env.example .env   # configure your LLM backend / API key

# Frontend
cd ../frontend
npm install
```

### Running

```bash
./start.sh   # attempts to start backend + frontend together
```

If that doesn't work, run them separately:

```bash
# Terminal 1 — backend
cd backend && uvicorn main:app --reload

# Terminal 2 — frontend
cd frontend && npm run dev
```

## Usage

Once running, the dashboard is available in your browser (default: `http://localhost:5173` or wherever Vite serves it).

- **Chat** — talk to the agent directly
- **Dashboard** — overview of agent activity
- **Goals** — track and manage agent goals/tasks
- **Ingest** — feed new data/conversations into the agent's memory
- **Lexicon** — browse the agent's learned vocabulary/terms
- **Media** — manage ingested media/conversation files
- **Memories** — browse episodic, semantic, and procedural memory
- **Models** — configure the LLM backend
- **Profile** — agent identity/persona settings

## Tech Stack

**Backend:** Python, FastAPI, ChromaDB, BGE-M3 / BGE-reranker-v2-m3, Ollama
**Frontend:** React, Vite
**Storage:** SQLite (episodic, semantic, procedural, graph, lexicon, consolidation)

## License

This project is licensed under the MIT License — see [LICENSE](LICENSE) for details.

## Author

Built by [Vishal R J](https://github.com/rjvishal080)
