import { TextField } from '@mui/material';
import type { UseFormRegister, FieldErrors } from 'react-hook-form';
import type { MarriageEvent } from '../../../types/scenario';

interface Props {
  register: UseFormRegister<MarriageEvent>;
  errors: FieldErrors<MarriageEvent>;
}

export function MarriageForm({ register, errors }: Props) {
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
        label="一時費用（円）"
        type="number"
        fullWidth
        error={!!errors.cost}
        helperText={errors.cost?.message}
        {...register('cost', {
          valueAsNumber: true,
          min: { value: 0, message: '費用は 0 以上で入力してください' },
        })}
      />
    </>
  );
}
