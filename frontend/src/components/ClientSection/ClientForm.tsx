import { useEffect } from 'react';
import { useForm, Controller } from 'react-hook-form';
import {
  Box,
  TextField,
  MenuItem,
  Typography,
} from '@mui/material';
import type { ClientFormData, IncomeModel } from '../../types/scenario';

interface Props {
  title: string;
  defaultValues?: Partial<ClientFormData>;
  onChange: (data: ClientFormData) => void;
}

const INCOME_MODEL_OPTIONS: { value: IncomeModel; label: string }[] = [
  { value: 'flat', label: '一定' },
  { value: 'raise_rate', label: '昇給率指定' },
  { value: 'post_retirement', label: '定年後減額' },
];

const DEFAULT_VALUES: ClientFormData = {
  age: 0,
  annual_income: 0,
  income_model: 'flat',
  raise_rate: 0,
  retirement_age: 65,
  post_retirement_income: 0,
  pension_start_age: 65,
  pension_annual: 0,
};

export function ClientForm({ title, defaultValues, onChange }: Props) {
  const {
    register,
    watch,
    control,
    formState: { errors },
    getValues,
  } = useForm<ClientFormData>({
    defaultValues: { ...DEFAULT_VALUES, ...defaultValues },
    mode: 'onChange',
  });

  const incomeModel = watch('income_model');

  // フォーム値の変化を親コンポーネントへ通知する
  useEffect(() => {
    const subscription = watch((values) => {
      onChange(values as ClientFormData);
    });
    return () => subscription.unsubscribe();
  }, [watch, onChange]);

  // 初期値を親に通知する
  useEffect(() => {
    onChange(getValues());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
        {title}
      </Typography>

      <TextField
        label="現在年齢"
        type="number"
        error={!!errors.age}
        helperText={errors.age?.message}
        {...register('age', {
          required: '現在年齢は必須です',
          valueAsNumber: true,
          min: { value: 1, message: '年齢は 1〜100 で入力してください' },
          max: { value: 100, message: '年齢は 1〜100 で入力してください' },
        })}
      />

      <TextField
        label="税引後年収（円）"
        type="number"
        error={!!errors.annual_income}
        helperText={errors.annual_income?.message}
        {...register('annual_income', {
          required: '税引後年収は必須です',
          valueAsNumber: true,
          min: { value: 0, message: '年収は 0 以上で入力してください' },
        })}
      />

      <Controller
        name="income_model"
        control={control}
        render={({ field }) => (
          <TextField select label="収入モデル" {...field}>
            {INCOME_MODEL_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </TextField>
        )}
      />

      <TextField
        label="昇給率（%）"
        type="number"
        // 収入モデルが「昇給率指定」のときのみ入力可
        disabled={incomeModel !== 'raise_rate'}
        error={!!errors.raise_rate}
        helperText={errors.raise_rate?.message}
        {...register('raise_rate', {
          valueAsNumber: true,
          max: { value: 100, message: '昇給率は 100% 以下で入力してください' },
          min: { value: 0, message: '昇給率は 0 以上で入力してください' },
        })}
      />

      <TextField
        label="定年年齢"
        type="number"
        error={!!errors.retirement_age}
        helperText={errors.retirement_age?.message}
        {...register('retirement_age', {
          valueAsNumber: true,
          min: { value: 1, message: '定年年齢は 1 以上で入力してください' },
        })}
      />

      <TextField
        label="定年後年収（円）"
        type="number"
        // 収入モデルが「定年後減額」のときのみ入力可
        disabled={incomeModel !== 'post_retirement'}
        error={!!errors.post_retirement_income}
        helperText={errors.post_retirement_income?.message}
        {...register('post_retirement_income', {
          valueAsNumber: true,
          min: { value: 0, message: '定年後年収は 0 以上で入力してください' },
        })}
      />

      <TextField
        label="年金受給開始年齢"
        type="number"
        error={!!errors.pension_start_age}
        helperText={errors.pension_start_age?.message}
        {...register('pension_start_age', {
          valueAsNumber: true,
          min: { value: 1, message: '年金受給開始年齢は 1 以上で入力してください' },
        })}
      />

      <TextField
        label="年金額（円/年）"
        type="number"
        error={!!errors.pension_annual}
        helperText={errors.pension_annual?.message}
        {...register('pension_annual', {
          valueAsNumber: true,
          min: { value: 0, message: '年金額は 0 以上で入力してください' },
        })}
      />
    </Box>
  );
}
