import type { PropsWithChildren } from 'react';

export function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <div className="pointer-events-none fixed inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.16),_transparent_40%),radial-gradient(circle_at_bottom_right,_rgba(34,197,94,0.14),_transparent_35%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(120deg,_rgba(15,23,42,0.82),_rgba(2,6,23,0.92))]" />
      </div>

      <div className="relative mx-auto flex min-h-screen w-full max-w-6xl flex-col px-3 sm:px-4 lg:px-6">
        <header className="sticky top-0 z-10 border-b border-slate-800/80 bg-slate-950/75 px-2 py-4 backdrop-blur">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 text-sm font-bold text-white shadow-[0_0_24px_rgba(56,189,248,0.35)]">
              SP
            </div>
            <div>
              <h1 className="text-sm font-semibold tracking-wide text-slate-100 sm:text-base">StockPulse Intelligence</h1>
              <p className="text-xs text-slate-400">Store Operations Agent</p>
            </div>
            <div className="ml-auto flex gap-1.5">
              {['SQL', 'NoSQL', 'RAG'].map((label) => (
                <span
                  key={label}
                  className="rounded-full border border-slate-700 bg-slate-900/80 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-slate-300 sm:text-xs"
                >
                  {label}
                </span>
              ))}
            </div>
          </div>
        </header>

        {children}
      </div>
    </div>
  );
}
