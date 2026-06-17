// すべての fetch 呼び出しをここに集約する
// コンポーネントや hooks が直接 fetch を呼ばない

import type {
  SimulateRequestBody,
  CashFlowRowResponse,
  SimulateError,
  DownloadPdfRequestBody,
  GenerateCommentRequestBody,
  GenerateCommentResponse,
  DownloadError,
  ClientListItem,
  ClientResponse,
  SaveClientBody,
  ClientError,
} from './types';

// Electron から注入された apiBaseUrl を最優先で使う
// ?? を使う理由: || は空文字を falsy 扱いするため
declare global {
  interface Window {
    electronAPI?: {
      apiBaseUrl: string;
    };
  }
}

const BASE_URL =
  window.electronAPI?.apiBaseUrl
  ?? import.meta.env.VITE_API_URL
  ?? 'http://localhost:8000';

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

export async function postDownloadPdf(
  body: DownloadPdfRequestBody,
  timeoutMs = 30000,
): Promise<Blob> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${BASE_URL}/download-pdf`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!response.ok) {
      const err: DownloadError = { kind: 'server' };
      throw err;
    }
    return response.blob();
  } catch (e) {
    clearTimeout(timer);
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw { kind: 'timeout' } as DownloadError;
    }
    if (e && typeof e === 'object' && 'kind' in e) throw e;
    throw { kind: 'network' } as DownloadError;
  }
}

export async function postGenerateComment(
  body: GenerateCommentRequestBody,
  timeoutMs = 30000,
): Promise<GenerateCommentResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(`${BASE_URL}/generate-comment`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timer);

    if (!response.ok) {
      const err: DownloadError = { kind: 'server' };
      throw err;
    }
    return response.json();
  } catch (e) {
    clearTimeout(timer);
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw { kind: 'timeout' } as DownloadError;
    }
    if (e && typeof e === 'object' && 'kind' in e) throw e;
    throw { kind: 'network' } as DownloadError;
  }
}

// ---------------------------------------------------------------------------
// ep4.5: クライアント CRUD
// ---------------------------------------------------------------------------

// クライアント CRUD 共通のエラーハンドリング
function handleClientError(e: unknown): never {
  if (e instanceof DOMException && e.name === 'AbortError') {
    throw { kind: 'timeout' } as ClientError;
  }
  if (e && typeof e === 'object' && 'kind' in e) throw e;
  throw { kind: 'network' } as ClientError;
}

async function parseClientErrorResponse(response: Response): Promise<never> {
  const json = await response.json().catch(() => ({}));
  if (response.status === 404) {
    throw { kind: 'not_found' } as ClientError;
  }
  if (response.status === 422) {
    const detail = typeof json.detail === 'string' ? json.detail : '入力内容に誤りがあります';
    throw { kind: 'validation', detail } as ClientError;
  }
  throw { kind: 'server' } as ClientError;
}

export async function getClients(timeoutMs = 10000): Promise<ClientListItem[]> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BASE_URL}/clients`, {
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!response.ok) return parseClientErrorResponse(response);
    return response.json();
  } catch (e) {
    clearTimeout(timer);
    return handleClientError(e);
  }
}

export async function getClient(id: number, timeoutMs = 10000): Promise<ClientResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BASE_URL}/clients/${id}`, {
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!response.ok) return parseClientErrorResponse(response);
    return response.json();
  } catch (e) {
    clearTimeout(timer);
    return handleClientError(e);
  }
}

export async function postClient(body: SaveClientBody, timeoutMs = 10000): Promise<ClientResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BASE_URL}/clients`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!response.ok) return parseClientErrorResponse(response);
    return response.json();
  } catch (e) {
    clearTimeout(timer);
    return handleClientError(e);
  }
}

export async function putClient(id: number, body: SaveClientBody, timeoutMs = 10000): Promise<ClientResponse> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BASE_URL}/clients/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!response.ok) return parseClientErrorResponse(response);
    return response.json();
  } catch (e) {
    clearTimeout(timer);
    return handleClientError(e);
  }
}

export async function deleteClient(id: number, timeoutMs = 10000): Promise<void> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${BASE_URL}/clients/${id}`, {
      method: 'DELETE',
      signal: controller.signal,
    });
    clearTimeout(timer);
    if (!response.ok) return parseClientErrorResponse(response);
  } catch (e) {
    clearTimeout(timer);
    return handleClientError(e);
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
