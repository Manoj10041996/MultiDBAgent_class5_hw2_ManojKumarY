import { useState, useRef, useEffect } from 'react';
import type { Message } from './types';
import { sendQuestion } from './api/chat';
import { ToolTrace } from './components/ToolTrace';
import { WarningBanner } from './components/WarningBanner';

// ── Suggested questions ────────────────────────────────────────────────────
const SUGGESTIONS = [
  'What are the top 5 selling products this month?',
  'What are customers complaining about most this week?',
  'What is our return policy for damaged goods?',
  'Which customers have placed the most orders?',
  'Show me all 1-star reviews for the Wireless Mouse',
];

// ── Tool badge colours ─────────────────────────────────────────────────────
const TOOL_COLORS: Record<string, string> = {
  sql_query:       'bg-blue-500/20 text-blue-300 border-blue-500/30',
  mongo_query:     'bg-green-500/20 text-green-300 border-green-500/30',
  handbook_search: 'bg-purple-500/20 text-purple-300 border-purple-500/30',
};

function toolColor(tool: string): string {
  return TOOL_COLORS[tool] ?? 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

// ── App ────────────────────────────────────────────────────────────────────
export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  async function handleSubmit(question: string) {
    if (!question.trim() || isLoading) return;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: question.trim(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);
    setError(null);

    try {
      const data = await sendQuestion(question.trim());
      const agentMsg: Message = {
        id: crypto.randomUUID(),
        role: 'agent',
        content: data.answer,
        trace: data.tool_calls,
        warnings: data.warnings,
        elapsed_ms: data.elapsed_ms,
      };
      setMessages(prev => [...prev, agentMsg]);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(input);
    }
  }

  return (
    <div className="flex flex-col h-screen bg-[#0f1117]">
      {/* ── Header ── */}
      <header className="flex-none border-b border-slate-800 px-6 py-4 flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-bold text-sm">
            SP
          </div>
          <div>
            <h1 className="text-slate-100 font-semibold text-sm leading-none">StockPulse Intelligence</h1>
            <p className="text-slate-500 text-xs mt-0.5">Store Operations Agent</p>
          </div>
        </div>
        <div className="ml-auto flex gap-1.5">
          {['SQL', 'NoSQL', 'RAG'].map((label, i) => (
            <span
              key={label}
              className={`text-xs px-2 py-0.5 rounded-full border font-medium ${
                i === 0 ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' :
                i === 1 ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                'bg-purple-500/10 text-purple-400 border-purple-500/20'
              }`}
            >
              {label}
            </span>
          ))}
        </div>
      </header>

      {/* ── Messages ── */}
      <main className="flex-1 overflow-y-auto px-4 py-6 space-y-6">
        {messages.length === 0 && !isLoading && (
          <div className="max-w-2xl mx-auto mt-12 text-center">
            <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-2xl mx-auto mb-4">
              🧠
            </div>
            <h2 className="text-slate-200 font-semibold text-xl mb-2">Ask anything about your store</h2>
            <p className="text-slate-500 text-sm mb-8">
              I query your Postgres database, MongoDB, and policy documents to give you grounded answers with full receipts.
            </p>
            <div className="grid gap-2">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  id={`suggestion-${s.slice(0, 20).replace(/\s+/g, '-').toLowerCase()}`}
                  onClick={() => handleSubmit(s)}
                  className="text-left px-4 py-3 rounded-xl border border-slate-700 hover:border-slate-500 bg-slate-800/50 hover:bg-slate-800 text-slate-300 text-sm transition-all duration-150"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map(msg => (
          <div key={msg.id} className={`max-w-3xl mx-auto ${msg.role === 'user' ? 'flex justify-end' : ''}`}>
            {msg.role === 'user' ? (
              <div className="bg-blue-600/20 border border-blue-500/30 rounded-2xl rounded-tr-sm px-4 py-3 max-w-xl">
                <p className="text-slate-200 text-sm leading-relaxed">{msg.content}</p>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Agent avatar + answer */}
                <div className="flex gap-3 items-start">
                  <div className="flex-none w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold mt-0.5">
                    AI
                  </div>
                  <div className="flex-1">
                    <p className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                    {msg.elapsed_ms !== undefined && (
                      <p className="text-slate-600 text-xs mt-2">{msg.elapsed_ms.toLocaleString()} ms</p>
                    )}
                  </div>
                </div>

                {/* Tool call trace */}
                {msg.trace && msg.trace.length > 0 && (
                  <div className="ml-10">
                    <div className="flex gap-1.5 mb-2">
                      {msg.trace.map((tc, i) => (
                        <span key={i} className={`text-xs px-2 py-0.5 rounded-full border font-mono font-medium ${toolColor(tc.tool)}`}>
                          {tc.tool}
                        </span>
                      ))}
                    </div>
                    <ToolTrace trace={msg.trace} />
                  </div>
                )}

                {/* Warnings */}
                {msg.warnings && msg.warnings.length > 0 && (
                  <div className="ml-10">
                    <WarningBanner warnings={msg.warnings} />
                  </div>
                )}
              </div>
            )}
          </div>
        ))}

        {/* Loading indicator */}
        {isLoading && (
          <div className="max-w-3xl mx-auto flex gap-3 items-start">
            <div className="flex-none w-7 h-7 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white text-xs font-bold mt-0.5">
              AI
            </div>
            <div className="flex items-center gap-1.5 py-3">
              {[0, 1, 2].map(i => (
                <div
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-slate-500 animate-bounce"
                  style={{ animationDelay: `${i * 150}ms` }}
                />
              ))}
              <span className="text-slate-500 text-xs ml-2">Thinking…</span>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="max-w-3xl mx-auto">
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl px-4 py-3 text-red-400 text-sm">
              ⚠️ {error}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </main>

      {/* ── Input bar ── */}
      <footer className="flex-none border-t border-slate-800 px-4 py-4">
        <div className="max-w-3xl mx-auto flex gap-3 items-end">
          <div className="flex-1 bg-slate-800 border border-slate-700 rounded-2xl overflow-hidden focus-within:border-blue-500/50 focus-within:ring-1 focus-within:ring-blue-500/20 transition-all">
            <textarea
              ref={inputRef}
              id="chat-input"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your store — sales, tickets, policies…"
              rows={1}
              className="w-full bg-transparent px-4 py-3 text-slate-200 text-sm placeholder-slate-500 resize-none outline-none leading-relaxed"
              style={{ maxHeight: '120px' }}
              disabled={isLoading}
            />
          </div>
          <button
            id="submit-btn"
            onClick={() => handleSubmit(input)}
            disabled={isLoading || !input.trim()}
            className="flex-none w-10 h-10 rounded-xl bg-blue-600 hover:bg-blue-500 disabled:bg-slate-700 disabled:cursor-not-allowed text-white flex items-center justify-center transition-all duration-150"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
              <path d="M3.105 2.289a.75.75 0 00-.826.95l1.414 4.925A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.896 28.896 0 0015.293-7.154.75.75 0 000-1.115A28.897 28.897 0 003.105 2.289z" />
            </svg>
          </button>
        </div>
        <p className="text-center text-slate-700 text-xs mt-2">
          Press Enter to send · Shift+Enter for new line
        </p>
      </footer>
    </div>
  );
}
