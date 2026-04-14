import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import { SimulateButton } from '../../components/SimulateButton';

describe('SimulateButton', () => {
  it('loading が false のときボタンが有効', () => {
    render(<SimulateButton loading={false} onClick={vi.fn()} />);
    expect(screen.getByRole('button')).not.toBeDisabled();
  });

  it('loading が true のときボタンが無効化される', () => {
    render(<SimulateButton loading={true} onClick={vi.fn()} />);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('loading が false のときクリックでコールバックが呼ばれる', async () => {
    const onClick = vi.fn();
    render(<SimulateButton loading={false} onClick={onClick} />);
    await userEvent.click(screen.getByRole('button'));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it('loading が true のときボタンが disabled なのでクリックイベントは発火しない', () => {
    const onClick = vi.fn();
    render(<SimulateButton loading={true} onClick={onClick} />);
    // disabled ボタンは pointer-events:none のため userEvent.click ではなく
    // DOM の disabled 状態を確認し、onClick が結線されていても発火しないことを保証する
    const button = screen.getByRole('button');
    expect(button).toBeDisabled();
    // disabled 属性があれば onClick は発火しない（ブラウザの仕様）
    button.click(); // DOM レベルの click イベント（disabled では無視される）
    expect(onClick).not.toHaveBeenCalled();
  });
});
