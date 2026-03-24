"""Pydantic models for request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel


class ChatRequest(BaseModel):
    query: str
    sessionId: str = "default"


class NodeData(BaseModel):
    id: str
    type: str
    label: str
    metadata: dict


class EdgeData(BaseModel):
    source: str
    target: str
    type: str


class GraphResponse(BaseModel):
    nodes: list[NodeData]
    edges: list[EdgeData]
    total: int


class NodeDetailResponse(BaseModel):
    id: str
    type: str
    label: str
    metadata: dict
    connections: int
