import { useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  MenuItem,
  TextField,
  Box,
} from '@mui/material';
import { useForm } from 'react-hook-form';
import { MarriageForm } from './event-forms/MarriageForm';
import { BirthForm } from './event-forms/BirthForm';
import { HousingForm } from './event-forms/HousingForm';
import { EducationForm } from './event-forms/EducationForm';
import { CareForm } from './event-forms/CareForm';
import { OtherExpenseForm } from './event-forms/OtherExpenseForm';
import type { LifeEvent, MarriageEvent, BirthEvent, HousingEvent, EducationEvent, CareEvent, OtherExpenseEvent } from '../../types/scenario';

type EventType = LifeEvent['type'];

const EVENT_TYPE_OPTIONS: { value: EventType; label: string }[] = [
  { value: 'marriage', label: '結婚' },
  { value: 'birth', label: '出産' },
  { value: 'housing', label: '住宅購入' },
  { value: 'education', label: '教育' },
  { value: 'care', label: '介護' },
  { value: 'other_expense', label: 'その他支出' },
];

interface Props {
  open: boolean;
  initialValue?: LifeEvent;
  onSubmit: (event: LifeEvent) => void;
  onClose: () => void;
}

// 各種別のデフォルト値（追加モード用）
const DEFAULT_MARRIAGE: MarriageEvent = { type: 'marriage', year: new Date().getFullYear(), cost: 0 };
const DEFAULT_BIRTH: BirthEvent = { type: 'birth', year: new Date().getFullYear(), child_count: 1, client_maternity_rate: 1.0, client_maternity_years: 0, spouse_maternity_rate: 1.0, spouse_maternity_years: 0 };
const DEFAULT_HOUSING: HousingEvent = { type: 'housing', year: new Date().getFullYear(), price: 0, down_payment: 0, loan_years: 35, interest_rate: 0.02, use_tax_deduction: true };
const DEFAULT_EDUCATION: EducationEvent = { type: 'education', year: new Date().getFullYear(), child_birth_year: new Date().getFullYear(), kindergarten: 'public', elementary: 'public', junior_high: 'public', high_school: 'public', university: 'public' };
const DEFAULT_CARE: CareEvent = { type: 'care', year: new Date().getFullYear(), duration_years: 1, monthly_cost: 0 };
const DEFAULT_OTHER: OtherExpenseEvent = { type: 'other_expense', year: new Date().getFullYear(), amount: 0, name: '' };

function getDefaultValues(type: EventType): LifeEvent {
  switch (type) {
    case 'marriage': return DEFAULT_MARRIAGE;
    case 'birth': return DEFAULT_BIRTH;
    case 'housing': return DEFAULT_HOUSING;
    case 'education': return DEFAULT_EDUCATION;
    case 'care': return DEFAULT_CARE;
    case 'other_expense': return DEFAULT_OTHER;
  }
}

export function EventDialog({ open, initialValue, onSubmit, onClose }: Props) {
  const [selectedType, setSelectedType] = useState<EventType>(
    initialValue?.type ?? 'marriage',
  );

  // 種別ごとに useForm を切り替えるため、種別が変わったら key を変えてリマウントする
  // marriage フォーム
  const marriageForm = useForm<MarriageEvent>({
    defaultValues: (initialValue?.type === 'marriage' ? initialValue : DEFAULT_MARRIAGE),
  });
  const birthForm = useForm<BirthEvent>({
    defaultValues: (initialValue?.type === 'birth' ? initialValue : DEFAULT_BIRTH),
  });
  const housingForm = useForm<HousingEvent>({
    defaultValues: (initialValue?.type === 'housing' ? initialValue : DEFAULT_HOUSING),
  });
  const educationForm = useForm<EducationEvent>({
    defaultValues: (initialValue?.type === 'education' ? initialValue : DEFAULT_EDUCATION),
  });
  const careForm = useForm<CareEvent>({
    defaultValues: (initialValue?.type === 'care' ? initialValue : DEFAULT_CARE),
  });
  const otherForm = useForm<OtherExpenseEvent>({
    defaultValues: (initialValue?.type === 'other_expense' ? initialValue : DEFAULT_OTHER),
  });

  const handleTypeChange = (type: EventType) => {
    setSelectedType(type);
  };

  const handleSubmit = async () => {
    let result: LifeEvent | null = null;

    switch (selectedType) {
      case 'marriage': {
        const valid = await marriageForm.trigger();
        if (!valid) return;
        result = { ...marriageForm.getValues(), type: 'marriage' };
        break;
      }
      case 'birth': {
        const valid = await birthForm.trigger();
        if (!valid) return;
        result = { ...birthForm.getValues(), type: 'birth' };
        break;
      }
      case 'housing': {
        const valid = await housingForm.trigger();
        if (!valid) return;
        const values = housingForm.getValues();
        // 頭金 >= 物件価格のバリデーション（フィールド間の制約）
        if (values.down_payment >= values.price) {
          housingForm.setError('down_payment', { message: '頭金は物件価格より少なく設定してください' });
          return;
        }
        result = { ...values, type: 'housing' };
        break;
      }
      case 'education': {
        const valid = await educationForm.trigger();
        if (!valid) return;
        result = { ...educationForm.getValues(), type: 'education' };
        break;
      }
      case 'care': {
        const valid = await careForm.trigger();
        if (!valid) return;
        result = { ...careForm.getValues(), type: 'care' };
        break;
      }
      case 'other_expense': {
        const valid = await otherForm.trigger();
        if (!valid) return;
        result = { ...otherForm.getValues(), type: 'other_expense' };
        break;
      }
    }

    if (result) {
      onSubmit(result);
      onClose();
    }
  };

  const currentType = selectedType;
  const defaultValues = initialValue ? undefined : getDefaultValues(currentType);
  void defaultValues; // 未使用変数警告を抑制

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>
        {initialValue ? 'イベントを編集' : 'イベントを追加'}
      </DialogTitle>
      <DialogContent>
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 1 }}>
          {/* 編集モードでは種別を変更できない（既存データとの整合性のため） */}
          <TextField
            select
            label="イベント種別"
            value={selectedType}
            onChange={(e) => handleTypeChange(e.target.value as EventType)}
            disabled={!!initialValue}
            fullWidth
          >
            {EVENT_TYPE_OPTIONS.map((opt) => (
              <MenuItem key={opt.value} value={opt.value}>
                {opt.label}
              </MenuItem>
            ))}
          </TextField>

          {/* 選択した種別に応じてフォームを切り替える */}
          {currentType === 'marriage' && (
            <MarriageForm register={marriageForm.register} errors={marriageForm.formState.errors} />
          )}
          {currentType === 'birth' && (
            <BirthForm register={birthForm.register} errors={birthForm.formState.errors} />
          )}
          {currentType === 'housing' && (
            <HousingForm
              register={housingForm.register}
              errors={housingForm.formState.errors}
              control={housingForm.control}
            />
          )}
          {currentType === 'education' && (
            <EducationForm
              register={educationForm.register}
              errors={educationForm.formState.errors}
              control={educationForm.control}
            />
          )}
          {currentType === 'care' && (
            <CareForm register={careForm.register} errors={careForm.formState.errors} />
          )}
          {currentType === 'other_expense' && (
            <OtherExpenseForm register={otherForm.register} errors={otherForm.formState.errors} />
          )}
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>キャンセル</Button>
        <Button variant="contained" onClick={handleSubmit}>
          {initialValue ? '保存' : '追加'}
        </Button>
      </DialogActions>
    </Dialog>
  );
}
