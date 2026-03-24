export interface GraphNode {
  id: string;
  type: string;
  label: string;
  metadata: Record<string, unknown>;
  x?: number;
  y?: number;
  fx?: number;
  fy?: number;
  color?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  type: string;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  total: number;
}

export interface NodeType {
  prefix: string;
  color: string;
  label: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'error';
  content: string;
  sql?: string;
  nodeIds?: string[];
  resultCount?: number;
}
