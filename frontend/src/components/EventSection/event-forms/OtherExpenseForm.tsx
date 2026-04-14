import { TextField } from '@mui/material';
import type { UseFormRegister, FieldErrors } from 'react-hook-form';
import type { OtherExpenseEvent } from '../../../types/scenario';

interface Props {
  register: UseFormRegister<OtherExpenseEvent>;
  errors: FieldErrors<OtherExpenseEvent>;
}

export function OtherExpenseForm({ register, errors }: Props) {
  return (
    <>
      <TextField
        label="発生年（西暦）"
        type="number"
        fullWidth
        error={!!errors.year}
        helperText={errors.year?.message}
        {...register('year', {
          required: '発生年は必須です',
          valueAsNumber: true,
          min: { value: 1900, message: '有効な西暦を入力してください' },
        })}
      />
      <TextField
        label="金額（円）"
        type="number"
        fullWidth
        error={!!errors.amount}
        helperText={errors.amount?.message}
        {...register('amount', {
          valueAsNumber: true,
          min: { value: 0, message: '金額は 0 以上で入力してください' },
        })}
      />
      <TextField
        label="名称"
        fullWidth
        error={!!errors.name}
        helperText={errors.name?.message}
        {...register('name')}
      />
    </>
  );
}
