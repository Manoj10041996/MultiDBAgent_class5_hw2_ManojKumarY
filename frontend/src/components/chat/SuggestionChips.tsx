interface SuggestionChipsProps {
  suggestions: string[];
  disabled?: boolean;
  onSelect: (question: string) => void;
}

function toSuggestionId(value: string): string {
  return `suggestion-${value.slice(0, 20).replace(/\s+/g, '-').toLowerCase()}`;
}

export function SuggestionChips({ suggestions, disabled, onSelect }: SuggestionChipsProps) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {suggestions.map((suggestion) => (
        <button
          key={suggestion}
          id={toSuggestionId(suggestion)}
          onClick={() => onSelect(suggestion)}
          disabled={disabled}
          className="rounded-xl border border-slate-700/90 bg-slate-900/55 px-4 py-3 text-left text-sm text-slate-300 transition duration-150 hover:-translate-y-0.5 hover:border-cyan-500/40 hover:bg-slate-900 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {suggestion}
        </button>
      ))}
    </div>
  );
}
