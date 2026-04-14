import { Button } from '@mui/material';
import PersonAddIcon from '@mui/icons-material/PersonAdd';
import PersonRemoveIcon from '@mui/icons-material/PersonRemove';

interface Props {
  shown: boolean;
  onToggle: () => void;
}

export function SpouseToggle({ shown, onToggle }: Props) {
  return (
    <Button
      variant="outlined"
      startIcon={shown ? <PersonRemoveIcon /> : <PersonAddIcon />}
      onClick={onToggle}
      color={shown ? 'error' : 'primary'}
    >
      {shown ? '配偶者を削除' : '配偶者を追加'}
    </Button>
  );
}
