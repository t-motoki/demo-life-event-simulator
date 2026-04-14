import { Button, CircularProgress } from '@mui/material';

interface Props {
  loading: boolean;
  onClick: () => void;
}

export function SimulateButton({ loading, onClick }: Props) {
  return (
    <Button
      variant="contained"
      size="large"
      disabled={loading}
      onClick={onClick}
      startIcon={loading ? <CircularProgress size={20} color="inherit" /> : null}
    >
      {loading ? '計算中...' : 'シミュレーション実行'}
    </Button>
  );
}
