import { describe, it, expect, vi, afterEach } from 'vitest';
import {
  getClients,
  getClient,
  postClient,
  putClient,
  deleteClient,
} from '../../api/client';
import type { ClientError, SaveClientBody, SimulateRequestBody } from '../../api/types';

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

const MOCK_SAVE_BODY: SaveClientBody = {
  name: '田中',
  scenario: MOCK_SCENARIO,
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('getClients', () => {
  it('HTTP 200 のとき ClientSummary[] を返す', async () => {
    const mockList = [{ id: 1, name: '田中', updated_at: '2026-06-17T00:00:00Z' }];
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: true, status: 200, json: async () => mockList }),
    );
    const result = await getClients();
    expect(result).toEqual(mockList);
  });

  it('HTTP 500 のとき server エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) }),
    );
    await expect(getClients()).rejects.toMatchObject({
      kind: 'server',
    } satisfies ClientError);
  });

  it('fetch が throw するとき network エラーを throw する', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValueOnce(new Error('Failed to fetch')));
    await expect(getClients()).rejects.toMatchObject({
      kind: 'network',
    } satisfies ClientError);
  });
});

describe('getClient', () => {
  it('HTTP 200 のとき ClientDetail を返す', async () => {
    const mockDetail = {
      id: 1,
      name: '田中',
      scenario: MOCK_SCENARIO,
      created_at: '2026-06-17T00:00:00Z',
      updated_at: '2026-06-17T00:00:00Z',
    };
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: true, status: 200, json: async () => mockDetail }),
    );
    const result = await getClient(1);
    expect(result).toEqual(mockDetail);
  });

  it('HTTP 404 のとき not_found エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({}) }),
    );
    await expect(getClient(999)).rejects.toMatchObject({
      kind: 'not_found',
    } satisfies ClientError);
  });

  it('HTTP 500 のとき server エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) }),
    );
    await expect(getClient(1)).rejects.toMatchObject({
      kind: 'server',
    } satisfies ClientError);
  });
});

describe('postClient', () => {
  it('HTTP 201 のとき ClientDetail を返す', async () => {
    const mockCreated = {
      id: 1,
      name: '田中',
      scenario: MOCK_SCENARIO,
      created_at: '2026-06-17T00:00:00Z',
      updated_at: '2026-06-17T00:00:00Z',
    };
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: true, status: 201, json: async () => mockCreated }),
    );
    const result = await postClient(MOCK_SAVE_BODY);
    expect(result).toEqual(mockCreated);
  });

  it('リクエストボディに name と scenario が含まれる', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 201,
      json: async () => ({ id: 1, name: '田中', scenario: MOCK_SCENARIO, created_at: '', updated_at: '' }),
    });
    vi.stubGlobal('fetch', mockFetch);
    await postClient(MOCK_SAVE_BODY);
    const callArgs = mockFetch.mock.calls[0];
    const body = JSON.parse(callArgs[1].body);
    expect(body).toHaveProperty('name', '田中');
    expect(body).toHaveProperty('scenario');
  });

  it('HTTP 422 のとき validation エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({
        ok: false,
        status: 422,
        json: async () => ({ detail: '名前は必須です' }),
      }),
    );
    await expect(postClient(MOCK_SAVE_BODY)).rejects.toMatchObject({
      kind: 'validation',
      detail: '名前は必須です',
    } satisfies ClientError);
  });

  it('HTTP 500 のとき server エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) }),
    );
    await expect(postClient(MOCK_SAVE_BODY)).rejects.toMatchObject({
      kind: 'server',
    } satisfies ClientError);
  });
});

describe('putClient', () => {
  it('HTTP 200 のとき ClientDetail を返す', async () => {
    const mockUpdated = {
      id: 42,
      name: '田中',
      scenario: MOCK_SCENARIO,
      created_at: '2026-06-17T00:00:00Z',
      updated_at: '2026-06-17T01:00:00Z',
    };
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: true, status: 200, json: async () => mockUpdated }),
    );
    const result = await putClient(42, MOCK_SAVE_BODY);
    expect(result).toEqual(mockUpdated);
  });

  it('URL に id が含まれる', async () => {
    const mockFetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ id: 42, name: '田中', scenario: MOCK_SCENARIO, created_at: '', updated_at: '' }),
    });
    vi.stubGlobal('fetch', mockFetch);
    await putClient(42, MOCK_SAVE_BODY);
    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toMatch(/\/clients\/42$/);
  });

  it('HTTP 404 のとき not_found エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({}) }),
    );
    await expect(putClient(42, MOCK_SAVE_BODY)).rejects.toMatchObject({
      kind: 'not_found',
    } satisfies ClientError);
  });

  it('HTTP 500 のとき server エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) }),
    );
    await expect(putClient(42, MOCK_SAVE_BODY)).rejects.toMatchObject({
      kind: 'server',
    } satisfies ClientError);
  });
});

describe('deleteClient', () => {
  it('HTTP 204 のとき正常終了する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: true, status: 204 }),
    );
    await expect(deleteClient(1)).resolves.toBeUndefined();
  });

  it('HTTP 404 のとき not_found エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: false, status: 404, json: async () => ({}) }),
    );
    await expect(deleteClient(999)).rejects.toMatchObject({
      kind: 'not_found',
    } satisfies ClientError);
  });

  it('HTTP 500 のとき server エラーを throw する', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) }),
    );
    await expect(deleteClient(1)).rejects.toMatchObject({
      kind: 'server',
    } satisfies ClientError);
  });
});
