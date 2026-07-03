'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api } from '@/lib/api';
import { fmtMoney } from '@/lib/format';
import type { ChatMessage } from '@/lib/types';

interface ChatPanelProps {
  collapsed: boolean;
  onToggle: () => void;
  onActions: () => void; // called after a response so portfolio/watchlist can refresh
}

let idSeq = 0;
const nextId = () => `msg-${Date.now()}-${idSeq++}`;

function ActionChips({ msg }: { msg: ChatMessage }) {
  const hasAny = (msg.trades?.length ?? 0) + (msg.watchlist_changes?.length ?? 0) + (msg.errors?.length ?? 0) > 0;
  if (!hasAny) return null;
  return (
    <div className="mt-1.5 flex flex-wrap gap-1" data-testid="chat-actions">
      {msg.trades?.map((t, i) => (
        <span
          key={`t${i}`}
          className={`rounded border px-1.5 py-0.5 text-[10px] ${
            t.side === 'buy' ? 'border-up/40 text-up' : 'border-down/40 text-down'
          }`}
        >
          {t.side.toUpperCase()} {t.quantity} {t.ticker} @ {fmtMoney(t.price)}
        </span>
      ))}
      {msg.watchlist_changes?.map((w, i) => (
        <span key={`w${i}`} className="rounded border border-brand/40 px-1.5 py-0.5 text-[10px] text-brand">
          {w.action === 'add' ? '+ ' : '− '}
          {w.ticker}
        </span>
      ))}
      {msg.errors?.map((err, i) => (
        <span key={`e${i}`} className="rounded border border-accent/50 px-1.5 py-0.5 text-[10px] text-accent">
          ⚠ {err}
        </span>
      ))}
    </div>
  );
}

export function ChatPanel({ collapsed, onToggle, onActions }: ChatPanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        "Hi, I'm FinAlly — your AI trading assistant. Ask me to analyze your portfolio, suggest trades, or manage your watchlist.",
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, loading]);

  async function send(e: FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    const userMsg: ChatMessage = { id: nextId(), role: 'user', content: text };
    setMessages((m) => [...m, userMsg]);
    setInput('');
    setLoading(true);
    try {
      const res = await api.chat(text);
      setMessages((m) => [
        ...m,
        {
          id: nextId(),
          role: 'assistant',
          content: res.message,
          trades: res.trades,
          watchlist_changes: res.watchlist_changes,
          errors: res.errors,
        },
      ]);
      if ((res.trades?.length ?? 0) > 0 || (res.watchlist_changes?.length ?? 0) > 0) {
        onActions();
      }
    } catch (e2) {
      setMessages((m) => [
        ...m,
        {
          id: nextId(),
          role: 'assistant',
          content: `Sorry — I couldn't reach the assistant. ${e2 instanceof Error ? e2.message : ''}`.trim(),
          errors: ['request_failed'],
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onToggle}
        aria-label="Open AI assistant"
        className="flex w-10 shrink-0 flex-col items-center gap-2 border-l border-border-subtle bg-bg-panel py-3 text-brand hover:bg-bg-hover"
      >
        <span className="text-lg">✦</span>
        <span className="[writing-mode:vertical-rl] text-[11px] uppercase tracking-widest text-flat">AI Assistant</span>
      </button>
    );
  }

  return (
    <aside
      className="flex w-80 shrink-0 flex-col border-l border-border-subtle bg-bg-panel"
      aria-label="AI assistant"
      data-testid="chat-panel"
    >
      <header className="flex shrink-0 items-center justify-between border-b border-border-subtle px-3 py-2">
        <div className="flex items-center gap-1.5">
          <span className="text-brand">✦</span>
          <h2 className="text-[11px] font-semibold uppercase tracking-wider text-gray-200">FinAlly Assistant</h2>
        </div>
        <button
          type="button"
          onClick={onToggle}
          aria-label="Collapse AI assistant"
          className="rounded px-1 text-flat hover:text-gray-200"
        >
          ›
        </button>
      </header>

      <div ref={scrollRef} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {messages.map((m) => (
          <div key={m.id} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              data-testid={`chat-msg-${m.role}`}
              className={`max-w-[85%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
                m.role === 'user'
                  ? 'bg-brand/20 text-gray-100'
                  : 'border border-border-subtle bg-bg-raised text-gray-200'
              }`}
            >
              <p className="whitespace-pre-wrap">{m.content}</p>
              <ActionChips msg={m} />
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start" data-testid="chat-loading">
            <div className="flex items-center gap-1 rounded-lg border border-border-subtle bg-bg-raised px-3 py-2">
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-flat [animation-delay:-0.2s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-flat [animation-delay:-0.1s]" />
              <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-flat" />
            </div>
          </div>
        )}
      </div>

      <form onSubmit={send} className="flex shrink-0 items-center gap-2 border-t border-border-subtle p-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask FinAlly…"
          aria-label="Message FinAlly"
          disabled={loading}
          className="min-w-0 flex-1 rounded border border-border-subtle bg-bg-base px-2 py-1.5 text-xs text-gray-100 outline-none focus:border-brand disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="rounded bg-submit px-3 py-1.5 text-xs font-semibold text-white hover:brightness-110 disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </aside>
  );
}
