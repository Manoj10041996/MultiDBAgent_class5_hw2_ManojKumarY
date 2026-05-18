import { useCallback, useRef, useState } from 'react';
import { sendQuestion } from '../api/chat';
import type { Message } from '../types';

function buildId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }

  return `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

interface SubmitOptions {
  skipUserMessage?: boolean;
}

export function useChatSession() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastQuestionRef = useRef<string | null>(null);

  const submitQuestion = useCallback(
    async (questionOverride?: string, options?: SubmitOptions) => {
      if (isLoading) {
        return;
      }

      const question = (questionOverride ?? input).trim();
      if (!question) {
        return;
      }

      lastQuestionRef.current = question;
      if (!options?.skipUserMessage) {
        setMessages((prev) => [
          ...prev,
          {
            id: buildId(),
            role: 'user',
            content: question,
          },
        ]);
        setInput('');
      }

      setError(null);
      setIsLoading(true);

      try {
        const data = await sendQuestion(question);
        setMessages((prev) => [
          ...prev,
          {
            id: buildId(),
            role: 'agent',
            content: data.answer,
            trace: data.tool_calls,
            warnings: data.warnings,
            elapsed_ms: data.elapsed_ms,
          },
        ]);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Something went wrong');
      } finally {
        setIsLoading(false);
      }
    },
    [input, isLoading],
  );

  const retryLast = useCallback(async () => {
    if (!lastQuestionRef.current) {
      return;
    }

    await submitQuestion(lastQuestionRef.current, { skipUserMessage: true });
  }, [submitQuestion]);

  const clearChat = useCallback(() => {
    setMessages([]);
    setInput('');
    setError(null);
    setIsLoading(false);
    lastQuestionRef.current = null;
  }, []);

  return {
    messages,
    input,
    isLoading,
    error,
    submitQuestion,
    retryLast,
    setInput,
    clearChat,
  };
}
