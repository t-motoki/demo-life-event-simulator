import { TextField } from '@mui/material';
import type { UseFormRegister, FieldErrors } from 'react-hook-form';
import type { CareEvent } from '../../../types/scenario';

interface Props {
  register: UseFormRegister<CareEvent>;
  errors: FieldErrors<CareEvent>;
}

export function CareForm({ register, errors }: Props) {
  return (
    <>
      <TextField
        label="開始年（西暦）"
        type="number"
        fullWidth
        error={!!errors.year}
        helperText={errors.year?.message}
        {...register('year', {
          required: '開始年は必須です',
          valueAsNumber: true,
          min: { value: 1900, message: '有効な西暦を入力してください' },
        })}
      />
      <TextField
        label="期間（年）"
        type="number"
        fullWidth
        error={!!errors.duration_years}
        helperText={errors.duration_years?.message}
        {...register('duration_years', {
          valueAsNumber: true,
          min: { value: 1, message: '期間は 1 以上で入力してください' },
        })}
      />
      <TextField
        label="月額費用（円）"
        type="number"
        fullWidth
        error={!!errors.monthly_cost}
        helperText={errors.monthly_cost?.message}
        {...register('monthly_cost', {
          valueAsNumber: true,
          min: { value: 0, message: '月額費用は 0 以上で入力してください' },
        })}
      />
    </>
  );
}
