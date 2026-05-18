import type { ChatResponse } from '../types';

const configuredBase = (import.meta.env.VITE_API_URL ?? '').replace(/\/+$/, '');

function getCandidateBases(): string[] {
  if (!import.meta.env.DEV) {
    return [configuredBase];
  }

  const bases = [
    configuredBase,
    '',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'http://0.0.0.0:8000',
  ];

  return [...new Set(bases)];
}

function buildUrl(base: string): string {
  return base ? `${base}/chat` : '/chat';
}

export async function sendQuestion(question: string): Promise<ChatResponse> {
  const body = JSON.stringify({ question });
  let lastNetworkError: unknown = null;

  for (const base of getCandidateBases()) {
    try {
      const response = await fetch(buildUrl(base), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
      });

      if (response.ok) {
        return response.json() as Promise<ChatResponse>;
      }

      const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
      const detail = err.detail ?? `HTTP ${response.status}`;

      // If Vite proxy is unavailable in dev, try direct backend URLs.
      if (import.meta.env.DEV && base === '' && response.status === 404) {
        continue;
      }

      throw new Error(detail);
    } catch (error) {
      if (error instanceof TypeError) {
        lastNetworkError = error;
        continue;
      }
      throw error;
    }
  }

  if (lastNetworkError instanceof Error) {
    throw new Error(
      `Unable to reach backend. Start FastAPI on port 8000 or set VITE_API_URL. Details: ${lastNetworkError.message}`,
    );
  }

  throw new Error('Unable to reach backend. Start FastAPI on port 8000 or set VITE_API_URL.');
}
