# SAP O2C Graph Explorer

An interactive graph-based data modeling and query system for SAP Order-to-Cash (O2C) data. Built for the Dodge AI Forward Deployed Engineer assignment.

**Live Demo:** [Coming soon — deploying to Render]

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   FRONTEND (React + Vite)                │
│  ┌─────────────────┐  ┌──────────────────────────────┐  │
│  │ GraphPanel       │  │ ChatPanel                     │ │
│  │ react-force-     │  │ - NL input                    │ │
│  │ graph-2d         │◄─┤ - SSE streaming               │ │
│  │ - click expand   │  │ - SQL display                 │ │
│  │ - hover labels   │  │ - Conversation history        │ │
│  │ - highlighting   │  │ - Node highlight triggers     │ │
│  └─────────────────┘  └──────────────────────────────┘  │
│         Zustand store: highlightedNodeIds                │
└──────────────────────────┬──────────────────────────────┘
                           │ REST + SSE
┌──────────────────────────┴──────────────────────────────┐
│                  BACKEND (FastAPI + Python)               │
│                                                          │
│  Endpoints:                                              │
│  GET  /api/graph?limit=500&entityType=all                │
│  GET  /api/node/{nodeId}                                 │
│  GET  /api/expand?nodeId=SO:740506                       │
│  POST /api/chat (SSE stream)                             │
│  GET  /api/schema                                        │
│  GET  /api/node-types                                    │
│  GET  /api/broken-flows                                  │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────┐ │
│  │ NetworkX │  │ Gemini   │  │ Guardrails (3-layer)   │ │
│  │ graph    │  │ 2.5 Flash│  │ 1. keyword check       │ │
│  │ analysis │  │ NL→SQL   │  │ 2. system prompt       │ │
│  └────┬─────┘  └────┬─────┘  │ 3. SQL output validate │ │
│       │              │        └────────────────────────┘ │
│  ┌────┴──────────────┴──────┐                            │
│  │    SQLite (WAL mode)     │                            │
│  │    19 tables from JSONL  │                            │
│  └──────────────────────────┘                            │
└──────────────────────────────────────────────────────────┘
```

## Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | SQLite | Zero deployment friction, JSONL data is tabular, SQL is easier for LLMs to generate than Cypher |
| Graph engine | NetworkX (server-side) | Graph analysis (path finding, broken flows) without graph DB overhead |
| Graph viz | react-force-graph-2d | Canvas-based, handles 500+ nodes, mature React component |
| LLM | Gemini 2.5 Flash + 2.0 Flash-Lite fallback | Flash for SQL quality, auto-fallback on rate limits |
| Streaming | SSE (not WebSocket) | Simpler, unidirectional sufficient, FastAPI native |
| State mgmt | Zustand | Minimal boilerplate for chat-to-graph communication |

## Graph Data Model

```
SalesOrder ──SOLD_TO──→ Customer
SalesOrder ──HAS_ITEM──→ Product
SalesOrder ──DELIVERED_BY──→ Delivery ──FROM_PLANT──→ Plant
Delivery ──BILLED_IN──→ BillingDocument
BillingDocument ──POSTED_AS──→ JournalEntry
JournalEntry ──CLEARED_BY──→ Payment
```

**713 nodes** across 8 entity types, **825 edges** across 7 relationship types, ingested from **19 JSONL entity tables**.

## LLM Prompting Strategy

The NL-to-SQL pipeline uses a two-pass approach:

1. **Query Pass:** Send user question + full database schema + sample rows + FK relationship descriptions to Gemini 2.5 Flash. The model generates a SQL query wrapped in a code block.
2. **Summary Pass:** Execute the SQL against SQLite, then send the results back to Gemini for a natural language summary with specific document IDs and amounts.

The system prompt includes the complete schema, sample data from key tables, and explicit JOIN relationship descriptions so the LLM can generate correct multi-table queries.

## Guardrails (3-Layer)

1. **Keyword Check (pre-LLM):** Scans the query for SAP/O2C domain terms. Off-topic queries are rejected immediately without an LLM call.
2. **System Prompt:** Explicit instruction to refuse non-O2C questions and only generate SQLite-compatible SELECT queries.
3. **SQL Validation (post-LLM):** Regex-based check that only SELECT statements are generated. Table/column names are validated against the known schema using sqlparse. No raw error messages are exposed.

## Features

- **Interactive Graph Visualization:** Force-directed graph with 500-node view, color-coded by entity type, click-to-expand neighbors
- **NL-to-SQL Chat:** Ask questions in natural language, see generated SQL and results
- **Node Highlighting:** Chat results automatically highlight relevant nodes in the graph
- **Broken Flow Detection:** Identifies sales orders with incomplete O2C flows (missing deliveries, billing, etc.)
- **Conversation Memory:** 10-message sliding window per session
- **SSE Streaming:** Real-time response streaming from the LLM
- **SQL Display:** Collapsible SQL block showing the generated query

## Setup

### Prerequisites
- Python 3.9+
- Node.js 18+
- Gemini API key ([Get one here](https://aistudio.google.com/apikey))

### Local Development

```bash
# Clone
git clone https://github.com/your-username/Dodge-AI-FDE.git
cd Dodge-AI-FDE

# Backend
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
pip install -r backend/requirements.txt

# Ingest data (first time only)
python -m backend.database

# Start backend
uvicorn backend.main:app --reload --port 8000

# Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 to use the app.

### Run Tests

```bash
python -m pytest backend/test_api.py -v
```

### Production Build

```bash
cd frontend && npm run build
# Backend serves frontend from frontend/dist/
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Example Queries

1. **"Which products are associated with the highest number of billing documents?"** — Generates a multi-table JOIN with GROUP BY and ORDER BY, returns top products with counts.
2. **"Trace the full flow of billing document 90504259"** — Traces the O2C chain from billing → delivery → sales order → customer.
3. **"Identify sales orders with broken or incomplete flows"** — Uses the `/api/broken-flows` endpoint powered by NetworkX graph traversal.

## Project Structure

```
Dodge-AI-FDE/
├── backend/
│   ├── main.py           # FastAPI app, routes, lifespan
│   ├── database.py       # SQLite ingestion, schema, FK validation
│   ├── graph.py          # NetworkX graph construction + analysis
│   ├── llm.py            # Gemini NL→SQL pipeline
│   ├── guardrails.py     # 3-layer query validation
│   ├── models.py         # Pydantic schemas
│   ├── test_api.py       # Integration tests (20 tests)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main layout
│   │   ├── components/
│   │   │   ├── GraphPanel.tsx   # Force-directed graph
│   │   │   └── ChatPanel.tsx    # Chat interface
│   │   ├── hooks/useChat.ts     # SSE streaming hook
│   │   ├── store.ts             # Zustand state
│   │   └── types.ts             # TypeScript types
│   └── package.json
├── sap-o2c-data/         # JSONL dataset (19 entities)
├── render.yaml           # Render deployment config
├── .env.example
└── README.md
```
