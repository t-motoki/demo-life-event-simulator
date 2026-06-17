import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  Button,
} from '@mui/material';

interface SaveDialogProps {
  open: boolean;
  defaultName: string;
  onSave: (name: string) => void;
  onCancel: () => void;
}

export function SaveDialog({ open, defaultName, onSave, onCancel }: SaveDialogProps) {
  const [name, setName] = useState(defaultName);

  const handleSave = () => {
    if (name.trim()) {
      onSave(name.trim());
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && name.trim()) {
      handleSave();
    }
  };

  return (
    <Dialog open={open} onClose={onCancel} maxWidth="xs" fullWidth>
      <DialogTitle>クライアントを保存</DialogTitle>
      <DialogContent>
        <TextField
          autoFocus
          label="クライアント名"
          fullWidth
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          sx={{ mt: 1 }}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onCancel}>キャンセル</Button>
        <Button onClick={handleSave} variant="contained" disabled={!name.trim()}>
          保存する
        </Button>
      </DialogActions>
    </Dialog>
  );
}
