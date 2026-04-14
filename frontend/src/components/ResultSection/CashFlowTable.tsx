import {
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
} from '@mui/material';
import type { CashFlowRowResponse } from '../../api/types';

interface Props {
  rows: CashFlowRowResponse[];
  hasSpouse: boolean;
}

export function CashFlowTable({ rows, hasSpouse }: Props) {
  return (
    <TableContainer component={Paper}>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>年</TableCell>
            <TableCell>年齢</TableCell>
            {/* 配偶者なしのシナリオでは列を表示しない */}
            {hasSpouse && <TableCell>配偶者年齢</TableCell>}
            <TableCell align="right">収入合計</TableCell>
            <TableCell align="right">支出合計</TableCell>
            <TableCell align="right">住宅ローン控除</TableCell>
            <TableCell align="right">年間収支</TableCell>
            <TableCell align="right">貯蓄残高</TableCell>
            <TableCell>イベント</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((row) => {
            const negativeSavings = row.savings < 0;
            const negativeNet = row.net < 0;
            return (
              <TableRow
                key={row.year}
                // テストから参照しやすいように data 属性で状態を表現する
                data-negative-savings={negativeSavings ? 'true' : undefined}
                sx={negativeSavings ? { backgroundColor: '#ffebee' } : undefined}
              >
                <TableCell>{row.year}</TableCell>
                <TableCell>{row.age_client}</TableCell>
                {hasSpouse && <TableCell>{row.age_spouse ?? '—'}</TableCell>}
                <TableCell align="right">{row.income_total.toLocaleString()}</TableCell>
                <TableCell align="right">{row.expense_total.toLocaleString()}</TableCell>
                <TableCell align="right">{row.loan_deduction.toLocaleString()}</TableCell>
                <TableCell
                  align="right"
                  data-negative-net={negativeNet ? 'true' : undefined}
                  sx={negativeNet ? { color: 'error.main' } : undefined}
                >
                  {row.net.toLocaleString()}
                </TableCell>
                <TableCell
                  align="right"
                  sx={
                    negativeSavings
                      ? { color: 'error.main', fontWeight: 'bold' }
                      : undefined
                  }
                >
                  {row.savings.toLocaleString()}
                </TableCell>
                <TableCell>{row.events_label}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
