'use client';

/**
 * ChatPanel — collapsible AI copilot sidebar (UI-08).
 *
 * Keeps its own in-memory session message history (POST /api/chat does not
 * return prior history — see backend `app/chat.py`). Each assistant turn's
 * `actions` (auto-executed trades/watchlist changes) render inline as
 * confirmation chips: green for `status: 'ok'`, red for `status: 'error'`.
 *
 * When a turn executed at least one action, `onActions()` is called so the
 * parent can re-fetch `/api/portfolio` and `/api/watchlist` (T-04-09
 * threat model: all message/action text is untrusted LLM/user output and
 * MUST be rendered as plain React text nodes — never via raw-HTML
 * injection APIs).
 */

import { useEffect, useRef, useState } from 'react';

import * as api from '../lib/api';
import type { ChatAction } from '../lib/types';

export interface ChatPanelProps {
  /** Called after a turn whose response included one or more executed actions. */
  onActions: () => void;
}

interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  /** Present only on assistant messages that executed actions. */
  actions?: ChatAction[];
  /** True for a locally-synthesized error bubble (transport/API failure). */
  isError?: boolean;
}

let nextMessageId = 0;

function actionLabel(action: ChatAction): string {
  return action.detail;
}

function ActionChip({ action }: { action: ChatAction }) {
  const ok = action.status === 'ok';
  return (
    <div
      className={`mt-1 rounded border px-2 py-1 text-xs ${
        ok
          ? 'border-up/40 bg-up/10 text-up'
          : 'border-down/40 bg-down/10 text-down'
      }`}
    >
      {actionLabel(action)}
    </div>
  );
}

function LoadingDots() {
  return (
    <div className="flex items-center gap-1 rounded bg-base px-3 py-2 text-gray-400" aria-live="polite">
      <span className="animate-pulse">.</span>
      <span className="animate-pulse [animation-delay:150ms]">.</span>
      <span className="animate-pulse [animation-delay:300ms]">.</span>
      <span className="sr-only">Waiting for response</span>
    </div>
  );
}

export default function ChatPanel({ onActions }: ChatPanelProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, loading]);

  async function handleSend() {
    const text = input.trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { id: nextMessageId++, role: 'user', content: text }]);
    setInput('');
    setLoading(true);

    try {
      const response = await api.sendChat(text);
      setMessages((prev) => [
        ...prev,
        {
          id: nextMessageId++,
          role: 'assistant',
          content: response.message,
          actions: response.actions,
        },
      ]);
      if (response.actions.length > 0) {
        onActions();
      }
    } catch (err) {
      const detail = err instanceof Error ? err.message : 'Chat request failed';
      setMessages((prev) => [
        ...prev,
        { id: nextMessageId++, role: 'assistant', content: detail, isError: true },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Enter') {
      event.preventDefault();
      void handleSend();
    }
  }

  if (collapsed) {
    return (
      <div className="flex h-full items-start justify-end">
        <button
          type="button"
          onClick={() => setCollapsed(false)}
          className="rounded border border-border-muted bg-panel px-3 py-2 text-xs font-semibold text-accent hover:border-accent"
          aria-label="Expand AI chat panel"
        >
          AI Chat
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col rounded border border-border-muted bg-panel">
      <div className="flex items-center justify-between border-b border-border-muted px-3 py-2">
        <span className="text-sm font-semibold text-gray-200">AI Chat</span>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          className="rounded px-2 py-1 text-xs text-gray-400 hover:text-accent"
          aria-label="Collapse AI chat panel"
        >
          Collapse
        </button>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {messages.length === 0 && !loading ? (
          <p className="text-xs text-gray-500">
            Ask about your portfolio, request analysis, or tell the assistant to trade.
          </p>
        ) : null}

        {messages.map((message) => (
          <div key={message.id} className={message.role === 'user' ? 'text-right' : 'text-left'}>
            <div
              className={`inline-block max-w-full rounded px-3 py-2 text-sm ${
                message.role === 'user'
                  ? 'bg-blue/20 text-gray-100'
                  : message.isError
                    ? 'bg-down/10 text-down'
                    : 'bg-base text-gray-200'
              }`}
            >
              {message.content}
            </div>
            {message.actions && message.actions.length > 0 ? (
              <div className="mt-1 flex flex-col items-start gap-1">
                {message.actions.map((action, index) => (
                  <ActionChip key={`${message.id}-${index}`} action={action} />
                ))}
              </div>
            ) : null}
          </div>
        ))}

        {loading ? <LoadingDots /> : null}
      </div>

      <div className="flex items-center gap-2 border-t border-border-muted px-3 py-2">
        <input
          type="text"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask FinAlly..."
          disabled={loading}
          className="flex-1 rounded border border-border-muted bg-base px-2 py-1.5 text-sm text-gray-100 placeholder:text-gray-600 focus:border-blue focus:outline-none disabled:opacity-50"
        />
        <button
          type="button"
          onClick={() => void handleSend()}
          disabled={loading || !input.trim()}
          className="rounded bg-purple px-3 py-1.5 text-sm font-semibold text-white hover:bg-purple/90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
