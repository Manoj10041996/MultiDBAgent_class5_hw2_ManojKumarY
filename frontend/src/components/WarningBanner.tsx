interface Props {
  warnings: string[];
}

export function WarningBanner({ warnings }: Props) {
  if (!warnings.length) return null;

  return (
    <div id="warning-banner" className="space-y-1.5">
      {warnings.map((w, i) => (
        <div
          key={i}
          className="flex gap-2 items-start px-3 py-2 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs"
        >
          <span className="flex-none mt-0.5">!</span>
          <span className="leading-relaxed">{w}</span>
        </div>
      ))}
    </div>
  );
}
