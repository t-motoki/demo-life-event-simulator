import { TextField, FormControlLabel, Checkbox } from '@mui/material';
import type { UseFormRegister, FieldErrors, Control } from 'react-hook-form';
import { Controller } from 'react-hook-form';
import type { HousingEvent } from '../../../types/scenario';

interface Props {
  register: UseFormRegister<HousingEvent>;
  errors: FieldErrors<HousingEvent>;
  control: Control<HousingEvent>;
}

export function HousingForm({ register, errors, control }: Props) {
  return (
    <>
      <TextField
        label="購入年（西暦）"
        type="number"
        fullWidth
        error={!!errors.year}
        helperText={errors.year?.message}
        {...register('year', {
          required: '購入年は必須です',
          valueAsNumber: true,
          min: { value: 1900, message: '有効な西暦を入力してください' },
        })}
      />
      <TextField
        label="物件価格（円）"
        type="number"
        fullWidth
        error={!!errors.price}
        helperText={errors.price?.message}
        {...register('price', {
          valueAsNumber: true,
          min: { value: 0, message: '物件価格は 0 以上で入力してください' },
        })}
      />
      <TextField
        label="頭金（円）"
        type="number"
        fullWidth
        error={!!errors.down_payment}
        helperText={errors.down_payment?.message}
        {...register('down_payment', {
          valueAsNumber: true,
          min: { value: 0, message: '頭金は 0 以上で入力してください' },
        })}
      />
      <TextField
        label="ローン年数"
        type="number"
        fullWidth
        error={!!errors.loan_years}
        helperText={errors.loan_years?.message}
        {...register('loan_years', {
          valueAsNumber: true,
          min: { value: 1, message: 'ローン年数は 1〜50 で入力してください' },
          max: { value: 50, message: 'ローン年数は 1〜50 で入力してください' },
        })}
      />
      <TextField
        label="金利（例: 0.02 = 2%）"
        type="number"
        fullWidth
        slotProps={{ htmlInput: { step: 0.001 } }}
        error={!!errors.interest_rate}
        helperText={errors.interest_rate?.message}
        {...register('interest_rate', {
          valueAsNumber: true,
          min: { value: 0, message: '金利は 0〜1 の範囲で入力してください' },
          max: { value: 1, message: '金利は 0〜1 の範囲で入力してください' },
        })}
      />
      <Controller
        name="use_tax_deduction"
        control={control}
        render={({ field }) => (
          <FormControlLabel
            control={<Checkbox {...field} checked={field.value} />}
            label="住宅ローン控除を使う"
          />
        )}
      />
    </>
  );
}
