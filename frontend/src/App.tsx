import { useRef, useState, useCallback } from 'react';
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
import { ClientManager } from './components/ClientManager/ClientManager';
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

  // key-based remount: クライアント選択・新規作成・削除時に increment する
  const [formKey, setFormKey] = useState(0);

  // クライアント読み込み時のフォーム初期値
  const [defaultClient, setDefaultClient] = useState<Partial<ClientFormData> | undefined>(undefined);
  const [defaultSpouse, setDefaultSpouse] = useState<ClientFormData | null>(null);
  const [defaultCommon, setDefaultCommon] = useState<Partial<ScenarioCommonData> | undefined>(undefined);
  const [defaultExpense, setDefaultExpense] = useState<Partial<MonthlyExpensesRequest> | undefined>(undefined);

  const handleSpouseChange = (data: ClientFormData | null) => {
    spouseRef.current = data;
    setHasSpouse(data !== null);
  };

  // 現在のフォーム値から SimulateRequestBody を組み立てる
  const buildScenarioBody = useCallback((): SimulateRequestBody => ({
    client: clientRef.current,
    spouse: spouseRef.current,
    savings_initial: commonRef.current.savings_initial,
    end_age: commonRef.current.end_age,
    start_year: commonRef.current.start_year,
    monthly_expenses: expenseRef.current,
    events: events,
  }), [events]);

  // クライアント読み込み時にフォーム全体を復元する
  const handleLoadClient = (scenario: SimulateRequestBody) => {
    setDefaultClient(scenario.client);
    setDefaultSpouse(scenario.spouse);
    setDefaultCommon({
      savings_initial: scenario.savings_initial,
      end_age: scenario.end_age,
      start_year: scenario.start_year,
    });
    setDefaultExpense(scenario.monthly_expenses);
    dispatch({ type: 'SET_ALL', events: scenario.events });
    setFormKey((prev) => prev + 1);
  };

  const handleSimulate = async () => {
    const body = buildScenarioBody();
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

      {/* クライアント管理バー */}
      <ClientManager
        onLoad={handleLoadClient}
        getCurrentScenario={buildScenarioBody}
      />

      {/* key で囲んで remount する（useScenario は remount 対象外） */}
      <Box key={formKey}>
        <ClientSection
          defaultClient={defaultClient}
          defaultSpouse={defaultSpouse}
          defaultCommon={defaultCommon}
          onClientChange={(data) => { clientRef.current = data; }}
          onSpouseChange={handleSpouseChange}
          onCommonChange={(data) => { commonRef.current = data; }}
        />

        <ExpenseSection
          defaultValues={defaultExpense}
          onExpenseChange={(data) => { expenseRef.current = data; }}
        />
      </Box>

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
