import { TextField } from '@mui/material';
import type { UseFormRegister, FieldErrors } from 'react-hook-form';
import type { BirthEvent } from '../../../types/scenario';

interface Props {
  register: UseFormRegister<BirthEvent>;
  errors: FieldErrors<BirthEvent>;
}

export function BirthForm({ register, errors }: Props) {
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
        label="子ども人数"
        type="number"
        fullWidth
        error={!!errors.child_count}
        helperText={errors.child_count?.message}
        {...register('child_count', {
          valueAsNumber: true,
          min: { value: 1, message: '1 人以上で入力してください' },
        })}
      />
      <TextField
        label="本人育休中収入率（0〜1）"
        type="number"
        fullWidth
        slotProps={{ htmlInput: { step: 0.1 } }}
        error={!!errors.client_maternity_rate}
        helperText={errors.client_maternity_rate?.message}
        {...register('client_maternity_rate', {
          valueAsNumber: true,
          min: { value: 0, message: '収入率は 0〜1 で入力してください' },
          max: { value: 1, message: '収入率は 0〜1 で入力してください' },
        })}
      />
      <TextField
        label="本人育休期間（年）"
        type="number"
        fullWidth
        error={!!errors.client_maternity_years}
        helperText={errors.client_maternity_years?.message}
        {...register('client_maternity_years', {
          valueAsNumber: true,
          min: { value: 0, message: '育休期間は 0 以上で入力してください' },
        })}
      />
      <TextField
        label="配偶者育休中収入率（0〜1）"
        type="number"
        fullWidth
        slotProps={{ htmlInput: { step: 0.1 } }}
        error={!!errors.spouse_maternity_rate}
        helperText={errors.spouse_maternity_rate?.message}
        {...register('spouse_maternity_rate', {
          valueAsNumber: true,
          min: { value: 0, message: '収入率は 0〜1 で入力してください' },
          max: { value: 1, message: '収入率は 0〜1 で入力してください' },
        })}
      />
      <TextField
        label="配偶者育休期間（年）"
        type="number"
        fullWidth
        error={!!errors.spouse_maternity_years}
        helperText={errors.spouse_maternity_years?.message}
        {...register('spouse_maternity_years', {
          valueAsNumber: true,
          min: { value: 0, message: '育休期間は 0 以上で入力してください' },
        })}
      />
    </>
  );
}
