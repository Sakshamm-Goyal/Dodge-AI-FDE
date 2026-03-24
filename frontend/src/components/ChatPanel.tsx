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
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Auto-resize textarea
  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }
  }, [input]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const query = input.trim();
    if (!query || chatLoading) return;
    setInput('');
    sendMessage(query);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <div>
          <h2>Chat with Graph</h2>
          <span className="chat-subtitle">Order to Cash</span>
        </div>
      </div>

      <div className="chat-messages">
        {messages.map((msg) => (
          <div key={msg.id} className={`chat-message ${msg.role}`}>
            {msg.role === 'assistant' && (
              <div className="msg-avatar-row">
                <div className="bot-avatar">
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                  </svg>
                </div>
                <div className="bot-name">
                  <strong>Dodge AI</strong>
                  <span>Graph Agent</span>
                </div>
              </div>
            )}
            {msg.role === 'user' && (
              <div className="msg-avatar-row user-row">
                <span className="user-label">You</span>
                <div className="user-avatar">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                    <circle cx="12" cy="7" r="4" />
                  </svg>
                </div>
              </div>
            )}
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
                <div className="highlight-info" onClick={clearHighlights}>
                  <span className="highlight-dot" />
                  {msg.nodeIds.length} node{msg.nodeIds.length !== 1 ? 's' : ''} highlighted
                  {msg.resultCount ? ` \u00b7 ${msg.resultCount} results` : ''}
                </div>
              )}
            </div>
          </div>
        ))}
        {chatLoading && (
          <div className="chat-message assistant">
            <div className="msg-avatar-row">
              <div className="bot-avatar">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2">
                  <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                </svg>
              </div>
              <div className="bot-name">
                <strong>Dodge AI</strong>
                <span>Graph Agent</span>
              </div>
            </div>
            <div className="message-content">
              <div className="typing-indicator">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-area">
        <div className="input-status">
          <span className="status-dot" />
          <span>Dodge AI is awaiting instructions</span>
        </div>
        <form className="chat-input-form" onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Analyze anything"
            disabled={chatLoading}
            rows={1}
          />
          <button type="submit" disabled={chatLoading || !input.trim()}>
            Send
          </button>
        </form>
      </div>
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
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points={expanded ? "18 15 12 9 6 15" : "6 9 12 15 18 9"} />
        </svg>
        {expanded ? 'Hide' : 'View'} SQL Query
      </button>
      {expanded && (
        <pre className="sql-code">{sql}</pre>
      )}
    </div>
  );
}
