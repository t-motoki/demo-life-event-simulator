import { TextField, MenuItem } from '@mui/material';
import type { UseFormRegister, FieldErrors, Control } from 'react-hook-form';
import { Controller } from 'react-hook-form';
import type { EducationEvent, SchoolType } from '../../../types/scenario';

interface Props {
  register: UseFormRegister<EducationEvent>;
  errors: FieldErrors<EducationEvent>;
  control: Control<EducationEvent>;
}

const SCHOOL_OPTIONS: { value: SchoolType; label: string }[] = [
  { value: 'public', label: '公立' },
  { value: 'private', label: '私立' },
];

function SchoolSelect({
  name,
  label,
  control,
}: {
  name: keyof Pick<EducationEvent, 'kindergarten' | 'elementary' | 'junior_high' | 'high_school' | 'university'>;
  label: string;
  control: Control<EducationEvent>;
}) {
  return (
    <Controller
      name={name}
      control={control}
      render={({ field }) => (
        <TextField select label={label} fullWidth {...field}>
          {SCHOOL_OPTIONS.map((opt) => (
            <MenuItem key={opt.value} value={opt.value}>
              {opt.label}
            </MenuItem>
          ))}
        </TextField>
      )}
    />
  );
}

export function EducationForm({ register, errors, control }: Props) {
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
        label="子の誕生年（西暦）"
        type="number"
        fullWidth
        error={!!errors.child_birth_year}
        helperText={errors.child_birth_year?.message}
        {...register('child_birth_year', {
          required: '子の誕生年は必須です',
          valueAsNumber: true,
          min: { value: 1900, message: '有効な西暦を入力してください' },
        })}
      />
      <SchoolSelect name="kindergarten" label="幼稚園" control={control} />
      <SchoolSelect name="elementary" label="小学校" control={control} />
      <SchoolSelect name="junior_high" label="中学校" control={control} />
      <SchoolSelect name="high_school" label="高校" control={control} />
      <SchoolSelect name="university" label="大学" control={control} />
    </>
  );
}
