import { useForm } from 'react-hook-form';
import { Box, Paper, TextField, Typography } from '@mui/material';
import type { MonthlyExpensesRequest } from '../../api/types';

interface Props {
  onExpenseChange: (data: MonthlyExpensesRequest) => void;
}

export function ExpenseSection({ onExpenseChange }: Props) {
  const {
    register,
    watch,
    formState: { errors },
  } = useForm<MonthlyExpensesRequest>({
    defaultValues: { living: 0, insurance: 0, other: 0 },
    mode: 'onChange',
  });

  const values = watch();
  // 月間合計を参考値としてリアルタイム表示する（FP の確認用）
  const monthlyTotal = (values.living ?? 0) + (values.insurance ?? 0) + (values.other ?? 0);

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        月間支出
      </Typography>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <TextField
          label="月間生活費（円）"
          type="number"
          error={!!errors.living}
          helperText={errors.living?.message}
          {...register('living', {
            required: '月間生活費は必須です',
            valueAsNumber: true,
            min: { value: 0, message: '生活費は 0 以上で入力してください' },
            onChange: () => onExpenseChange(watch()),
          })}
        />
        <TextField
          label="保険料（円/月）"
          type="number"
          error={!!errors.insurance}
          helperText={errors.insurance?.message}
          {...register('insurance', {
            valueAsNumber: true,
            min: { value: 0, message: '保険料は 0 以上で入力してください' },
            onChange: () => onExpenseChange(watch()),
          })}
        />
        <TextField
          label="その他固定費（円/月）"
          type="number"
          error={!!errors.other}
          helperText={errors.other?.message}
          {...register('other', {
            valueAsNumber: true,
            min: { value: 0, message: 'その他固定費は 0 以上で入力してください' },
            onChange: () => onExpenseChange(watch()),
          })}
        />
        <Typography variant="body2" color="text.secondary">
          月間合計（参考）: {monthlyTotal.toLocaleString()} 円
        </Typography>
      </Box>
    </Paper>
  );
}
