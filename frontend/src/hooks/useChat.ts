import { useCallback } from 'react';
import { useStore } from '../store';

const API_BASE = import.meta.env.VITE_API_URL || '';

export function useChat() {
  const { addMessage, setChatLoading, setHighlightedNodeIds, sessionId } =
    useStore();

  const sendMessage = useCallback(
    async (query: string) => {
      const userMsg = {
        id: 'user-' + Date.now(),
        role: 'user' as const,
        content: query,
      };
      addMessage(userMsg);
      setChatLoading(true);

      try {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, sessionId }),
        });

        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let buffer = '';
        let sql: string | undefined;
        let answer = '';
        let nodeIds: string[] = [];
        let resultCount = 0;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              const eventType = line.slice(7).trim();
              // Next data line
              const dataIdx = lines.indexOf(line) + 1;
              if (dataIdx < lines.length && lines[dataIdx].startsWith('data: ')) {
                // handled below
              }
              void eventType;
            } else if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                if (data.sql) sql = data.sql;
                if (data.answer) answer = data.answer;
                if (data.nodeIds) nodeIds = data.nodeIds;
                if (data.resultCount !== undefined)
                  resultCount = data.resultCount;
                if (data.message) answer = data.message; // error events
              } catch {
                // ignore parse errors
              }
            }
          }
        }

        if (answer) {
          addMessage({
            id: 'assistant-' + Date.now(),
            role: 'assistant',
            content: answer,
            sql,
            nodeIds,
            resultCount,
          });

          if (nodeIds.length > 0) {
            setHighlightedNodeIds(nodeIds);
          }
        }
      } catch (err) {
        addMessage({
          id: 'error-' + Date.now(),
          role: 'error',
          content:
            err instanceof Error
              ? err.message
              : 'Something went wrong. Please try again.',
        });
      } finally {
        setChatLoading(false);
      }
    },
    [addMessage, setChatLoading, setHighlightedNodeIds, sessionId]
  );

  return { sendMessage };
}
