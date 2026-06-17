import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ThemeProvider, createTheme } from '@mui/material';
import { ClientManager } from '../../components/ClientManager/ClientManager';
import * as api from '../../api/client';
import type { ClientListItem, ClientResponse, SimulateRequestBody } from '../../api/types';

vi.mock('../../api/client');

const theme = createTheme();

const MOCK_SCENARIO: SimulateRequestBody = {
  client: {
    age: 35,
    annual_income: 5000000,
    income_model: 'flat',
    raise_rate: 0,
    retirement_age: 65,
    post_retirement_income: 0,
    pension_start_age: 65,
    pension_annual: 1200000,
  },
  spouse: null,
  savings_initial: 3000000,
  end_age: 90,
  start_year: 2026,
  monthly_expenses: { living: 200000, insurance: 10000, other: 0 },
  events: [],
};

const MOCK_CLIENTS: ClientListItem[] = [
  { id: 1, name: '田中', updated_at: '2026-06-17T00:00:00Z' },
  { id: 2, name: '佐藤', updated_at: '2026-06-17T01:00:00Z' },
];

const MOCK_DETAIL: ClientResponse = {
  id: 1,
  name: '田中',
  scenario: MOCK_SCENARIO,
  created_at: '2026-06-17T00:00:00Z',
  updated_at: '2026-06-17T00:00:00Z',
};

function renderWithTheme(ui: React.ReactElement) {
  return render(<ThemeProvider theme={theme}>{ui}</ThemeProvider>);
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.getClients).mockResolvedValue(MOCK_CLIENTS);
  vi.mocked(api.getClient).mockResolvedValue(MOCK_DETAIL);
  vi.mocked(api.postClient).mockResolvedValue({
    id: 3,
    name: '山田',
    scenario: MOCK_SCENARIO,
    created_at: '2026-06-17T02:00:00Z',
    updated_at: '2026-06-17T02:00:00Z',
  });
  vi.mocked(api.deleteClient).mockResolvedValue(undefined);
});

describe('ClientManager - 初期表示', () => {
  it('ドロップダウン・保存・名前を付けて保存・削除ボタンが表示される', async () => {
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    await waitFor(() => {
      // Autocomplete のテキストフィールド
      expect(screen.getByLabelText('クライアント選択')).toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: '保存' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '名前を付けて保存' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '削除' })).toBeInTheDocument();
  });

  it('クライアント未選択のとき削除ボタンが無効化されている', async () => {
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '削除' })).toBeDisabled();
    });
  });
});

describe('ClientManager - クライアント選択', () => {
  it('ドロップダウンからクライアントを選択すると onLoad が呼ばれる', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText('クライアント選択')).toBeInTheDocument();
    });

    // Autocomplete を開いてオプションを選択
    const input = screen.getByLabelText('クライアント選択');
    await user.click(input);

    await waitFor(() => {
      expect(screen.getByText('田中')).toBeInTheDocument();
    });
    await user.click(screen.getByText('田中'));

    await waitFor(() => {
      expect(onLoad).toHaveBeenCalledWith(MOCK_SCENARIO);
    });
  });
});

describe('ClientManager - 保存', () => {
  it('クライアント選択中に保存ボタンを押すと上書き保存される', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);
    vi.mocked(api.putClient).mockResolvedValue(MOCK_DETAIL);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    // まずクライアントを選択
    await waitFor(() => {
      expect(screen.getByLabelText('クライアント選択')).toBeInTheDocument();
    });
    const input = screen.getByLabelText('クライアント選択');
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText('田中')).toBeInTheDocument();
    });
    await user.click(screen.getByText('田中'));
    await waitFor(() => {
      expect(onLoad).toHaveBeenCalled();
    });

    // 保存ボタンを押す → 上書き保存（ダイアログなし）
    await user.click(screen.getByRole('button', { name: '保存' }));
    await waitFor(() => {
      expect(api.putClient).toHaveBeenCalled();
    });
  });

  it('クライアント未選択で保存ボタンを押すと SaveDialog が表示される', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '保存' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });
});

describe('ClientManager - 名前を付けて保存', () => {
  it('名前を付けて保存ボタンを押すと SaveDialog が表示される', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '名前を付けて保存' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: '名前を付けて保存' }));
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });
  });

  it('SaveDialog で名前を入力して保存するとクライアント一覧が更新される', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);
    vi.mocked(api.getClients)
      .mockResolvedValueOnce(MOCK_CLIENTS)
      .mockResolvedValueOnce([...MOCK_CLIENTS, { id: 3, name: '山田', updated_at: '2026-06-17T02:00:00Z' }]);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '名前を付けて保存' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: '名前を付けて保存' }));
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    const nameInput = screen.getByLabelText('クライアント名');
    await user.type(nameInput, '山田');

    const saveButton = screen.getByRole('button', { name: '保存する' });
    await user.click(saveButton);

    await waitFor(() => {
      expect(api.postClient).toHaveBeenCalled();
    });
  });

  it('SaveDialog で空文字のまま保存しようとすると保存されない', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '名前を付けて保存' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: '名前を付けて保存' }));
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    // 保存ボタンが disabled であること
    const saveButton = screen.getByRole('button', { name: '保存する' });
    expect(saveButton).toBeDisabled();

    expect(api.postClient).not.toHaveBeenCalled();
  });

  it('SaveDialog でキャンセルすると何も起きない', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '名前を付けて保存' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: '名前を付けて保存' }));
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'キャンセル' }));

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    });
    expect(api.postClient).not.toHaveBeenCalled();
  });
});

describe('ClientManager - 削除', () => {
  it('削除ボタンを押すと確認ダイアログが表示される', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    // まずクライアントを選択して削除ボタンを有効にする
    await waitFor(() => {
      expect(screen.getByLabelText('クライアント選択')).toBeInTheDocument();
    });
    const input = screen.getByLabelText('クライアント選択');
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText('田中')).toBeInTheDocument();
    });
    await user.click(screen.getByText('田中'));
    await waitFor(() => {
      expect(onLoad).toHaveBeenCalled();
    });

    await user.click(screen.getByRole('button', { name: '削除' }));
    await waitFor(() => {
      expect(screen.getByText('このクライアントを削除しますか？')).toBeInTheDocument();
    });
  });

  it('確認ダイアログで「はい」を押すと削除される', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    // クライアント選択
    await waitFor(() => {
      expect(screen.getByLabelText('クライアント選択')).toBeInTheDocument();
    });
    const input = screen.getByLabelText('クライアント選択');
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText('田中')).toBeInTheDocument();
    });
    await user.click(screen.getByText('田中'));
    await waitFor(() => {
      expect(onLoad).toHaveBeenCalled();
    });

    // 削除
    await user.click(screen.getByRole('button', { name: '削除' }));
    await waitFor(() => {
      expect(screen.getByText('このクライアントを削除しますか？')).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: 'はい' }));

    await waitFor(() => {
      expect(api.deleteClient).toHaveBeenCalledWith(1);
    });
  });

  it('確認ダイアログで「いいえ」を押すと削除されない', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    // クライアント選択
    await waitFor(() => {
      expect(screen.getByLabelText('クライアント選択')).toBeInTheDocument();
    });
    const input = screen.getByLabelText('クライアント選択');
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText('田中')).toBeInTheDocument();
    });
    await user.click(screen.getByText('田中'));
    await waitFor(() => {
      expect(onLoad).toHaveBeenCalled();
    });

    await user.click(screen.getByRole('button', { name: '削除' }));
    await waitFor(() => {
      expect(screen.getByText('このクライアントを削除しますか？')).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: 'いいえ' }));

    await waitFor(() => {
      expect(screen.queryByText('このクライアントを削除しますか？')).not.toBeInTheDocument();
    });
    expect(api.deleteClient).not.toHaveBeenCalled();
  });

  it('クライアント未選択のとき削除ボタンが押せない', async () => {
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '削除' })).toBeDisabled();
    });
  });
});

describe('ClientManager - エラー表示', () => {
  it('保存が失敗したらエラーメッセージが表示される', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);
    vi.mocked(api.postClient).mockRejectedValue({ kind: 'server' });

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '名前を付けて保存' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: '名前を付けて保存' }));
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument();
    });

    const nameInput = screen.getByLabelText('クライアント名');
    await user.type(nameInput, 'テスト');
    await user.click(screen.getByRole('button', { name: '保存する' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('削除が失敗したらエラーメッセージが表示される', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);
    vi.mocked(api.deleteClient).mockRejectedValue({ kind: 'server' });

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    // クライアント選択
    await waitFor(() => {
      expect(screen.getByLabelText('クライアント選択')).toBeInTheDocument();
    });
    const input = screen.getByLabelText('クライアント選択');
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText('田中')).toBeInTheDocument();
    });
    await user.click(screen.getByText('田中'));
    await waitFor(() => {
      expect(onLoad).toHaveBeenCalled();
    });

    await user.click(screen.getByRole('button', { name: '削除' }));
    await waitFor(() => {
      expect(screen.getByText('このクライアントを削除しますか？')).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: 'はい' }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });

  it('クライアント選択が失敗したらエラーメッセージが表示される', async () => {
    const user = userEvent.setup();
    const onLoad = vi.fn();
    const getCurrentScenario = vi.fn().mockReturnValue(MOCK_SCENARIO);
    vi.mocked(api.getClient).mockRejectedValue({ kind: 'not_found' });

    renderWithTheme(
      <ClientManager onLoad={onLoad} getCurrentScenario={getCurrentScenario} />,
    );

    await waitFor(() => {
      expect(screen.getByLabelText('クライアント選択')).toBeInTheDocument();
    });
    const input = screen.getByLabelText('クライアント選択');
    await user.click(input);
    await waitFor(() => {
      expect(screen.getByText('田中')).toBeInTheDocument();
    });
    await user.click(screen.getByText('田中'));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
  });
});
