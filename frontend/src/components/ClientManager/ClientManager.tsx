import { useState } from 'react';
import {
  Box,
  Button,
  Autocomplete,
  TextField,
  Alert,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Paper,
} from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import SaveAsIcon from '@mui/icons-material/SaveAs';
import DeleteIcon from '@mui/icons-material/Delete';
import { SaveDialog } from './SaveDialog';
import { useClients } from '../../hooks/useClients';
import type { SimulateRequestBody, ClientListItem } from '../../api/types';

interface ClientManagerProps {
  onLoad: (scenario: SimulateRequestBody) => void;
  getCurrentScenario: () => SimulateRequestBody;
}

export function ClientManager({ onLoad, getCurrentScenario }: ClientManagerProps) {
  const {
    clients,
    selectedId,
    loading,
    error,
    selectClient,
    saveClient,
    overwriteClient,
    removeClient,
  } = useClients();

  const [saveDialogOpen, setSaveDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // Autocomplete の選択値を管理
  const selectedClient = clients.find((c) => c.id === selectedId) ?? null;

  const handleSelect = async (_event: unknown, value: ClientListItem | null) => {
    if (!value) return;
    try {
      const detail = await selectClient(value.id);
      onLoad(detail.scenario);
    } catch {
      // エラーは useClients 内で処理済み
    }
  };

  const handleSave = () => {
    if (selectedId !== null) {
      // 選択中なら上書き保存
      overwriteClient(getCurrentScenario());
    } else {
      // 未選択なら名前入力ダイアログ
      setSaveDialogOpen(true);
    }
  };

  const handleSaveAs = () => {
    setSaveDialogOpen(true);
  };

  const handleSaveDialogSubmit = async (name: string) => {
    setSaveDialogOpen(false);
    await saveClient(name, getCurrentScenario());
  };

  const handleDelete = () => {
    setDeleteDialogOpen(true);
  };

  const handleDeleteConfirm = async () => {
    setDeleteDialogOpen(false);
    if (selectedId !== null) {
      await removeClient(selectedId);
    }
  };

  return (
    <Paper sx={{ p: 2, mb: 3 }}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
        <Autocomplete
          options={clients}
          getOptionLabel={(option) => option.name}
          value={selectedClient}
          onChange={handleSelect}
          loading={loading}
          sx={{ minWidth: 250, flexGrow: 1 }}
          renderInput={(params) => (
            <TextField {...params} label="クライアント選択" size="small" />
          )}
          isOptionEqualToValue={(option, value) => option.id === value.id}
        />

        <Button
          variant="outlined"
          startIcon={<SaveIcon />}
          onClick={handleSave}
          size="small"
        >
          保存
        </Button>

        <Button
          variant="outlined"
          startIcon={<SaveAsIcon />}
          onClick={handleSaveAs}
          size="small"
        >
          名前を付けて保存
        </Button>

        <Button
          variant="outlined"
          color="error"
          startIcon={<DeleteIcon />}
          onClick={handleDelete}
          disabled={selectedId === null}
          size="small"
        >
          削除
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mt: 1 }}>
          {error}
        </Alert>
      )}

      {/* 名前入力ダイアログ */}
      {saveDialogOpen && (
        <SaveDialog
          open={saveDialogOpen}
          defaultName=""
          onSave={handleSaveDialogSubmit}
          onCancel={() => setSaveDialogOpen(false)}
        />
      )}

      {/* 削除確認ダイアログ */}
      <Dialog open={deleteDialogOpen} onClose={() => setDeleteDialogOpen(false)}>
        <DialogTitle>クライアントの削除</DialogTitle>
        <DialogContent>
          <DialogContentText>このクライアントを削除しますか？</DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>いいえ</Button>
          <Button onClick={handleDeleteConfirm} color="error">はい</Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
}
