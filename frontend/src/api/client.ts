// すべての fetch 呼び出しをここに集約する
// コンポーネントや hooks が直接 fetch を呼ばない

import type { SimulateRequestBody, CashFlowRowResponse, SimulateError } from './types';

// Electron ビルド時は VITE_API_URL を .env.production で上書きする
// ?? を使う理由: || は空文字を falsy 扱いするため
const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

export async function postSimulate(
  body: SimulateRequestBody,
  timeoutMs = 30000,
): Promise<CashFlowRowResponse[]> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${BASE_URL}/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!response.ok) {
      const json = await response.json().catch(() => ({}));
      if (response.status === 422) {
        const detail = json.detail;
        // validator.py 由来: detail は文字列、Pydantic 由来: detail は配列
        const message =
          typeof detail === 'string' ? detail : '入力内容に誤りがあります';
        const err: SimulateError = { kind: 'validation', detail: message };
        throw err;
      }
      const err: SimulateError = { kind: 'server' };
      throw err;
    }
    return response.json();
  } catch (e) {
    clearTimeout(timer);
    // AbortController が発火した場合は timeout エラーに変換する
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw { kind: 'timeout' } as SimulateError;
    }
    // すでに SimulateError として throw されたものはそのまま再 throw
    if (e && typeof e === 'object' && 'kind' in e) throw e;
    // fetch 自体が失敗（接続なし）は network エラー
    throw { kind: 'network' } as SimulateError;
  }
}

export async function getHealth(timeoutMs = 5000): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BASE_URL}/health`, { signal: controller.signal });
    clearTimeout(timer);
    if (!response.ok) {
      throw { kind: 'server' } as SimulateError;
    }
  } catch (e) {
    clearTimeout(timer);
    throw e;
  }
}
