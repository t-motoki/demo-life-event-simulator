import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Box, Paper, TextField, Typography } from '@mui/material';
import { ClientForm } from './ClientForm';
import { SpouseToggle } from './SpouseToggle';
import type { ClientFormData, ScenarioCommonData } from '../../types/scenario';

interface Props {
  onClientChange: (data: ClientFormData) => void;
  onSpouseChange: (data: ClientFormData | null) => void;
  onCommonChange: (data: ScenarioCommonData) => void;
}

export function ClientSection({ onClientChange, onSpouseChange, onCommonChange }: Props) {
  const [spouseVisible, setSpouseVisible] = useState(false);

  const { register, watch, formState: { errors } } = useForm<ScenarioCommonData>({
    defaultValues: {
      savings_initial: 0,
      end_age: 90,
      start_year: new Date().getFullYear(),
    },
    mode: 'onChange',
  });

  // フォーム値の変化を親へ通知する
  const values = watch();
  const handleCommonChange = () => {
    onCommonChange(values);
  };

  const handleSpouseToggle = () => {
    const next = !spouseVisible;
    setSpouseVisible(next);
    // 非表示になったら親に null を通知する
    if (!next) onSpouseChange(null);
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        クライアント情報
      </Typography>

      {/* シナリオ共通情報 */}
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, mb: 3 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 'bold' }}>
          シナリオ共通設定
        </Typography>
        <TextField
          label="現在の貯蓄残高（円）"
          type="number"
          error={!!errors.savings_initial}
          helperText={errors.savings_initial?.message}
          {...register('savings_initial', {
            required: '貯蓄残高は必須です',
            valueAsNumber: true,
            min: { value: 0, message: '貯蓄残高は 0 以上で入力してください' },
            onChange: handleCommonChange,
          })}
        />
        <TextField
          label="シミュレーション終了年齢"
          type="number"
          error={!!errors.end_age}
          helperText={errors.end_age?.message}
          {...register('end_age', {
            valueAsNumber: true,
            min: { value: 1, message: '終了年齢は 1 以上で入力してください' },
            onChange: handleCommonChange,
          })}
        />
        <TextField
          label="シミュレーション開始年（西暦）"
          type="number"
          error={!!errors.start_year}
          helperText={errors.start_year?.message}
          {...register('start_year', {
            valueAsNumber: true,
            min: { value: 1900, message: '有効な西暦を入力してください' },
            onChange: handleCommonChange,
          })}
        />
      </Box>

      {/* 本人情報 */}
      <ClientForm title="本人情報" onChange={onClientChange} />

      {/* 配偶者トグルと配偶者フォーム */}
      <Box sx={{ mt: 3 }}>
        <SpouseToggle shown={spouseVisible} onToggle={handleSpouseToggle} />
        {/* 非表示時はアンマウントして React Hook Form の状態をリセットする */}
        {spouseVisible && (
          <Box sx={{ mt: 2 }}>
            <ClientForm title="配偶者情報" onChange={onSpouseChange} />
          </Box>
        )}
      </Box>
    </Paper>
  );
}
