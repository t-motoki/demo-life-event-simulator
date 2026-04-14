import { describe, it, expect, vi, afterEach } from 'vitest';
import { postSimulate } from '../../api/client';
import type { SimulateRequestBody, SimulateError } from '../../api/types';

const MOCK_REQUEST: SimulateRequestBody = {
  client: {
    age: 35,
    annual_income: 5000000,
    income_model: 'flat',
    raise_rate: 0,
    retirement_age: 65,
    post_retirement_income: 0,
    pension_start_age: 65,
    pension_annual: 1200000,
  },
  spouse: null,
  savings_initial: 3000000,
  end_age: 90,
  start_year: 2026,
  monthly_expenses: { living: 200000, insurance: 10000, other: 0 },
  events: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('postSimulate', () => {
  it('HTTP 200 のとき CashFlowRowResponse[] を返す', async () => {
    const mockRows = [
      {
        year: 2026,
        age_client: 35,
        age_spouse: null,
        income_total: 5000000,
        expense_total: 2520000,
        loan_deduction: 0,
        net: 2480000,
        savings: 5480000,
        events_label: '',
      },
    ];
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: true, status: 200, json: async () => mockRows }),
    );
    const result = await postSimulate(MOCK_REQUEST);
    expect(result).toEqual(mockRows);
  });

  it('HTTP 422 (detail が文字列) のとき validation エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: '年齢が不正です' }),
      }),
    );
    await expect(postSimulate(MOCK_REQUEST)).rejects.toMatchObject({
      kind: 'validation',
      detail: '年齢が不正です',
    } satisfies SimulateError);
  });

  it('HTTP 422 (detail が配列) のとき汎用メッセージの validation エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: [{ msg: 'value error' }] }),
      }),
    );
    await expect(postSimulate(MOCK_REQUEST)).rejects.toMatchObject({
      kind: 'validation',
      detail: '入力内容に誤りがあります',
    } satisfies SimulateError);
  });

  it('HTTP 500 のとき server エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) }),
    );
    await expect(postSimulate(MOCK_REQUEST)).rejects.toMatchObject({
      kind: 'server',
    } satisfies SimulateError);
  });

  it('fetch が throw するとき network エラーを throw する', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValueOnce(new Error('Failed to fetch')));
    await expect(postSimulate(MOCK_REQUEST)).rejects.toMatchObject({
      kind: 'network',
    } satisfies SimulateError);
  });

  it('タイムアウトのとき timeout エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementationOnce((_url: string, options?: RequestInit) => {
        return new Promise((_resolve, reject) => {
          if (options?.signal) {
            options.signal.addEventListener('abort', () => {
              const err = new DOMException('The operation was aborted.', 'AbortError');
              reject(err);
            });
          }
        });
      }),
    );
    // タイムアウトを 50ms に短縮してテストを高速化
    const fastTimeout = postSimulate(MOCK_REQUEST, 50);
    await expect(fastTimeout).rejects.toMatchObject({ kind: 'timeout' } satisfies SimulateError);
  });
});
