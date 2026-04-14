// フロントエンド内部のドメイン型（フォームの入力値・ライフイベントリスト）

export type IncomeModel = 'flat' | 'raise_rate' | 'post_retirement';
export type SchoolType = 'public' | 'private';

export interface ClientFormData {
  age: number;
  annual_income: number;
  income_model: IncomeModel;
  raise_rate: number;
  retirement_age: number;
  post_retirement_income: number;
  pension_start_age: number;
  pension_annual: number;
}

// シナリオ全体の共通情報（本人・配偶者以外）
export interface ScenarioCommonData {
  savings_initial: number;
  end_age: number;
  start_year: number;
}

// ライフイベントは API 型と同一にして変換コストをゼロにする
export interface MarriageEvent {
  type: 'marriage';
  year: number;
  cost: number;
}

export interface BirthEvent {
  type: 'birth';
  year: number;
  child_count: number;
  client_maternity_rate: number;
  client_maternity_years: number;
  spouse_maternity_rate: number;
  spouse_maternity_years: number;
}

export interface HousingEvent {
  type: 'housing';
  year: number;
  price: number;
  down_payment: number;
  loan_years: number;
  interest_rate: number;
  use_tax_deduction: boolean;
}

export interface EducationEvent {
  type: 'education';
  year: number;
  child_birth_year: number;
  kindergarten: SchoolType;
  elementary: SchoolType;
  junior_high: SchoolType;
  high_school: SchoolType;
  university: SchoolType;
}

export interface CareEvent {
  type: 'care';
  year: number;
  duration_years: number;
  monthly_cost: number;
}

export interface OtherExpenseEvent {
  type: 'other_expense';
  year: number;
  amount: number;
  name: string;
}

export type LifeEvent =
  | MarriageEvent
  | BirthEvent
  | HousingEvent
  | EducationEvent
  | CareEvent
  | OtherExpenseEvent;
