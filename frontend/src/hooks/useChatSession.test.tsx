import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { useChatSession } from './useChatSession';
import { sendQuestion } from '../api/chat';

vi.mock('../api/chat', () => ({
  sendQuestion: vi.fn(),
}));

describe('useChatSession', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('submits a question and appends user and agent messages', async () => {
    vi.mocked(sendQuestion).mockResolvedValue({
      answer: 'Top seller is Wireless Mouse.',
      tool_calls: [],
      warnings: [],
      elapsed_ms: 42,
    });

    const { result } = renderHook(() => useChatSession());

    act(() => {
      result.current.setInput('What is top seller?');
    });

    await act(async () => {
      await result.current.submitQuestion();
    });

    expect(sendQuestion).toHaveBeenCalledWith('What is top seller?');
    expect(result.current.messages).toHaveLength(2);
    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[1].role).toBe('agent');
    expect(result.current.input).toBe('');
    expect(result.current.error).toBeNull();
  });

  it('shows error and retryLast retries the failed request without duplicating user message', async () => {
    vi.mocked(sendQuestion)
      .mockRejectedValueOnce(new Error('Network down'))
      .mockResolvedValueOnce({
        answer: 'Recovered response',
        tool_calls: [],
        warnings: [],
        elapsed_ms: 99,
      });

    const { result } = renderHook(() => useChatSession());

    act(() => {
      result.current.setInput('retry me');
    });

    await act(async () => {
      await result.current.submitQuestion();
    });

    expect(result.current.error).toBe('Network down');
    expect(result.current.messages).toHaveLength(1);

    await act(async () => {
      await result.current.retryLast();
    });

    await waitFor(() => {
      expect(result.current.error).toBeNull();
      expect(result.current.messages).toHaveLength(2);
    });

    expect(result.current.messages[0].role).toBe('user');
    expect(result.current.messages[1].content).toBe('Recovered response');
  });
});
