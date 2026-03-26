import { useCallback } from 'react';
import { useStore } from '../store';

const API_BASE = import.meta.env.VITE_API_URL || '';

export function useChat() {
  const { addMessage, updateMessage, setChatLoading, setHighlightedNodeIds, sessionId } =
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

      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60000); // 60s timeout

      try {
        const res = await fetch(`${API_BASE}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query, sessionId }),
          signal: controller.signal,
        });

        clearTimeout(timeout);

        if (!res.ok) {
          throw new Error(`Server error (${res.status}). Please try again.`);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error('No response body');

        const decoder = new TextDecoder();
        let buffer = '';
        let sql: string | undefined;
        let answer = '';
        let streamedText = '';
        let nodeIds: string[] = [];
        let resultCount = 0;
        let hasError = false;
        let streamMsgId = 'assistant-' + Date.now();
        let isStreaming = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // SSE events are separated by double newlines
          const events = buffer.split('\n\n');
          buffer = events.pop() || ''; // Keep incomplete event in buffer

          for (const eventBlock of events) {
            if (!eventBlock.trim()) continue;

            const lines = eventBlock.split('\n');
            let eventType = 'message';
            let eventData = '';

            for (const line of lines) {
              if (line.startsWith('event: ')) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith('data: ')) {
                eventData = line.slice(6);
              }
            }

            if (!eventData) continue;

            try {
              const data = JSON.parse(eventData);

              switch (eventType) {
                case 'sql':
                  if (data.sql) sql = data.sql;
                  break;
                case 'token':
                  // Progressive streaming — update message in place
                  if (data.token) {
                    streamedText += data.token;
                    if (!isStreaming) {
                      isStreaming = true;
                      addMessage({
                        id: streamMsgId,
                        role: 'assistant',
                        content: streamedText,
                        sql,
                      });
                    } else {
                      updateMessage(streamMsgId, streamedText);
                    }
                  }
                  break;
                case 'result':
                  if (data.answer) answer = data.answer;
                  if (data.nodeIds) nodeIds = data.nodeIds;
                  if (data.resultCount !== undefined) resultCount = data.resultCount;
                  if (data.sql && !sql) sql = data.sql;
                  break;
                case 'error':
                  if (data.message) {
                    answer = data.message;
                    hasError = true;
                  }
                  break;
                case 'done':
                  break;
              }
            } catch {
              // ignore parse errors for malformed events
            }
          }
        }

        if (answer) {
          if (isStreaming) {
            // Update the streaming message with final data (nodeIds, resultCount)
            updateMessage(streamMsgId, answer, {
              sql: hasError ? undefined : sql,
              nodeIds: hasError ? undefined : nodeIds,
              resultCount: hasError ? undefined : resultCount,
            });
          } else {
            addMessage({
              id: streamMsgId,
              role: hasError ? 'error' : 'assistant',
              content: answer,
              sql: hasError ? undefined : sql,
              nodeIds: hasError ? undefined : nodeIds,
              resultCount: hasError ? undefined : resultCount,
            });
          }

          if (!hasError && nodeIds.length > 0) {
            setHighlightedNodeIds(nodeIds);
          }
        }
      } catch (err) {
        clearTimeout(timeout);
        const message =
          err instanceof DOMException && err.name === 'AbortError'
            ? 'Request timed out. The AI service may be slow — please try again.'
            : err instanceof Error
              ? err.message
              : 'Something went wrong. Please try again.';

        addMessage({
          id: 'error-' + Date.now(),
          role: 'error',
          content: message,
        });
      } finally {
        setChatLoading(false);
      }
    },
    [addMessage, updateMessage, setChatLoading, setHighlightedNodeIds, sessionId]
  );

  return { sendMessage };
}
