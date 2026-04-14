import { Card, CardContent, CardActions, Typography, Button, Box } from '@mui/material';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import type { LifeEvent } from '../../types/scenario';
import { formatEventSummary } from '../../utils/formatCurrency';

const EVENT_TYPE_LABEL: Record<LifeEvent['type'], string> = {
  marriage: '結婚',
  birth: '出産',
  housing: '住宅購入',
  education: '教育',
  care: '介護',
  other_expense: 'その他支出',
};

interface Props {
  event: LifeEvent;
  onEdit: () => void;
  onDelete: () => void;
}

export function EventCard({ event, onEdit, onDelete }: Props) {
  return (
    <Card variant="outlined" sx={{ mb: 1 }}>
      <CardContent sx={{ pb: 0 }}>
        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography variant="subtitle2" color="primary">
            {EVENT_TYPE_LABEL[event.type]}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {event.year} 年
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary">
          {formatEventSummary(event)}
        </Typography>
      </CardContent>
      <CardActions sx={{ pt: 0 }}>
        <Button size="small" startIcon={<EditIcon />} onClick={onEdit}>
          編集
        </Button>
        <Button size="small" color="error" startIcon={<DeleteIcon />} onClick={onDelete}>
          削除
        </Button>
      </CardActions>
    </Card>
  );
}
