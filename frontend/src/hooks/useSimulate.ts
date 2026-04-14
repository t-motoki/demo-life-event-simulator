import { useState, useCallback } from 'react';
import { postSimulate } from '../api/client';
import type { SimulateRequestBody, CashFlowRowResponse, SimulateError } from '../api/types';

interface UseSimulateReturn {
  loading: boolean;
  result: CashFlowRowResponse[] | null;
  error: SimulateError | null;
  simulate: (scenario: SimulateRequestBody) => Promise<void>;
}

export function useSimulate(): UseSimulateReturn {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CashFlowRowResponse[] | null>(null);
  const [error, setError] = useState<SimulateError | null>(null);

  // 呼び出しのたびに前回の result・error をリセットしてから fetch を開始する
  const simulate = useCallback(async (scenario: SimulateRequestBody) => {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const rows = await postSimulate(scenario);
      setResult(rows);
    } catch (e) {
      setError(e as SimulateError);
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, result, error, simulate };
}
