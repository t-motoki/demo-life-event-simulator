import { useEffect, useRef, useState } from 'react';
import { Box, Button, Typography, Alert } from '@mui/material';
import { CashFlowTable } from './CashFlowTable';
import type { CashFlowRowResponse, SimulateRequestBody } from '../../api/types';
import { postDownloadPdf } from '../../api/client';

interface Props {
  result: CashFlowRowResponse[] | null;
  hasSpouse: boolean;
  scenarioBody: SimulateRequestBody | null;
}

export function ResultSection({ result, hasSpouse, scenarioBody }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [isDownloading, setIsDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  // 結果が更新されたら自動的にスクロールして FP が気づけるようにする
  useEffect(() => {
    if (result && ref.current) {
      ref.current.scrollIntoView({ behavior: 'smooth' });
    }
    // シミュレーション再実行時は前回のエラーをクリアする（AC-4-6 対応）
    setDownloadError(null);
  }, [result]);

  // 未実行時は何も表示しない（初期状態での空テーブルを避ける）
  if (!result) return null;

  const handleDownloadPdf = async () => {
    if (!scenarioBody || !result) return;

    setIsDownloading(true);
    setDownloadError(null);

    try {
      const blob = await postDownloadPdf({
        scenario: scenarioBody,
        rows: result,
        fp_comment: '',
      });

      // ブラウザのダウンロードダイアログを起動する
      const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      const filename = `cf_simulation_${today}.pdf`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadError('ダウンロードに失敗しました。しばらくしてから再試行してください。');
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <Box ref={ref} sx={{ mt: 4 }}>
      <Typography variant="h6" gutterBottom>
        シミュレーション結果
      </Typography>
      <CashFlowTable rows={result} hasSpouse={hasSpouse} />

      <Box sx={{ mt: 2, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Button
          variant="contained"
          onClick={handleDownloadPdf}
          disabled={isDownloading}
        >
          {isDownloading ? 'ダウンロード中...' : 'PDF をダウンロード'}
        </Button>
      </Box>

      {downloadError && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {downloadError}
        </Alert>
      )}
    </Box>
  );
}
