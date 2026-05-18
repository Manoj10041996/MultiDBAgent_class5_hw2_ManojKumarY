import type { Message } from '../../types';
import { WarningBanner } from '../WarningBanner';
import { TracePanel } from './TracePanel';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
}

const TOOL_COLORS: Record<string, string> = {
  sql_query: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  mongo_query: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  handbook_search: 'bg-indigo-500/20 text-indigo-300 border-indigo-500/30',
};

function toolColor(tool: string): string {
  return TOOL_COLORS[tool] ?? 'bg-slate-500/20 text-slate-300 border-slate-500/30';
}

async function copyText(value: string): Promise<void> {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
  }
}

export function MessageList({ messages, isLoading, error, onRetry }: MessageListProps) {
  return (
    <div className="space-y-5 pb-6">
      {messages.map((message) => (
        <article
          key={message.id}
          className={`animate-message-in ${message.role === 'user' ? 'flex justify-end' : ''}`}
        >
          {message.role === 'user' ? (
            <div className="max-w-[90%] rounded-2xl rounded-tr-sm border border-cyan-500/30 bg-cyan-500/15 px-4 py-3 sm:max-w-xl">
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-100">{message.content}</p>
            </div>
          ) : (
            <div className="w-full space-y-3">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 grid h-8 w-8 flex-none place-items-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 text-xs font-bold text-white">
                  AI
                </div>
                <div className="min-w-0 flex-1 rounded-2xl border border-slate-700/80 bg-slate-900/60 px-4 py-3">
                  <div className="flex items-start gap-2">
                    <p className="flex-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-100">{message.content}</p>
                    <button
                      type="button"
                      onClick={() => {
                        void copyText(message.content);
                      }}
                      className="rounded-md border border-slate-700 px-2 py-0.5 text-[11px] text-slate-400 transition hover:border-cyan-500/50 hover:text-cyan-300"
                    >
                      Copy
                    </button>
                  </div>
                  {typeof message.elapsed_ms === 'number' && (
                    <p className="mt-2 text-[11px] text-slate-500">{message.elapsed_ms.toLocaleString()} ms</p>
                  )}
                </div>
              </div>

              {message.trace && message.trace.length > 0 && (
                <div className="ml-11 space-y-2">
                  <div className="flex flex-wrap gap-1.5">
                    {message.trace.map((toolCall, index) => (
                      <span
                        key={`${toolCall.tool}-${index}`}
                        className={`rounded-full border px-2 py-0.5 font-mono text-[11px] font-medium ${toolColor(toolCall.tool)}`}
                      >
                        {toolCall.tool}
                      </span>
                    ))}
                  </div>
                  <TracePanel trace={message.trace} />
                </div>
              )}

              {message.warnings && message.warnings.length > 0 && (
                <div className="ml-11">
                  <WarningBanner warnings={message.warnings} />
                </div>
              )}
            </div>
          )}
        </article>
      ))}

      {isLoading && (
        <div className="flex items-center gap-3 rounded-2xl border border-slate-700/80 bg-slate-900/60 px-4 py-3 text-slate-300 animate-message-in">
          <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 text-xs font-bold text-white">
            AI
          </div>
          <div className="flex items-center gap-2">
            {[0, 1, 2].map((dot) => (
              <span
                key={dot}
                className="h-1.5 w-1.5 animate-pulse rounded-full bg-cyan-300/85"
                style={{ animationDelay: `${dot * 120}ms` }}
              />
            ))}
            <p className="text-xs text-slate-400">Thinking through data sources...</p>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/35 bg-red-500/10 px-4 py-3 text-sm text-red-300 animate-message-in">
          <div className="flex flex-wrap items-center gap-3">
            <p className="flex-1">Request failed: {error}</p>
            <button
              type="button"
              onClick={onRetry}
              className="rounded-lg border border-red-400/40 bg-red-500/10 px-3 py-1 text-xs font-medium text-red-200 transition hover:bg-red-500/20"
            >
              Retry
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
