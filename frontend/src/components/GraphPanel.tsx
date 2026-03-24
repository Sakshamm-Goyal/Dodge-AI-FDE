import { useEffect, useRef, useCallback, useMemo, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useStore } from '../store';
import type { GraphNode } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '';

const TYPE_COLORS: Record<string, string> = {
  SalesOrder: '#6366f1',
  Delivery: '#3b82f6',
  BillingDocument: '#60a5fa',
  JournalEntry: '#93c5fd',
  Payment: '#e879a0',
  Customer: '#f472b6',
  Product: '#fb7185',
  Plant: '#a78bfa',
};

const TYPE_DISPLAY: Record<string, string> = {
  SalesOrder: 'Sales Order',
  Delivery: 'Delivery',
  BillingDocument: 'Billing Document',
  JournalEntry: 'Journal Entry',
  Payment: 'Payment',
  Customer: 'Customer',
  Product: 'Product',
  Plant: 'Plant',
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

  // Canvas rendering for nodes
  const paintNode = useCallback(
    (node: any, ctx: CanvasRenderingContext2D, globalScale: number) => {
      const isHighlighted = highlightedNodeIds.has(node.id);
      const isSelected = selectedNode?.id === node.id;
      const baseRadius = isHighlighted ? 5 : isSelected ? 4.5 : 3.5;

      const color = node.color || '#94a3b8';

      // Highlighted glow
      if (isHighlighted) {
        ctx.beginPath();
        ctx.arc(node.x, node.y, baseRadius + 8, 0, 2 * Math.PI);
        ctx.fillStyle = color + '15';
        ctx.fill();

        ctx.beginPath();
        ctx.arc(node.x, node.y, baseRadius + 4, 0, 2 * Math.PI);
        ctx.fillStyle = color + '30';
        ctx.fill();
      }

      // Node with border
      ctx.beginPath();
      ctx.arc(node.x, node.y, baseRadius, 0, 2 * Math.PI);
      ctx.fillStyle = '#ffffff';
      ctx.fill();
      ctx.strokeStyle = color;
      ctx.lineWidth = isSelected ? 2.5 : isHighlighted ? 2 : 1.5;
      ctx.stroke();

      // Inner dot
      ctx.beginPath();
      ctx.arc(node.x, node.y, baseRadius * 0.45, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();

      // Label when zoomed in or overlay is on
      if (showLabels && globalScale > 1.2) {
        const label = node.type || '';
        const fontSize = Math.max(9 / globalScale, 2);
        ctx.font = `500 ${fontSize}px -apple-system, BlinkMacSystemFont, sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillStyle = '#64748b';
        ctx.fillText(label, node.x, node.y + baseRadius + 2);
      }
    },
    [highlightedNodeIds, selectedNode, showLabels]
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
          ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
        }}
        linkColor={() => '#bfdbfe'}
        linkWidth={(link: any) => {
          const srcId = typeof link.source === 'object' ? link.source.id : link.source;
          const tgtId = typeof link.target === 'object' ? link.target.id : link.target;
          if (highlightedNodeIds.has(srcId) || highlightedNodeIds.has(tgtId)) return 2;
          return 0.8;
        }}
        linkDirectionalArrowLength={0}
        onNodeClick={handleNodeClick}
        backgroundColor="#f8fafc"
        cooldownTicks={100}
        onEngineStop={() => graphRef.current?.zoomToFit(400, 80)}
        d3AlphaDecay={0.02}
        d3VelocityDecay={0.3}
      />

      {/* Node tooltip on hover */}
      {selectedNode && (
        <NodeTooltip
          node={selectedNode}
          onClose={() => setSelectedNode(null)}
        />
      )}
    </div>
  );
}

function NodeTooltip({ node, onClose }: { node: GraphNode; onClose: () => void }) {
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
          <span className="tooltip-val">{
            Object.keys(node.metadata || {}).length > 0 ? '...' : '0'
          }</span>
        </div>
      </div>
    </div>
  );
}
