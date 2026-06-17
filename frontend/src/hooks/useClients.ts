import { useState, useEffect, useCallback } from 'react';
import {
  getClients as apiGetClients,
  getClient as apiGetClient,
  postClient as apiPostClient,
  putClient as apiPutClient,
  deleteClient as apiDeleteClient,
} from '../api/client';
import type {
  ClientListItem,
  ClientResponse,
  SimulateRequestBody,
} from '../api/types';

// API エラーの kind をユーザー向けメッセージに変換する
function toErrorMessage(e: unknown): string {
  if (e && typeof e === 'object' && 'kind' in e) {
    const err = e as { kind: string; detail?: string };
    switch (err.kind) {
      case 'network':
        return 'サーバーに接続できません。バックエンドが起動しているか確認してください。';
      case 'timeout':
        return '応答がありませんでした。時間をおいて再試行してください。';
      case 'not_found':
        return '指定されたクライアントが見つかりません。';
      case 'validation':
        return err.detail ?? '入力内容に誤りがあります。';
      case 'server':
        return 'サーバーでエラーが発生しました。';
    }
  }
  return '予期しないエラーが発生しました。';
}

export interface UseClientsReturn {
  clients: ClientListItem[];
  selectedId: number | null;
  loading: boolean;
  error: string | null;
  selectClient: (id: number) => Promise<ClientResponse>;
  saveClient: (name: string, scenario: SimulateRequestBody) => Promise<void>;
  overwriteClient: (scenario: SimulateRequestBody) => Promise<void>;
  removeClient: (id: number) => Promise<void>;
  refreshClients: () => Promise<void>;
}

export function useClients(): UseClientsReturn {
  const [clients, setClients] = useState<ClientListItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 選択中のクライアント名（上書き保存時に必要）
  const [selectedName, setSelectedName] = useState<string>('');

  const refreshClients = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await apiGetClients();
      setClients(list);
    } catch (e) {
      setError(toErrorMessage(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // マウント時に一覧を取得
  useEffect(() => {
    refreshClients();
  }, [refreshClients]);

  const selectClient = useCallback(async (id: number): Promise<ClientResponse> => {
    setError(null);
    try {
      const detail = await apiGetClient(id);
      setSelectedId(id);
      setSelectedName(detail.name);
      return detail;
    } catch (e) {
      setError(toErrorMessage(e));
      throw e;
    }
  }, []);

  const saveClient = useCallback(async (name: string, scenario: SimulateRequestBody): Promise<void> => {
    setError(null);
    try {
      const created = await apiPostClient({ name, scenario });
      setSelectedId(created.id);
      setSelectedName(created.name);
      await refreshClients();
    } catch (e) {
      setError(toErrorMessage(e));
    }
  }, [refreshClients]);

  const overwriteClient = useCallback(async (scenario: SimulateRequestBody): Promise<void> => {
    setError(null);
    if (selectedId === null) {
      setError('クライアントが選択されていません。');
      return;
    }
    try {
      await apiPutClient(selectedId, { name: selectedName, scenario });
      await refreshClients();
    } catch (e) {
      setError(toErrorMessage(e));
    }
  }, [selectedId, selectedName, refreshClients]);

  const removeClient = useCallback(async (id: number): Promise<void> => {
    setError(null);
    try {
      await apiDeleteClient(id);
      if (selectedId === id) {
        setSelectedId(null);
        setSelectedName('');
      }
      await refreshClients();
    } catch (e) {
      setError(toErrorMessage(e));
    }
  }, [selectedId, refreshClients]);

  return {
    clients,
    selectedId,
    loading,
    error,
    selectClient,
    saveClient,
    overwriteClient,
    removeClient,
    refreshClients,
  };
}
