import { useEffect, useRef, useCallback, useMemo } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useStore } from '../store';
import type { GraphNode } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '';

const TYPE_COLORS: Record<string, string> = {
  SalesOrder: '#4F46E5',
  Delivery: '#0891B2',
  BillingDocument: '#059669',
  JournalEntry: '#D97706',
  Payment: '#DC2626',
  Customer: '#7C3AED',
  Product: '#DB2777',
  Plant: '#65A30D',
};

export default function GraphPanel() {
  const {
    nodes,
    edges,
    graphLoading,
    highlightedNodeIds,
    selectedNode,
    setGraphData,
    addGraphData,
    setSelectedNode,
    setGraphLoading,
    setNodeTypes,
  } = useStore();

  const graphRef = useRef<any>(null);

  // Fetch initial graph data
  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const [graphRes, typesRes] = await Promise.all([
          fetch(`${API_BASE}/api/graph?limit=500`),
          fetch(`${API_BASE}/api/node-types`),
        ]);
        const graphData = await graphRes.json();
        const typesData = await typesRes.json();

        setNodeTypes(typesData);
        setGraphData(
          graphData.nodes.map((n: GraphNode) => ({
            ...n,
            color: TYPE_COLORS[n.type] || '#6B7280',
          })),
          graphData.edges,
          graphData.total
        );
      } catch (err) {
        console.error('Failed to fetch graph:', err);
        setGraphLoading(false);
      }
    };
    fetchGraph();
  }, [setGraphData, setGraphLoading, setNodeTypes]);

  // Expand node on click
  const handleNodeClick = useCallback(
    async (node: any) => {
      setSelectedNode(node as GraphNode);
      try {
        const res = await fetch(
          `${API_BASE}/api/expand?nodeId=${encodeURIComponent(node.id)}`
        );
        const data = await res.json();
        if (data.nodes?.length) {
          addGraphData(
            data.nodes.map((n: GraphNode) => ({
              ...n,
              color: TYPE_COLORS[n.type] || '#6B7280',
            })),
            data.edges || []
          );
        }
      } catch (err) {
        console.error('Failed to expand node:', err);
      }
    },
    [addGraphData, setSelectedNode]
  );

  // Canvas rendering for nodes
  const paintNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const isHighlighted = highlightedNodeIds.has(node.id);
      const isSelected = selectedNode?.id === node.id;
      const radius = isHighlighted ? 6 : isSelected ? 5 : 4;
      const color = node.color || '#6B7280';

      // Glow effect for highlighted nodes
      if (isHighlighted) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius + 3, 0, 2 * Math.PI);
        ctx.fillStyle = color + '40';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(node.x, node.y, radius + 6, 0, 2 * Math.PI);
        ctx.fillStyle = color + '20';
        ctx.fill();
      }

      // Selection ring
      if (isSelected) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, radius + 2, 0, 2 * Math.PI);
        ctx.strokeStyle = '#fff';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      // Node circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      // Label at sufficient zoom
      if (globalScale > 1.5) {
        const label = node.label || node.id;
        const fontSize = Math.max(10 / globalScale, 2);
        ctx.font = `${fontSize}px sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillStyle = '#e5e7eb';
        ctx.fillText(label, node.x, node.y + radius + 2);
      }
    },
    [highlightedNodeIds, selectedNode]
  );

  // Graph data formatted for react-force-graph
  const graphData = useMemo(
    () => ({
      nodes: nodes.map((n) => ({ ...n })),
      links: edges.map((e) => ({ source: e.source, target: e.target, type: e.type })),
    }),
    [nodes, edges]
  );

  if (graphLoading) {
    return (
      <div className="graph-panel loading">
        <div className="spinner" />
        <p>Loading graph...</p>
      </div>
    );
  }

  return (
    <div className="graph-panel">
      <div className="graph-header">
        <h2>O2C Process Graph</h2>
        <span className="graph-stats">
          {nodes.length} nodes / {edges.length} edges
        </span>
      </div>
      <Legend />
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        nodeCanvasObject={paintNode}
        nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
          ctx.beginPath();
          ctx.arc(node.x, node.y, 6, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
        }}
        linkColor={() => '#374151'}
        linkWidth={0.5}
        linkDirectionalArrowLength={3}
        linkDirectionalArrowRelPos={1}
        onNodeClick={handleNodeClick}
        backgroundColor="#111827"
        cooldownTicks={100}
        onEngineStop={() => graphRef.current?.zoomToFit(400, 50)}
      />
      {selectedNode && <NodeDetail node={selectedNode} onClose={() => setSelectedNode(null)} />}
    </div>
  );
}

function Legend() {
  return (
    <div className="legend">
      {Object.entries(TYPE_COLORS).map(([type, color]) => (
        <span key={type} className="legend-item">
          <span className="legend-dot" style={{ backgroundColor: color }} />
          {type}
        </span>
      ))}
    </div>
  );
}

function NodeDetail({ node, onClose }: { node: GraphNode; onClose: () => void }) {
  return (
    <div className="node-detail">
      <div className="node-detail-header">
        <h3>{node.label}</h3>
        <button onClick={onClose}>&times;</button>
      </div>
      <div className="node-detail-type">{node.type}</div>
      <div className="node-detail-meta">
        {Object.entries(node.metadata || {}).map(([key, value]) => (
          <div key={key} className="meta-row">
            <span className="meta-key">{key}</span>
            <span className="meta-value">{String(value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
