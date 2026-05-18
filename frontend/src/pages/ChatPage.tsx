import { useEffect, useRef } from 'react';
import { Composer } from '../components/chat/Composer';
import { MessageList } from '../components/chat/MessageList';
import { SuggestionChips } from '../components/chat/SuggestionChips';
import { useChatSession } from '../hooks/useChatSession';

const SUGGESTIONS = [
  'What are the top 5 selling products this month?',
  'What are customers complaining about most this week?',
  'What is our return policy for damaged goods?',
  'Which customers have placed the most orders?',
  'Show me all 1-star reviews for the Wireless Mouse',
];

export function ChatPage() {
  const { messages, input, isLoading, error, submitQuestion, retryLast, setInput, clearChat } = useChatSession();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading, error]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <main className="min-h-0 flex-1 overflow-y-auto px-1 pb-4 pt-5 sm:px-2">
        <div className="mx-auto w-full max-w-4xl space-y-5">
          {messages.length === 0 && !isLoading && (
            <section className="animate-message-in rounded-3xl border border-slate-800/90 bg-slate-950/55 px-5 py-8 text-center shadow-[0_16px_40px_rgba(2,6,23,0.55)]">
              <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-600 text-2xl text-white">
                S
              </div>
              <h2 className="text-xl font-semibold text-slate-100">Ask anything about your store</h2>
              <p className="mx-auto mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">
                Get grounded answers from Postgres, MongoDB, and policy documents with full tool traces and warnings.
              </p>
              <div className="mt-6">
                <SuggestionChips
                  suggestions={SUGGESTIONS}
                  disabled={isLoading}
                  onSelect={(question) => {
                    void submitQuestion(question);
                  }}
                />
              </div>
            </section>
          )}

          <MessageList
            messages={messages}
            isLoading={isLoading}
            error={error}
            onRetry={() => {
              void retryLast();
            }}
          />

          <div ref={bottomRef} />
        </div>
      </main>

      <footer className="border-t border-slate-800/80 bg-slate-950/70 px-1 py-3 backdrop-blur sm:px-2 sm:py-4">
        <div className="mx-auto flex w-full max-w-4xl items-end gap-2 sm:gap-3">
          <div className="flex-1">
            <Composer
              value={input}
              isLoading={isLoading}
              onChange={setInput}
              onSubmit={() => {
                void submitQuestion();
              }}
            />
          </div>

          <button
            type="button"
            onClick={clearChat}
            disabled={isLoading || messages.length === 0}
            className="mb-6 rounded-xl border border-slate-700 bg-slate-900/70 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-slate-400 transition hover:border-cyan-500/40 hover:text-cyan-300 disabled:cursor-not-allowed disabled:opacity-50 sm:mb-7"
          >
            Clear
          </button>
        </div>
      </footer>
    </div>
  );
}
