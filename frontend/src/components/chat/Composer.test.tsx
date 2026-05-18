import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { Composer } from './Composer';

describe('Composer', () => {
  it('submits on Enter and does not submit on Shift+Enter', async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const onChange = vi.fn();

    render(
      <Composer
        value="hello"
        onChange={onChange}
        onSubmit={onSubmit}
        isLoading={false}
      />,
    );

    const input = screen.getByLabelText('Ask a question');

    await user.click(input);
    await user.keyboard('{Shift>}{Enter}{/Shift}');
    expect(onSubmit).not.toHaveBeenCalled();

    await user.keyboard('{Enter}');
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });
});
