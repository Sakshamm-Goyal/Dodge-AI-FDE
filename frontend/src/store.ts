import { create } from 'zustand';
import type { GraphNode, GraphEdge, ChatMessage } from './types';

interface AppStore {
  // Graph state
  nodes: GraphNode[];
  edges: GraphEdge[];
  totalNodes: number;
  graphLoading: boolean;
  selectedNode: GraphNode | null;

  // Highlight state (from chat)
  highlightedNodeIds: Set<string>;

  // Chat state
  messages: ChatMessage[];
  chatLoading: boolean;
  sessionId: string;

  // Node types for legend
  nodeTypes: Record<string, { prefix: string; color: string; label: string }>;

  // Actions
  setGraphData: (nodes: GraphNode[], edges: GraphEdge[], total: number) => void;
  addGraphData: (nodes: GraphNode[], edges: GraphEdge[]) => void;
  setGraphLoading: (loading: boolean) => void;
  setSelectedNode: (node: GraphNode | null) => void;
  setHighlightedNodeIds: (ids: string[]) => void;
  clearHighlights: () => void;
  addMessage: (msg: ChatMessage) => void;
  setChatLoading: (loading: boolean) => void;
  setNodeTypes: (types: Record<string, { prefix: string; color: string; label: string }>) => void;
}

export const useStore = create<AppStore>((set) => ({
  nodes: [],
  edges: [],
  totalNodes: 0,
  graphLoading: true,
  selectedNode: null,
  highlightedNodeIds: new Set(),
  messages: [
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Welcome! I can help you explore the SAP Order-to-Cash dataset. Try asking:\n\n' +
        '- "Which products have the most billing documents?"\n' +
        '- "Trace the full flow of billing document 90504259"\n' +
        '- "Find sales orders with incomplete flows"',
    },
  ],
  chatLoading: false,
  sessionId: 'session-' + Date.now(),
  nodeTypes: {},

  setGraphData: (nodes, edges, total) =>
    set({ nodes, edges, totalNodes: total, graphLoading: false }),

  addGraphData: (newNodes, newEdges) =>
    set((state) => {
      const existingIds = new Set(state.nodes.map((n) => n.id));
      const uniqueNodes = newNodes.filter((n) => !existingIds.has(n.id));
      const existingEdgeKeys = new Set(
        state.edges.map((e) => `${e.source}-${e.target}`)
      );
      const uniqueEdges = newEdges.filter(
        (e) => !existingEdgeKeys.has(`${e.source}-${e.target}`)
      );
      return {
        nodes: [...state.nodes, ...uniqueNodes],
        edges: [...state.edges, ...uniqueEdges],
      };
    }),

  setGraphLoading: (loading) => set({ graphLoading: loading }),

  setSelectedNode: (node) => set({ selectedNode: node }),

  setHighlightedNodeIds: (ids) =>
    set({ highlightedNodeIds: new Set(ids) }),

  clearHighlights: () => set({ highlightedNodeIds: new Set() }),

  addMessage: (msg) =>
    set((state) => ({ messages: [...state.messages, msg] })),

  setChatLoading: (loading) => set({ chatLoading: loading }),

  setNodeTypes: (types) => set({ nodeTypes: types }),
}));
