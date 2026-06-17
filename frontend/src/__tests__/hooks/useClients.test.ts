import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { useClients } from '../../hooks/useClients';
import * as api from '../../api/client';
import type { ClientListItem, ClientResponse, SimulateRequestBody } from '../../api/types';

vi.mock('../../api/client');

const MOCK_SCENARIO: SimulateRequestBody = {
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

const MOCK_CLIENTS: ClientListItem[] = [
  { id: 1, name: '田中', updated_at: '2026-06-17T00:00:00Z' },
  { id: 2, name: '佐藤', updated_at: '2026-06-17T01:00:00Z' },
];

const MOCK_DETAIL: ClientResponse = {
  id: 1,
  name: '田中',
  scenario: MOCK_SCENARIO,
  created_at: '2026-06-17T00:00:00Z',
  updated_at: '2026-06-17T00:00:00Z',
};

beforeEach(() => {
  vi.resetAllMocks();
  // デフォルト: getClients は空配列を返す
  vi.mocked(api.getClients).mockResolvedValue([]);
});

describe('useClients - 初期化', () => {
  it('マウント時に getClients を呼んで一覧を取得する', async () => {
    vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);

    const { result } = renderHook(() => useClients());

    await waitFor(() => {
      expect(result.current.loading).toBe(false);
    });
    expect(result.current.clients).toHaveLength(2);
    expect(api.getClients).toHaveBeenCalledOnce();
  });

  it('マウント時に getClients が失敗したら error にメッセージが入る', async () => {
    vi.mocked(api.getClients).mockRejectedValue({ kind: 'network' });

    const { result } = renderHook(() => useClients());

    await waitFor(() => {
      expect(result.current.error).not.toBeNull();
    });
    expect(result.current.clients).toEqual([]);
  });

  it('API 通信中は loading が true になる', async () => {
    // getClients を遅延させる
    let resolveGetClients: (value: ClientListItem[]) => void;
    vi.mocked(api.getClients).mockImplementation(
      () => new Promise((resolve) => { resolveGetClients = resolve; }),
    );

    const { result } = renderHook(() => useClients());

    // 通信中は loading が true
    expect(result.current.loading).toBe(true);

    // 解決すると loading が false
    await act(async () => {
      resolveGetClients!(MOCK_CLIENTS);
    });
    expect(result.current.loading).toBe(false);
  });
});

describe('useClients - selectClient', () => {
  it('selectClient で selectedId が更新される', async () => {
    vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);
    vi.mocked(api.getClient).mockResolvedValue(MOCK_DETAIL);

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.selectClient(1);
    });
    expect(result.current.selectedId).toBe(1);
  });

  it('selectClient が ClientDetail を返す', async () => {
    vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);
    vi.mocked(api.getClient).mockResolvedValue(MOCK_DETAIL);

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    let detail: ClientResponse | undefined;
    await act(async () => {
      detail = await result.current.selectClient(1);
    });
    expect(detail).toHaveProperty('scenario');
    expect(detail!.name).toBe('田中');
  });

  it('selectClient で getClient が失敗したら error にメッセージが入り selectedId は変わらない', async () => {
    vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);
    vi.mocked(api.getClient).mockRejectedValue({ kind: 'not_found' });

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.selectedId).toBeNull();

    await act(async () => {
      try {
        await result.current.selectClient(999);
      } catch {
        // エラーは hook 内部で処理される
      }
    });
    expect(result.current.error).not.toBeNull();
    expect(result.current.selectedId).toBeNull();
  });
});

describe('useClients - saveClient', () => {
  it('saveClient で postClient を呼び、一覧が再取得される', async () => {
    vi.mocked(api.getClients)
      .mockResolvedValueOnce(MOCK_CLIENTS)
      .mockResolvedValueOnce([...MOCK_CLIENTS, { id: 3, name: '山田', updated_at: '2026-06-17T02:00:00Z' }]);
    vi.mocked(api.postClient).mockResolvedValue({
      id: 3,
      name: '山田',
      scenario: MOCK_SCENARIO,
      created_at: '2026-06-17T02:00:00Z',
      updated_at: '2026-06-17T02:00:00Z',
    });

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.saveClient('山田', MOCK_SCENARIO);
    });

    expect(api.postClient).toHaveBeenCalledOnce();
    expect(result.current.clients).toHaveLength(3);
  });

  it('saveClient 後に selectedId が新規クライアントの id になる', async () => {
    vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);
    vi.mocked(api.postClient).mockResolvedValue({
      id: 3,
      name: '山田',
      scenario: MOCK_SCENARIO,
      created_at: '2026-06-17T02:00:00Z',
      updated_at: '2026-06-17T02:00:00Z',
    });

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.saveClient('山田', MOCK_SCENARIO);
    });
    expect(result.current.selectedId).toBe(3);
  });

  it('saveClient で postClient が失敗したら error にメッセージが入る', async () => {
    vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);
    vi.mocked(api.postClient).mockRejectedValue({ kind: 'validation', detail: '名前は必須です' });

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.saveClient('', MOCK_SCENARIO);
    });
    expect(result.current.error).not.toBeNull();
  });
});

describe('useClients - overwriteClient', () => {
  it('overwriteClient で putClient を selectedId で呼ぶ', async () => {
    vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);
    vi.mocked(api.getClient).mockResolvedValue(MOCK_DETAIL);
    vi.mocked(api.putClient).mockResolvedValue(MOCK_DETAIL);

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    // まず選択する
    await act(async () => {
      await result.current.selectClient(1);
    });

    await act(async () => {
      await result.current.overwriteClient(MOCK_SCENARIO);
    });
    expect(api.putClient).toHaveBeenCalledWith(1, expect.objectContaining({ scenario: MOCK_SCENARIO }));
  });

  it('overwriteClient 後に一覧が再取得される', async () => {
    vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);
    vi.mocked(api.getClient).mockResolvedValue(MOCK_DETAIL);
    vi.mocked(api.putClient).mockResolvedValue(MOCK_DETAIL);

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.selectClient(1);
    });

    const getClientsCallCount = vi.mocked(api.getClients).mock.calls.length;

    await act(async () => {
      await result.current.overwriteClient(MOCK_SCENARIO);
    });

    // 一覧再取得が呼ばれている
    expect(vi.mocked(api.getClients).mock.calls.length).toBeGreaterThan(getClientsCallCount);
  });

  it('selectedId が null のとき overwriteClient を呼ぶとエラーになる', async () => {
    vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    expect(result.current.selectedId).toBeNull();

    await act(async () => {
      await result.current.overwriteClient(MOCK_SCENARIO);
    });
    expect(result.current.error).not.toBeNull();
    expect(api.putClient).not.toHaveBeenCalled();
  });
});

describe('useClients - deleteClient', () => {
  it('deleteClient で一覧が再取得される', async () => {
    vi.mocked(api.getClients)
      .mockResolvedValueOnce(MOCK_CLIENTS)
      .mockResolvedValueOnce([MOCK_CLIENTS[1]]);
    vi.mocked(api.deleteClient).mockResolvedValue(undefined);

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.removeClient(1);
    });
    expect(api.deleteClient).toHaveBeenCalledWith(1);
    expect(result.current.clients).toHaveLength(1);
  });

  it('削除したクライアントが selectedId と一致する場合、selectedId が null になる', async () => {
    vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);
    vi.mocked(api.getClient).mockResolvedValue(MOCK_DETAIL);
    vi.mocked(api.deleteClient).mockResolvedValue(undefined);

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.selectClient(1);
    });
    expect(result.current.selectedId).toBe(1);

    await act(async () => {
      await result.current.removeClient(1);
    });
    expect(result.current.selectedId).toBeNull();
  });

  it('削除したクライアントが selectedId と一致しない場合、selectedId は変わらない', async () => {
    vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);
    vi.mocked(api.getClient).mockResolvedValue({ ...MOCK_DETAIL, id: 2, name: '佐藤' });
    vi.mocked(api.deleteClient).mockResolvedValue(undefined);

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.selectClient(2);
    });
    expect(result.current.selectedId).toBe(2);

    await act(async () => {
      await result.current.removeClient(1);
    });
    expect(result.current.selectedId).toBe(2);
  });

  it('deleteClient が失敗したら error にメッセージが入る', async () => {
    vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);
    vi.mocked(api.deleteClient).mockRejectedValue({ kind: 'server' });

    const { result } = renderHook(() => useClients());
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => {
      await result.current.removeClient(1);
    });
    expect(result.current.error).not.toBeNull();
  });
});
