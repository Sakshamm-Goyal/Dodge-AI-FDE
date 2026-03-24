import GraphPanel from './components/GraphPanel';
import ChatPanel from './components/ChatPanel';
import './App.css';

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>SAP O2C Graph Explorer</h1>
        <span className="subtitle">Order-to-Cash Process Visualization</span>
      </header>
      <main className="app-main">
        <GraphPanel />
        <ChatPanel />
      </main>
    </div>
  );
}

export default App;
