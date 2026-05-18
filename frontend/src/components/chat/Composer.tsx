import { useEffect, useRef } from 'react';

interface ComposerProps {
  value: string;
  isLoading: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
}

const MAX_HEIGHT = 180;

export function Composer({ value, isLoading, onChange, onSubmit }: ComposerProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const element = inputRef.current;
    if (!element) {
      return;
    }

    element.style.height = 'auto';
    const nextHeight = Math.min(element.scrollHeight, MAX_HEIGHT);
    element.style.height = `${Math.max(nextHeight, 44)}px`;
  }, [value]);

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  }

  return (
    <div className="rounded-2xl border border-slate-700/80 bg-slate-900/75 p-2 shadow-[0_10px_28px_rgba(2,6,23,0.55)] focus-within:border-cyan-500/60 focus-within:ring-1 focus-within:ring-cyan-500/30">
      <div className="flex items-end gap-2">
        <textarea
          ref={inputRef}
          id="chat-input"
          aria-label="Ask a question"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask about sales, customers, policies, or ticket trends..."
          rows={1}
          className="w-full resize-none bg-transparent px-2 py-2 text-sm leading-relaxed text-slate-200 outline-none placeholder:text-slate-500"
          disabled={isLoading}
          style={{ maxHeight: `${MAX_HEIGHT}px` }}
        />

        <button
          id="submit-btn"
          type="button"
          onClick={onSubmit}
          disabled={isLoading || !value.trim()}
          className="grid h-10 w-10 place-items-center rounded-xl bg-cyan-600 text-white transition hover:bg-cyan-500 disabled:cursor-not-allowed disabled:bg-slate-700"
          aria-label="Send message"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="h-4 w-4">
            <path d="M3.105 2.289a.75.75 0 00-.826.95l1.414 4.925A1.5 1.5 0 005.135 9.25h6.115a.75.75 0 010 1.5H5.135a1.5 1.5 0 00-1.442 1.086l-1.414 4.926a.75.75 0 00.826.95 28.896 28.896 0 0015.293-7.154.75.75 0 000-1.115A28.897 28.897 0 003.105 2.289z" />
          </svg>
        </button>
      </div>

      <p className="px-2 pt-1 text-[11px] text-slate-500">Enter to send, Shift+Enter for a new line</p>
    </div>
  );
}
