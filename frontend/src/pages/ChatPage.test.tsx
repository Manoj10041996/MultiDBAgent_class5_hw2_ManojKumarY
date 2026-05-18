import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useChatSession } from '../hooks/useChatSession';
import { ChatPage } from './ChatPage';

vi.mock('../hooks/useChatSession', () => ({
  useChatSession: vi.fn(),
}));

type ChatSessionState = ReturnType<typeof useChatSession>;

function createSession(overrides: Partial<ChatSessionState> = {}): ChatSessionState {
  return {
    messages: [],
    input: '',
    isLoading: false,
    error: null,
    submitQuestion: vi.fn(),
    retryLast: vi.fn(),
    setInput: vi.fn(),
    clearChat: vi.fn(),
    ...overrides,
  };
}

describe('ChatPage wiring', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.defineProperty(window.HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
      writable: true,
    });
  });

  it('suggestion click triggers submit flow', async () => {
    const user = userEvent.setup();
    const submitQuestion = vi.fn();
    vi.mocked(useChatSession).mockReturnValue(createSession({ submitQuestion }));

    render(<ChatPage />);

    await user.click(screen.getByRole('button', { name: 'What are the top 5 selling products this month?' }));

    expect(submitQuestion).toHaveBeenCalledTimes(1);
    expect(submitQuestion).toHaveBeenCalledWith('What are the top 5 selling products this month?');
  });

  it('retry action invokes retry path after error state', async () => {
    const user = userEvent.setup();
    const retryLast = vi.fn();
    vi.mocked(useChatSession).mockReturnValue(createSession({ error: 'Network down', retryLast }));

    render(<ChatPage />);

    await user.click(screen.getByRole('button', { name: 'Retry' }));

    expect(retryLast).toHaveBeenCalledTimes(1);
  });
});
