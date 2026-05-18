import { useState } from 'react';
import type { ToolCallRecord } from '../../types';

interface TracePanelProps {
  trace: ToolCallRecord[];
}

function formatResult(result: string): string {
  try {
    return JSON.stringify(JSON.parse(result), null, 2);
  } catch {
    return result;
  }
}

function formatArgs(args: ToolCallRecord['args']): string {
  if (typeof args === 'string') {
    return args;
  }

  try {
    return JSON.stringify(args, null, 2);
  } catch {
    return String(args);
  }
}

async function writeToClipboard(value: string): Promise<void> {
  if (typeof navigator !== 'undefined' && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
  }
}

function previewText(value: string): string {
  return value.slice(0, 80) + (value.length > 80 ? '...' : '');
}

function rowState(result: string): 'error' | 'warning' | 'ok' {
  if (result.startsWith('REFUSED:') || result.includes('ERROR:')) {
    return 'error';
  }

  if (result.includes('WARNING:')) {
    return 'warning';
  }

  return 'ok';
}

export function TracePanel({ trace }: TracePanelProps) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  async function copy(key: string, value: string) {
    try {
      await writeToClipboard(value);
      setCopiedKey(key);
      window.setTimeout(() => setCopiedKey((current) => (current === key ? null : current)), 1200);
    } catch {
      setCopiedKey(null);
    }
  }

  return (
    <div id="tool-trace" className="space-y-2">
      {trace.map((tc, index) => {
        const isOpen = openIdx === index;
        const state = rowState(tc.result);

        return (
          <div
            key={`${tc.tool}-${index}`}
            className={`overflow-hidden rounded-xl border ${
              state === 'error'
                ? 'border-red-500/35 bg-red-500/10'
                : state === 'warning'
                  ? 'border-amber-500/30 bg-amber-500/10'
                  : 'border-slate-700 bg-slate-900/45'
            }`}
          >
            <button
              id={`tool-trace-${index}-toggle`}
              type="button"
              onClick={() => setOpenIdx((current) => (current === index ? null : index))}
              className="flex w-full items-center gap-3 px-4 py-2.5 text-left"
            >
              <span className="rounded-md border border-slate-700/80 bg-slate-950/70 px-2 py-0.5 font-mono text-[11px] text-slate-300">
                {tc.tool}
              </span>
              <span className="rounded border border-slate-700 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-400">
                {state}
              </span>
              <span className="flex-1 truncate text-xs text-slate-500">{previewText(tc.result)}</span>
              <span className={`text-xs text-slate-400 transition ${isOpen ? 'rotate-180' : ''}`}>v</span>
            </button>

            {isOpen && (
              <div className="divide-y divide-slate-700/60 border-t border-slate-700/80">
                <section className="space-y-1 px-4 py-3">
                  <div className="flex items-center justify-between">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Arguments</p>
                    <button
                      type="button"
                      onClick={() => copy(`args-${index}`, formatArgs(tc.args))}
                      className="text-[11px] text-cyan-400 hover:text-cyan-300"
                    >
                      {copiedKey === `args-${index}` ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                  <pre className="overflow-x-auto rounded-lg bg-slate-950/70 p-2.5 text-xs leading-relaxed text-slate-200">
                    {formatArgs(tc.args)}
                  </pre>
                </section>

                <section className="space-y-1 px-4 py-3">
                  <div className="flex items-center justify-between">
                    <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Result</p>
                    <button
                      type="button"
                      onClick={() => copy(`result-${index}`, formatResult(tc.result))}
                      className="text-[11px] text-cyan-400 hover:text-cyan-300"
                    >
                      {copiedKey === `result-${index}` ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                  <pre
                    className={`max-h-72 overflow-x-auto rounded-lg p-2.5 text-xs leading-relaxed ${
                      state === 'error' ? 'bg-red-500/15 text-red-300' : 'bg-slate-950/70 text-emerald-300'
                    }`}
                  >
                    {formatResult(tc.result)}
                  </pre>
                </section>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
