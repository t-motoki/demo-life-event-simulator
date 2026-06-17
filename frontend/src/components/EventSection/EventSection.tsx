import { useState } from 'react';
import { Box, Button, Paper, Typography } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import { EventCard } from './EventCard';
import { EventDialog } from './EventDialog';
import type { LifeEvent } from '../../types/scenario';
import type { Dispatch } from 'react';

type EventAction =
  | { type: 'ADD'; event: LifeEvent }
  | { type: 'EDIT'; index: number; event: LifeEvent }
  | { type: 'DELETE'; index: number }
  | { type: 'SET_ALL'; events: LifeEvent[] };

interface Props {
  events: LifeEvent[];
  dispatch: Dispatch<EventAction>;
}

export function EventSection({ events, dispatch }: Props) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<{ index: number; event: LifeEvent } | null>(null);

  const handleAdd = (event: LifeEvent) => {
    dispatch({ type: 'ADD', event });
  };

  const handleEdit = (index: number, event: LifeEvent) => {
    dispatch({ type: 'EDIT', index, event });
  };

  const handleDelete = (index: number) => {
    dispatch({ type: 'DELETE', index });
  };

  const openAddDialog = () => {
    setEditTarget(null);
    setDialogOpen(true);
  };

  const openEditDialog = (index: number, event: LifeEvent) => {
    setEditTarget({ index, event });
    setDialogOpen(true);
  };

  const closeDialog = () => {
    setDialogOpen(false);
    setEditTarget(null);
  };

  const handleSubmit = (event: LifeEvent) => {
    if (editTarget !== null) {
      handleEdit(editTarget.index, event);
    } else {
      handleAdd(event);
    }
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
        <Typography variant="h6">ライフイベント</Typography>
        <Button variant="outlined" startIcon={<AddIcon />} onClick={openAddDialog}>
          イベントを追加
        </Button>
      </Box>

      {events.length === 0 ? (
        <Typography color="text.secondary" variant="body2">
          イベントがまだありません
        </Typography>
      ) : (
        events.map((event, index) => (
          <EventCard
            key={index}
            event={event}
            onEdit={() => openEditDialog(index, event)}
            onDelete={() => handleDelete(index)}
          />
        ))
      )}

      {/* ダイアログを閉じたら DOM からアンマウントして初期値をリセットする */}
      {dialogOpen && (
        <EventDialog
          open={dialogOpen}
          initialValue={editTarget?.event}
          onSubmit={handleSubmit}
          onClose={closeDialog}
        />
      )}
    </Paper>
  );
}
