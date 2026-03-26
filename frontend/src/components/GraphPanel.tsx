import { useEffect, useRef, useCallback, useMemo, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useStore } from '../store';
import type { GraphNode } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '';

// Vibrant colors — blue family for process nodes, warm for entity nodes
const TYPE_COLORS: Record<string, string> = {
  SalesOrder: '#4f46e5',
  Delivery: '#2563eb',
  BillingDocument: '#3b82f6',
  JournalEntry: '#6366f1',
  Payment: '#e11d48',
  Customer: '#ec4899',
  Product: '#f43f5e',
  Plant: '#8b5cf6',
};

const TYPE_DISPLAY: Record<string, string> = {
  SalesOrder: 'Sales Order',
  Delivery: 'Delivery',
  BillingDocument: 'Billing Doc',
  JournalEntry: 'Journal Entry',
  Payment: 'Payment',
  Customer: 'Customer',
  Product: 'Product',
  Plant: 'Plant',
};

// Edge colors by relationship type
const EDGE_COLORS: Record<string, string> = {
  HAS_ITEM: '#8b5cf6',
  SOLD_TO: '#ec4899',
  DELIVERED_BY: '#2563eb',
  BILLED_IN: '#3b82f6',
  POSTED_AS: '#6366f1',
  CLEARED_BY: '#e11d48',
  FROM_PLANT: '#22c55e',
};

interface Props {
  showLabels: boolean;
}

export default function GraphPanel({ showLabels }: Props) {
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
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const prevHighlightRef = useRef<Set<string>>(new Set());

  // Track container size
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const obs = new ResizeObserver((entries) => {
      const { width, height } = entries[0].contentRect;
      setDimensions({ width, height });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Customize d3 forces for a wide, spread-out layout
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg) return;
    fg.d3Force('charge')?.strength(-200);
    fg.d3Force('link')?.distance(35).strength(0.5);
    fg.d3Force('center')?.strength(0.05);
    fg.d3ReheatSimulation();
  }, [nodes]);

  // Auto-zoom to highlighted nodes when chat highlights change
  useEffect(() => {
    const fg = graphRef.current;
    if (!fg || highlightedNodeIds.size === 0) return;
    // Only zoom when highlights actually changed (not on every re-render)
    const prev = prevHighlightRef.current;
    const changed = highlightedNodeIds.size !== prev.size ||
      [...highlightedNodeIds].some(id => !prev.has(id));
    if (!changed) return;
    prevHighlightRef.current = new Set(highlightedNodeIds);

    // Find the highlighted nodes and zoom to fit them
    const hlNodes = nodes.filter(n => highlightedNodeIds.has(n.id));
    if (hlNodes.length === 0) return;

    // For a single node, center on it
    if (hlNodes.length === 1) {
      const n = hlNodes[0];
      if (n.x != null && n.y != null) {
        fg.centerAt(n.x, n.y, 800);
        fg.zoom(4, 800);
      }
      return;
    }

    // For multiple nodes, zoom to fit them all with some padding
    const validNodes = hlNodes.filter(n => n.x != null && n.y != null);
    if (validNodes.length === 0) return;

    const xs = validNodes.map(n => n.x!);
    const ys = validNodes.map(n => n.y!);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const cx = (minX + maxX) / 2;
    const cy = (minY + maxY) / 2;

    fg.centerAt(cx, cy, 800);
    // Zoom level based on spread — closer for tight clusters
    const spread = Math.max(maxX - minX, maxY - minY, 50);
    const targetZoom = Math.min(8, Math.max(1.5, 400 / spread));
    fg.zoom(targetZoom, 800);
  }, [highlightedNodeIds, nodes]);

  // After engine settles, zoom in to fill the viewport
  const handleEngineStop = useCallback(() => {
    const fg = graphRef.current;
    if (!fg) return;
    fg.zoomToFit(400, 40);
  }, []);

  // Fetch initial graph data — load all nodes for a dense graph
  useEffect(() => {
    const fetchGraph = async () => {
      try {
        const [graphRes, typesRes] = await Promise.all([
          fetch(`${API_BASE}/api/graph?limit=800`),
          fetch(`${API_BASE}/api/node-types`),
        ]);
        const graphData = await graphRes.json();
        const typesData = await typesRes.json();

        setNodeTypes(typesData);
        setGraphData(
          graphData.nodes.map((n: GraphNode) => ({
            ...n,
            color: TYPE_COLORS[n.type] || '#94a3b8',
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
              color: TYPE_COLORS[n.type] || '#94a3b8',
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

  // Build connection count map from edges
  const connectionCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const e of edges) {
      counts[e.source] = (counts[e.source] || 0) + 1;
      counts[e.target] = (counts[e.target] || 0) + 1;
    }
    return counts;
  }, [edges]);

  // Canvas rendering for nodes — solid filled circles with labels
  const paintNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const isHighlighted = highlightedNodeIds.has(node.id);
      const isSelected = selectedNode?.id === node.id;
      const conns = connectionCounts[node.id] || 0;

      // Size nodes by connectivity — hub nodes are bigger
      const baseRadius = isHighlighted ? 6 : isSelected ? 5.5 : Math.max(3, Math.min(5, 2.5 + conns * 0.3));
      const color = node.color || '#94a3b8';

      // Highlighted glow rings — pulsing effect
      if (isHighlighted) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, baseRadius + 12, 0, 2 * Math.PI);
        ctx.fillStyle = color + '10';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(node.x, node.y, baseRadius + 7, 0, 2 * Math.PI);
        ctx.fillStyle = color + '20';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(node.x, node.y, baseRadius + 3, 0, 2 * Math.PI);
        ctx.fillStyle = color + '35';
        ctx.fill();
      }

      // Selected ring
      if (isSelected) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, baseRadius + 3, 0, 2 * Math.PI);
        ctx.strokeStyle = color + '50';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Solid filled node
      ctx.beginPath();
      ctx.arc(node.x, node.y, baseRadius, 0, 2 * Math.PI);
      ctx.fillStyle = isHighlighted ? color : color;
      ctx.fill();

      // White border for contrast
      ctx.strokeStyle = isHighlighted ? '#ffffff' : '#ffffff';
      ctx.lineWidth = isHighlighted ? 2 : isSelected ? 1.5 : 0.8;
      ctx.stroke();

      // Show labels: always for highlighted, on zoom for overlay mode
      const shouldShowLabel = isHighlighted || (showLabels && globalScale > 1.2);
      if (shouldShowLabel) {
        // For highlighted nodes, show the ID (e.g., "SO 740506")
        const label = isHighlighted
          ? node.label || node.id
          : TYPE_DISPLAY[node.type] || node.type || '';
        const fontSize = isHighlighted
          ? Math.max(12 / globalScale, 3)
          : Math.max(10 / globalScale, 2.5);
        ctx.font = `600 ${fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';

        // Text background for readability
        if (isHighlighted) {
          const metrics = ctx.measureText(label);
          const pad = 2 / globalScale;
          ctx.fillStyle = 'rgba(255,255,255,0.85)';
          ctx.fillRect(
            node.x - metrics.width / 2 - pad,
            node.y + baseRadius + 1,
            metrics.width + pad * 2,
            fontSize + pad
          );
        }

        ctx.fillStyle = isHighlighted ? '#0f172a' : '#334155';
        ctx.fillText(label, node.x, node.y + baseRadius + 2);
      }
    },
    [highlightedNodeIds, selectedNode, showLabels, connectionCounts]
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
      <div className="graph-panel loading" ref={containerRef}>
        <div className="spinner" />
        <p>Loading graph data...</p>
      </div>
    );
  }

  return (
    <div className="graph-panel" ref={containerRef}>
      <ForceGraph2D
        ref={graphRef}
        graphData={graphData}
        width={dimensions.width}
        height={dimensions.height}
        nodeCanvasObject={paintNode}
        nodePointerAreaPaint={(node: any, color: string, ctx: CanvasRenderingContext2D) => {
          ctx.beginPath();
          ctx.arc(node.x, node.y, 10, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
        }}
        linkColor={(link: any) => {
          const linkType = link.type || '';
          const srcId = typeof link.source === 'object' ? link.source.id : link.source;
          const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
          const isHl = highlightedNodeIds.has(srcId) && highlightedNodeIds.has(tgtId);
          if (isHl) return EDGE_COLORS[linkType] || '#4f46e5';
          return EDGE_COLORS[linkType] ? EDGE_COLORS[linkType] + '50' : '#cbd5e1';
        }}
        linkWidth={(link: any) => {
          const srcId = typeof link.source === 'object' ? link.source.id : link.source;
          const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
          const bothHl = highlightedNodeIds.has(srcId) && highlightedNodeIds.has(tgtId);
          if (bothHl) return 3;
          if (highlightedNodeIds.has(srcId) || highlightedNodeIds.has(tgtId)) return 2;
          return 1;
        }}
        linkDirectionalArrowLength={4}
        linkDirectionalArrowRelPos={0.85}
        linkCurvature={0}
        onNodeClick={handleNodeClick}
        backgroundColor="#f8fafc"
        cooldownTicks={200}
        onEngineStop={handleEngineStop}
        d3AlphaDecay={0.01}
        d3VelocityDecay={0.2}
        d3AlphaMin={0.001}
        warmupTicks={80}
        minZoom={0.5}
        maxZoom={12}
      />

      {/* Node tooltip on click */}
      {selectedNode && (
        <NodeTooltip
          node={selectedNode}
          connectionCount={connectionCounts[selectedNode.id] || 0}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}

function NodeTooltip({ node, connectionCount, onClose }: { node: GraphNode; connectionCount: number; onClose: () => void }) {
  const entries = Object.entries(node.metadata || {});
  const visibleEntries = entries.slice(0, 12);
  const hasMore = entries.length > 12;

  return (
    <div className="node-tooltip" onClick={(e) => e.stopPropagation()}>
      <div className="tooltip-header">
        <h3>{TYPE_DISPLAY[node.type] || node.type}</h3>
        <button className="tooltip-close" onClick={onClose}>&times;</button>
      </div>
      <div className="tooltip-body">
        <div className="tooltip-row">
          <span className="tooltip-key">Entity</span>
          <span className="tooltip-val">{TYPE_DISPLAY[node.type] || node.type}</span>
        </div>
        {visibleEntries.map(([key, value]) => (
          <div key={key} className="tooltip-row">
            <span className="tooltip-key">{key}</span>
            <span className="tooltip-val">{value != null ? String(value) : ''}</span>
          </div>
        ))}
        {hasMore && (
          <div className="tooltip-more">
            Additional fields hidden for readability
          </div>
        )}
        <div className="tooltip-row connections">
          <span className="tooltip-key">Connections</span>
          <span className="tooltip-val">{connectionCount}</span>
        </div>
      </div>
    </div>
  );
}
