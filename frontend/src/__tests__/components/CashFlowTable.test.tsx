import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { CashFlowTable } from '../../components/ResultSection/CashFlowTable';
import type { CashFlowRowResponse } from '../../api/types';

const baseRow: CashFlowRowResponse = {
  year: 2026,
  age_client: 35,
  age_spouse: null,
  income_total: 5000000,
  expense_total: 2520000,
  loan_deduction: 0,
  net: 2480000,
  savings: 5480000,
  events_label: '',
};

describe('CashFlowTable', () => {
  it('貯蓄残高がマイナスの行は data-negative-savings 属性が付く', () => {
    const rows = [{ ...baseRow, savings: -100000 }];
    const { container } = render(<CashFlowTable rows={rows} hasSpouse={false} />);
    const trs = container.querySelectorAll('tbody tr');
    expect(trs[0].getAttribute('data-negative-savings')).toBe('true');
  });

  it('貯蓄残高がプラスの行は data-negative-savings 属性がない', () => {
    const rows = [{ ...baseRow, savings: 5000000 }];
    const { container } = render(<CashFlowTable rows={rows} hasSpouse={false} />);
    const trs = container.querySelectorAll('tbody tr');
    expect(trs[0].getAttribute('data-negative-savings')).toBeNull();
  });

  it('hasSpouse が false のとき配偶者年齢列が存在しない', () => {
    render(<CashFlowTable rows={[baseRow]} hasSpouse={false} />);
    expect(screen.queryByText('配偶者年齢')).not.toBeInTheDocument();
  });

  it('hasSpouse が true のとき配偶者年齢列が存在する', () => {
    const rows = [{ ...baseRow, age_spouse: 33 }];
    render(<CashFlowTable rows={rows} hasSpouse={true} />);
    expect(screen.getByText('配偶者年齢')).toBeInTheDocument();
  });

  it('net < 0 の行の年間収支セルに data-negative-net 属性が付く', () => {
    const rows = [{ ...baseRow, net: -500000 }];
    const { container } = render(<CashFlowTable rows={rows} hasSpouse={false} />);
    const netCells = container.querySelectorAll('[data-negative-net="true"]');
    expect(netCells.length).toBe(1);
  });

  it('同一年に複数イベントがある場合、" / " 区切りで表示する', () => {
    const rows = [{ ...baseRow, events_label: '結婚 / 住宅購入' }];
    render(<CashFlowTable rows={rows} hasSpouse={false} />);
    expect(screen.getByText('結婚 / 住宅購入')).toBeInTheDocument();
  });
});
