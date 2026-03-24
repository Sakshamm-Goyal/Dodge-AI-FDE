import { useState, useRef, useEffect } from 'react';
import { useStore } from '../store';
import { useChat } from '../hooks/useChat';

function renderMarkdown(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br/>');
}

export default function ChatPanel() {
  const { messages, chatLoading, clearHighlights } = useStore();
  const { sendMessage } = useChat();
  const [input, setInput] = useState('');
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const query = input.trim();
    if (!query || chatLoading) return;
    setInput('');
    sendMessage(query);
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <h2>AI Assistant</h2>
        <button className="clear-btn" onClick={clearHighlights} title="Clear highlights">
          Clear
        </button>
      </div>

      <div className="chat-messages">
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-message ${msg.role}`}>
            <div className="message-content">
              {msg.role === 'error' ? (
                <div className="error-msg">{msg.content}</div>
              ) : (
                <div
                  className="msg-text"
                  dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }}
                />
              )}
              {msg.sql && <SqlBlock sql={msg.sql} />}
              {msg.nodeIds && msg.nodeIds.length > 0 && (
                <div className="highlight-info">
                  Highlighted {msg.nodeIds.length} node{msg.nodeIds.length !== 1 ? 's' : ''} in graph
                  {msg.resultCount ? ` (${msg.resultCount} results)` : ''}
                </div>
              )}
            </div>
          </div>
        ))}
        {chatLoading && (
          <div className="chat-message assistant">
            <div className="message-content">
              <div className="typing-indicator">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form className="chat-input-form" onSubmit={handleSubmit}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about the O2C data..."
          disabled={chatLoading}
        />
        <button type="submit" disabled={chatLoading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

function SqlBlock({ sql }: { sql: string }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="sql-block">
      <button
        className="sql-toggle"
        onClick={() => setExpanded(!expanded)}
      >
        {expanded ? 'Hide' : 'Show'} SQL
      </button>
      {expanded && (
        <pre className="sql-code">{sql}</pre>
      )}
    </div>
  );
}
