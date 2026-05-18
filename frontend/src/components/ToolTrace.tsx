import { useState } from 'react';
import type { ToolCallRecord } from '../types';

interface Props {
  trace: ToolCallRecord[];
}

const TOOL_ICONS: Record<string, string> = {
  sql_query: '🗄️',
  mongo_query: '📄',
  handbook_search: '📖',
};

export function ToolTrace({ trace }: Props) {
  const [openIdx, setOpenIdx] = useState<number | null>(null);

  function toggleIdx(i: number) {
    setOpenIdx(prev => (prev === i ? null : i));
  }

  function formatResult(result: string): string {
    try {
      return JSON.stringify(JSON.parse(result), null, 2);
    } catch {
      return result;
    }
  }

  function formatArgs(args: ToolCallRecord['args']): string {
    if (typeof args === 'string') return args;
    try {
      return JSON.stringify(args, null, 2);
    } catch {
      return String(args);
    }
  }

  return (
    <div id="tool-trace" className="space-y-2">
      {trace.map((tc, i) => {
        const isOpen = openIdx === i;
        const icon = TOOL_ICONS[tc.tool] ?? '🔧';
        const resultPreview = tc.result.slice(0, 80) + (tc.result.length > 80 ? '…' : '');
        const isError = tc.result.startsWith('REFUSED:') ||
                        tc.result.includes('ERROR:');

        return (
          <div
            key={i}
            className={`rounded-xl border overflow-hidden transition-all duration-200 ${
              isError
                ? 'border-red-500/30 bg-red-500/5'
                : 'border-slate-700 bg-slate-800/50'
            }`}
          >
            {/* Header row — always visible */}
            <button
              id={`tool-trace-${i}-toggle`}
              onClick={() => toggleIdx(i)}
              className="w-full flex items-center gap-3 px-4 py-2.5 text-left hover:bg-slate-700/30 transition-colors"
            >
              <span className="text-sm">{icon}</span>
              <span className="font-mono text-xs font-medium text-slate-300">{tc.tool}</span>
              <span className="flex-1 text-slate-500 text-xs truncate">{resultPreview}</span>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
                className={`w-3.5 h-3.5 text-slate-500 flex-none transition-transform duration-200 ${isOpen ? 'rotate-180' : ''}`}
              >
                <path
                  fillRule="evenodd"
                  d="M5.22 8.22a.75.75 0 011.06 0L10 11.94l3.72-3.72a.75.75 0 111.06 1.06l-4.25 4.25a.75.75 0 01-1.06 0L5.22 9.28a.75.75 0 010-1.06z"
                  clipRule="evenodd"
                />
              </svg>
            </button>

            {/* Expanded detail */}
            {isOpen && (
              <div className="border-t border-slate-700 divide-y divide-slate-700/50">
                {/* Args */}
                <div className="px-4 py-3">
                  <p className="text-slate-500 text-xs font-medium mb-1.5 uppercase tracking-wider">Arguments</p>
                  <pre className="text-xs text-slate-300 overflow-x-auto whitespace-pre-wrap break-words leading-relaxed font-mono bg-slate-900/50 rounded-lg p-3">
                    {formatArgs(tc.args)}
                  </pre>
                </div>

                {/* Result */}
                <div className="px-4 py-3">
                  <p className="text-slate-500 text-xs font-medium mb-1.5 uppercase tracking-wider">Result</p>
                  <pre
                    className={`text-xs overflow-x-auto whitespace-pre-wrap break-words leading-relaxed font-mono rounded-lg p-3 ${
                      isError
                        ? 'text-red-400 bg-red-500/5'
                        : 'text-green-300 bg-slate-900/50'
                    }`}
                    style={{ maxHeight: '300px' }}
                  >
                    {formatResult(tc.result)}
                  </pre>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
