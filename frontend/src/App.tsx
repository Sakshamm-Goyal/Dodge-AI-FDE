import { useState } from 'react';
import { useStore } from './store';
import GraphPanel from './components/GraphPanel';
import ChatPanel from './components/ChatPanel';
import './App.css';

const LEGEND_ITEMS = [
  { type: 'SalesOrder', label: 'Sales Order', color: '#4f46e5' },
  { type: 'Delivery', label: 'Delivery', color: '#2563eb' },
  { type: 'BillingDocument', label: 'Billing', color: '#3b82f6' },
  { type: 'JournalEntry', label: 'Journal Entry', color: '#6366f1' },
  { type: 'Payment', label: 'Payment', color: '#e11d48' },
  { type: 'Customer', label: 'Customer', color: '#ec4899' },
  { type: 'Product', label: 'Product', color: '#f43f5e' },
  { type: 'Plant', label: 'Plant', color: '#8b5cf6' },
];

const FLOW_STEPS = [
  { label: 'Sales Order', color: '#4f46e5' },
  { label: 'Delivery', color: '#2563eb' },
  { label: 'Billing', color: '#3b82f6' },
  { label: 'Journal Entry', color: '#6366f1' },
  { label: 'Payment', color: '#e11d48' },
];

function App() {
  const [showOverlay, setShowOverlay] = useState(true);
  const [showWelcome, setShowWelcome] = useState(true);
  const { nodes, edges, totalNodes, highlightedNodeIds } = useStore();

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <div className="logo-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="3" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="3" width="7" height="7" rx="1" />
              <rect x="3" y="14" width="7" height="7" rx="1" />
              <rect x="14" y="14" width="7" height="7" rx="1" />
            </svg>
          </div>
          <span className="header-sep">|</span>
          <span className="header-nav">Mapping</span>
          <span className="header-nav-sep">/</span>
          <span className="header-nav active">Order to Cash</span>
        </div>
        {highlightedNodeIds.size > 0 && (
          <div className="header-highlight-badge">
            {highlightedNodeIds.size} nodes highlighted
          </div>
        )}
      </header>
      <main className="app-main">
        <div className="graph-wrapper">
          <div className="graph-toolbar">
            <button className="toolbar-btn" onClick={() => setShowWelcome(!showWelcome)}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="16" x2="12" y2="12" />
                <line x1="12" y1="8" x2="12.01" y2="8" />
              </svg>
              Guide
            </button>
            <button
              className={`toolbar-btn overlay-btn ${showOverlay ? 'active' : ''}`}
              onClick={() => setShowOverlay(!showOverlay)}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                {showOverlay ? (
                  <>
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                    <circle cx="12" cy="12" r="3" />
                  </>
                ) : (
                  <>
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
                    <line x1="1" y1="1" x2="23" y2="23" />
                  </>
                )}
              </svg>
              Labels
            </button>
          </div>

          <GraphPanel showLabels={showOverlay} />

          {/* Welcome / Guide overlay */}
          {showWelcome && nodes.length > 0 && (
            <div className="graph-welcome">
              <button className="welcome-close" onClick={() => setShowWelcome(false)}>&times;</button>
              <div className="welcome-title">SAP Order-to-Cash Flow</div>
              <div className="welcome-flow">
                {FLOW_STEPS.map((step, i) => (
                  <div key={step.label} className="flow-step">
                    <div className="flow-dot" style={{ background: step.color }} />
                    <span>{step.label}</span>
                    {i < FLOW_STEPS.length - 1 && (
                      <svg className="flow-arrow" width="16" height="12" viewBox="0 0 16 12">
                        <path d="M0 6h12M10 2l4 4-4 4" stroke="#94a3b8" strokeWidth="1.5" fill="none" />
                      </svg>
                    )}
                  </div>
                ))}
              </div>
              <div className="welcome-hint">
                Click any node to inspect it. Ask questions in the chat to highlight relevant entities.
              </div>
            </div>
          )}

          {/* Legend */}
          {nodes.length > 0 && (
            <div className="graph-legend">
              <div className="legend-title">Entity Types</div>
              <div className="legend-items">
                {LEGEND_ITEMS.map((item) => (
                  <div key={item.type} className="legend-item">
                    <div className="legend-dot" style={{ background: item.color }} />
                    {item.label}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Stats */}
          {nodes.length > 0 && (
            <div className="graph-stats">
              <span><span className="stat-num">{nodes.length}</span> nodes{totalNodes > nodes.length ? ` / ${totalNodes}` : ''}</span>
              <span><span className="stat-num">{edges.length}</span> edges</span>
            </div>
          )}
        </div>
        <ChatPanel />
      </main>
    </div>
  );
}

export default App;
