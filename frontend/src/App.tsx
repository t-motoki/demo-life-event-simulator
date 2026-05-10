import { useRef, useState } from 'react';
import { HashRouter, Routes, Route } from 'react-router-dom';
import {
  ThemeProvider,
  createTheme,
  CssBaseline,
  Container,
  Box,
  Typography,
  Alert,
} from '@mui/material';
import { ClientSection } from './components/ClientSection/ClientSection';
import { ExpenseSection } from './components/ExpenseSection/ExpenseSection';
import { EventSection } from './components/EventSection/EventSection';
import { SimulateButton } from './components/SimulateButton';
import { ResultSection } from './components/ResultSection/ResultSection';
import { useSimulate } from './hooks/useSimulate';
import { useScenario } from './hooks/useScenario';
import type { ClientFormData, ScenarioCommonData } from './types/scenario';
import type { MonthlyExpensesRequest, SimulateRequestBody } from './api/types';

const theme = createTheme();

function SimulatorPage() {
  const { loading, result, error, simulate } = useSimulate();
  const { events, dispatch } = useScenario();

  // 各フォームの最新値をここで保持する（フォームは子コンポーネントが管理）
  const clientRef = useRef<ClientFormData>({
    age: 0,
    annual_income: 0,
    income_model: 'flat',
    raise_rate: 0,
    retirement_age: 65,
    post_retirement_income: 0,
    pension_start_age: 65,
    pension_annual: 0,
  });
  const spouseRef = useRef<ClientFormData | null>(null);
  const commonRef = useRef<ScenarioCommonData>({
    savings_initial: 0,
    end_age: 90,
    start_year: new Date().getFullYear(),
  });
  const expenseRef = useRef<MonthlyExpensesRequest>({
    living: 0,
    insurance: 0,
    other: 0,
  });

  // 配偶者の有無（結果テーブルの列表示制御に使う）
  const [hasSpouse, setHasSpouse] = useState(false);

  // PDF ダウンロード用に最後に実行したシナリオを保持する
  const [lastScenarioBody, setLastScenarioBody] = useState<SimulateRequestBody | null>(null);

  const handleSpouseChange = (data: ClientFormData | null) => {
    spouseRef.current = data;
    setHasSpouse(data !== null);
  };

  const handleSimulate = async () => {
    const body: SimulateRequestBody = {
      client: clientRef.current,
      spouse: spouseRef.current,
      savings_initial: commonRef.current.savings_initial,
      end_age: commonRef.current.end_age,
      start_year: commonRef.current.start_year,
      monthly_expenses: expenseRef.current,
      // LifeEvent と EventRequest は同一型なので変換不要
      events: events,
    };
    setLastScenarioBody(body);
    await simulate(body);
  };

  // エラーメッセージを SimulateError から人間が読めるテキストに変換する
  const errorMessage = (() => {
    if (!error) return null;
    switch (error.kind) {
      case 'network': return 'サーバーに接続できません。バックエンドが起動しているか確認してください。';
      case 'timeout': return '応答がありませんでした。時間をおいて再試行してください。';
      case 'validation': return error.detail;
      case 'server': return 'サーバーでエラーが発生しました。';
    }
  })();

  return (
    <Container maxWidth="lg" sx={{ py: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        ライフイベント家計シミュレーター
      </Typography>

      <ClientSection
        onClientChange={(data) => { clientRef.current = data; }}
        onSpouseChange={handleSpouseChange}
        onCommonChange={(data) => { commonRef.current = data; }}
      />

      <ExpenseSection
        onExpenseChange={(data) => { expenseRef.current = data; }}
      />

      <EventSection events={events} dispatch={dispatch} />

      <Box sx={{ mt: 3, mb: 2 }}>
        <SimulateButton loading={loading} onClick={handleSimulate} />
      </Box>

      {errorMessage && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {errorMessage}
        </Alert>
      )}

      <ResultSection result={result} hasSpouse={hasSpouse} scenarioBody={lastScenarioBody} />
    </Container>
  );
}

function App() {
  return (
    // HashRouter を使う理由: Electron の file:// プロトコルで BrowserRouter は動作しない
    <HashRouter>
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Routes>
          <Route path="/" element={<SimulatorPage />} />
        </Routes>
      </ThemeProvider>
    </HashRouter>
  );
}

export default App;
