// API の入出力型（バックエンドの schemas.py と 1:1 対応）

export interface ClientRequest {
  age: number;
  annual_income: number;
  income_model: 'flat' | 'raise_rate' | 'post_retirement';
  raise_rate: number;
  retirement_age: number;
  post_retirement_income: number;
  pension_start_age: number;
  pension_annual: number;
}

export interface MonthlyExpensesRequest {
  living: number;
  insurance: number;
  other: number;
}

export interface MarriageEventRequest {
  type: 'marriage';
  year: number;
  cost: number;
}

export interface BirthEventRequest {
  type: 'birth';
  year: number;
  child_count: number;
  client_maternity_rate: number;
  client_maternity_years: number;
  spouse_maternity_rate: number;
  spouse_maternity_years: number;
}

export interface HousingEventRequest {
  type: 'housing';
  year: number;
  price: number;
  down_payment: number;
  loan_years: number;
  interest_rate: number;
  use_tax_deduction: boolean;
}

export interface EducationEventRequest {
  type: 'education';
  year: number;
  child_birth_year: number;
  kindergarten: 'public' | 'private';
  elementary: 'public' | 'private';
  junior_high: 'public' | 'private';
  high_school: 'public' | 'private';
  university: 'public' | 'private';
}

export interface CareEventRequest {
  type: 'care';
  year: number;
  duration_years: number;
  monthly_cost: number;
}

export interface OtherExpenseEventRequest {
  type: 'other_expense';
  year: number;
  amount: number;
  name: string;
}

export type EventRequest =
  | MarriageEventRequest
  | BirthEventRequest
  | HousingEventRequest
  | EducationEventRequest
  | CareEventRequest
  | OtherExpenseEventRequest;

export interface SimulateRequestBody {
  client: ClientRequest;
  spouse: ClientRequest | null;
  savings_initial: number;
  end_age: number;
  start_year: number;
  monthly_expenses: MonthlyExpensesRequest;
  events: EventRequest[];
}

export interface CashFlowRowResponse {
  year: number;
  age_client: number;
  age_spouse: number | null;
  income_total: number;
  expense_total: number;
  loan_deduction: number;
  net: number;
  savings: number;
  events_label: string;
}

// エラーは discriminated union 型で管理（ネットワーク / タイムアウト / バリデーション / サーバー）
export type SimulateError =
  | { kind: 'network' }
  | { kind: 'timeout' }
  | { kind: 'validation'; detail: string }
  | { kind: 'server' };

// ---------------------------------------------------------------------------
// ep4.4: PDF ダウンロード・FP コメント生成の型
// ---------------------------------------------------------------------------

export interface DownloadPdfRequestBody {
  scenario: SimulateRequestBody;
  rows: CashFlowRowResponse[];
  fp_comment: string;
}

export interface GenerateCommentRequestBody {
  scenario: SimulateRequestBody;
  rows: CashFlowRowResponse[];
}

export interface GenerateCommentResponse {
  comment: string;
}

export type DownloadError =
  | { kind: 'network' }
  | { kind: 'timeout' }
  | { kind: 'server' };

// ---------------------------------------------------------------------------
// ep4.5: クライアント管理 CRUD の型
// ---------------------------------------------------------------------------

// GET /clients の一覧要素
export interface ClientListItem {
  id: number;
  name: string;
  updated_at: string; // ISO 8601
}

// GET /clients/{id}, POST /clients, PUT /clients/{id} のレスポンス
export interface ClientResponse {
  id: number;
  name: string;
  scenario: SimulateRequestBody;
  created_at: string;
  updated_at: string;
}

// POST /clients, PUT /clients/{id} のリクエストボディ
export interface SaveClientBody {
  name: string;
  scenario: SimulateRequestBody;
}

// クライアント CRUD 操作のエラー（既存の discriminated union パターンに合わせる）
export type ClientError =
  | { kind: 'network' }
  | { kind: 'timeout' }
  | { kind: 'not_found' }
  | { kind: 'validation'; detail: string }
  | { kind: 'server' };
