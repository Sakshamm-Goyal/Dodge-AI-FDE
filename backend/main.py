"""FastAPI application for SAP O2C Graph Explorer."""

import json
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .database import get_connection, ingest_data, get_schema, validate_fk_relationships
from .graph import build_graph, graph_to_json, get_node_detail, expand_node, find_broken_flows, NODE_TYPES
from .llm import process_chat_query
from .models import ChatRequest

# Global state
_graph = None
_conn = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _graph, _conn

    db_path = os.environ.get("DB_PATH", "o2c.db")
    data_dir = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "sap-o2c-data"))

    # Ingest data if DB doesn't exist
    if not os.path.exists(db_path):
        print("Ingesting data...")
        counts = ingest_data(data_dir, db_path)
        print(f"Ingested {sum(counts.values())} records across {len(counts)} tables")

    _conn = get_connection()

    # Validate FK relationships
    print("Validating FK relationships...")
    fk_results = validate_fk_relationships(_conn)
    for r in fk_results:
        print(f"  {r['name']}: {r['matches']} matches [{r['status']}]")

    # Build graph
    print("Building graph...")
    _graph = build_graph(_conn)
    print(f"Graph: {_graph.number_of_nodes()} nodes, {_graph.number_of_edges()} edges")

    yield

    if _conn:
        _conn.close()


app = FastAPI(title="SAP O2C Graph Explorer", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/graph")
def get_graph(
    limit: int = Query(500, ge=1, le=2000),
    entityType: str = Query("all"),
):
    """Get graph data for visualization."""
    return graph_to_json(_graph, limit=limit, entity_type=entityType)


@app.get("/api/node/{node_id:path}")
def get_node(node_id: str):
    """Get detailed info for a single node."""
    detail = get_node_detail(_graph, node_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Node not found")
    return detail


@app.get("/api/expand")
def expand(nodeId: str = Query(...)):
    """Get neighbors of a node for graph expansion."""
    return expand_node(_graph, nodeId)


@app.get("/api/schema")
def schema():
    """Get database schema info."""
    return get_schema(_conn)


@app.get("/api/node-types")
def node_types():
    """Get node type colors for the legend."""
    return NODE_TYPES


@app.get("/api/broken-flows")
def broken_flows():
    """Find sales orders with incomplete O2C flows."""
    return find_broken_flows(_graph)


@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Chat endpoint with SSE streaming."""
    async def event_stream():
        async for event in process_chat_query(request.query, request.sessionId, _conn):
            event_type = event.get("event", "message")
            data = json.dumps(event.get("data", {}))
            yield f"event: {event_type}\ndata: {data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "nodes": _graph.number_of_nodes() if _graph else 0,
        "edges": _graph.number_of_edges() if _graph else 0,
    }


# Serve frontend static files in production
static_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.isdir(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
