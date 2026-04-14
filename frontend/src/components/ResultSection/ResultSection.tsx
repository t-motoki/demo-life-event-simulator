import { useEffect, useRef } from 'react';
import { Box, Typography } from '@mui/material';
import { CashFlowTable } from './CashFlowTable';
import type { CashFlowRowResponse } from '../../api/types';

interface Props {
  result: CashFlowRowResponse[] | null;
  hasSpouse: boolean;
}

export function ResultSection({ result, hasSpouse }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  // 結果が更新されたら自動的にスクロールして FP が気づけるようにする
  useEffect(() => {
    if (result && ref.current) {
      ref.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [result]);

  // 未実行時は何も表示しない（初期状態での空テーブルを避ける）
  if (!result) return null;

  return (
    <Box ref={ref} sx={{ mt: 4 }}>
      <Typography variant="h6" gutterBottom>
        シミュレーション結果
      </Typography>
      <CashFlowTable rows={result} hasSpouse={hasSpouse} />
    </Box>
  );
}
