import { useState } from 'react';
import GraphPanel from './components/GraphPanel';
import ChatPanel from './components/ChatPanel';
import './App.css';

function App() {
  const [showOverlay, setShowOverlay] = useState(true);

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
      </header>
      <main className="app-main">
        <div className="graph-wrapper">
          <div className="graph-toolbar">
            <button className="toolbar-btn" onClick={() => {}}>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="4 14 10 14 10 20" />
                <polyline points="20 10 14 10 14 4" />
                <line x1="14" y1="10" x2="21" y2="3" />
                <line x1="3" y1="21" x2="10" y2="14" />
              </svg>
              Minimize
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
              {showOverlay ? 'Hide' : 'Show'} Granular Overlay
            </button>
          </div>
          <GraphPanel showLabels={showOverlay} />
        </div>
        <ChatPanel />
      </main>
    </div>
  );
}

export default App;
