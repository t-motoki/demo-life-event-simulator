import type { LifeEvent } from '../types/scenario';

// 将来的な表示変更（単位・桁区切り）を 1 箇所に集約する
export function formatCurrency(amount: number): string {
  return amount.toLocaleString('ja-JP') + ' 円';
}

// EventCard のサマリー表示用の純粋関数
// 種別追加時の変更がここ 1 箇所に集まる
export function formatEventSummary(event: LifeEvent): string {
  switch (event.type) {
    case 'marriage':
      return `結婚（${event.year}年・費用 ${formatCurrency(event.cost)}）`;
    case 'birth':
      return `出産（${event.year}年・${event.child_count}人）`;
    case 'housing':
      return `住宅購入（${event.year}年・${formatCurrency(event.price)}）`;
    case 'education':
      return `教育（${event.year}年・${event.child_birth_year}年生まれ）`;
    case 'care':
      return `介護（${event.year}年・${event.duration_years}年間）`;
    case 'other_expense':
      return `その他（${event.year}年・${event.name || '名称なし'}・${formatCurrency(event.amount)}）`;
  }
}
