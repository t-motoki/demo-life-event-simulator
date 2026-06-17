# 設計: ep4.5 Phase 3 — Electron デスクトップアプリ化

## 概要

life-event-simulator を Electron シェルで包み、Windows .exe インストーラーとして配布する。
FastAPI サーバーは PyInstaller で単一 .exe にバンドルし、Electron メインプロセスから spawn する。

---

## 変更ファイル一覧

| ファイル | 変更種別 | 理由 |
| -------- | -------- | ---- |
| `electron/package.json` | 新規 | Electron + electron-builder 依存、scripts 定義 |
| `electron/main.js` | 新規 | メインプロセス（ポート確保・API spawn・BrowserWindow） |
| `electron/preload.js` | 新規 | contextBridge で apiBaseUrl を renderer に公開 |
| `electron/builder.config.js` | 新規 | electron-builder の Windows NSIS 設定 |
| `api-server.spec` | 新規 | PyInstaller ビルド設定（プロジェクトルート） |
| `frontend/vite.config.ts` | 変更 | `base: './'` 追加（file:// プロトコル対応） |
| `frontend/src/api/client.ts` | 変更 | `window.electronAPI?.apiBaseUrl` を BASE_URL の最優先に |
| `requirements.txt` | 変更 | `pyinstaller` 追加 |

---

## データモデル

新しいエンティティ・値オブジェクトの追加なし。

---

## インターフェース

### `electron/preload.js` が公開する API

```typescript
// renderer プロセスから参照可能
interface ElectronAPI {
  apiBaseUrl: string;  // 例: "http://127.0.0.1:51234"
}

// window.electronAPI としてアクセス
declare global {
  interface Window {
    electronAPI?: ElectronAPI;
  }
}
```

### `electron/main.js` の内部関数

```javascript
// 空きポートを取得する（OS に選ばせる）
async function findFreePort(): Promise<number>

// api-server プロセスを起動し、/health が応答するまで待つ
async function startApiServer(port: number): Promise<ChildProcess>

// /health エンドポイントをポーリングする
async function waitForHealth(port: number, maxRetries: number, intervalMs: number): Promise<void>

// api-server プロセスを停止する（SIGTERM → タイムアウト後 SIGKILL）
async function stopApiServer(proc: ChildProcess): Promise<void>
```

---

## 依存関係

```
electron/main.js
  ├── Node.js 標準: net, child_process, path, http
  ├── electron: app, BrowserWindow
  └── 外部依存なし

electron/preload.js
  └── electron: contextBridge, ipcRenderer（ipcRenderer は現時点では不使用だが型定義のみ）

frontend/src/api/client.ts
  └── window.electronAPI（preload.js が公開）

api-server.exe
  └── src/api/main.py（既存。LES_PORT, LES_DB_PATH, LES_CORS_ORIGINS を環境変数で受け取る）
```

**依存の方向**: Electron → FastAPI は spawn（プロセス間通信）。コード上の import 依存はない。
**Frontend → Electron**: `window.electronAPI` の存在チェックのみ。Electron がなくても動く（フォールバック）。

---

## 設計の詳細

### 1. `electron/package.json`

```jsonc
{
  "name": "life-event-simulator",
  "version": "1.0.0",
  "main": "main.js",
  "scripts": {
    "dev": "electron .",
    "build": "electron-builder --config builder.config.js"
  },
  "dependencies": {
    "electron": "^36.0.0"
  },
  "devDependencies": {
    "electron-builder": "^26.0.0"
  }
}
```

**注意**: `electron` は `dependencies`（`devDependencies` ではない）。electron-builder がパッケージング時に参照するため。

### 2. `electron/main.js` — メインプロセス

#### 2.1 開発モード vs 本番モードの判定

```javascript
const isDev = !app.isPackaged;
```

`app.isPackaged` は electron-builder でパッケージされた場合に `true` を返す。`NODE_ENV` より確実。

#### 2.2 空きポート確保

```javascript
async function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on('error', reject);
  });
}
```

`listen(0)` で OS に空きポートを選ばせる。ポート範囲を 49152-65535 に制限する必要はない（OS が ephemeral port を割り当てる）。

**`listen(0)` と `close()` の間にポートが奪われるリスク**: 理論上あるが、実用上は無視できる（数ミリ秒の窓）。SO_REUSEADDR を使う複雑な方式はオーバーエンジニアリング。

#### 2.3 API サーバーの起動

```javascript
async function startApiServer(port) {
  const env = {
    ...process.env,
    LES_PORT: String(port),
    LES_DB_PATH: path.join(app.getPath('userData'), 'clients.db'),
    LES_CORS_ORIGINS: '*',
  };

  let proc;
  if (isDev) {
    // 開発モード: Python を直接実行
    proc = spawn('python', ['-m', 'uvicorn', 'src.api.main:app', '--port', String(port)], {
      cwd: path.resolve(__dirname, '..'),
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } else {
    // 本番モード: PyInstaller でバンドルした exe
    const exePath = path.join(process.resourcesPath, 'api-server', 'api-server.exe');
    proc = spawn(exePath, [], {
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  }

  // ログ出力
  proc.stdout.on('data', (data) => { /* ロガーへ */ });
  proc.stderr.on('data', (data) => { /* ロガーへ */ });

  await waitForHealth(port, 30, 1000);
  return proc;
}
```

**環境変数の設計判断**:
- `LES_PORT`: `src/api/main.py` が既に対応済み（L42: `int(os.environ.get("LES_PORT", "49152"))`）
- `LES_DB_PATH`: `src/api/dependencies.py` で参照する（Phase 1 で実装済みの前提。未対応なら変更が必要）
- `LES_CORS_ORIGINS`: `src/api/main.py` L21 で対応済み。`*` を渡すことで file:// origin を許可

**`LES_CORS_ORIGINS=*` の根拠**: Electron 本番ビルドでは `file://` プロトコルから API にアクセスする。`file://` は origin が `null` になるブラウザもあるため、特定 origin を指定するより `*` が安全。通信は `127.0.0.1` のみであり、外部からアクセスできないためセキュリティリスクは低い。

#### 2.4 ヘルスチェック

```javascript
async function waitForHealth(port, maxRetries, intervalMs) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(`http://127.0.0.1:${port}/health`, (res) => {
          if (res.statusCode === 200) resolve();
          else reject(new Error(`status ${res.statusCode}`));
        });
        req.on('error', reject);
        req.setTimeout(2000, () => { req.destroy(); reject(new Error('timeout')); });
      });
      return; // 成功
    } catch {
      await new Promise(r => setTimeout(r, intervalMs));
    }
  }
  throw new Error(`API server did not start within ${maxRetries * intervalMs / 1000}s`);
}
```

Node.js 標準の `http` モジュールを使う。`node-fetch` や `axios` は不要。

#### 2.5 BrowserWindow

```javascript
async function createWindow(port) {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, '..', 'frontend', 'dist', 'index.html'));
  }
}
```

**開発モード**: Vite dev server（`http://localhost:5173`）を読み込む。HMR が効く。
**本番モード**: ビルド済み `frontend/dist/index.html` を file:// で読み込む。

#### 2.6 プロセスのライフサイクル

```javascript
let apiProcess = null;

app.whenReady().then(async () => {
  const port = await findFreePort();
  apiProcess = await startApiServer(port);
  await createWindow(port);
});

app.on('window-all-closed', async () => {
  if (apiProcess) {
    await stopApiServer(apiProcess);
  }
  app.quit();
});

async function stopApiServer(proc) {
  return new Promise((resolve) => {
    proc.on('close', resolve);
    proc.kill('SIGTERM');
    setTimeout(() => {
      if (!proc.killed) proc.kill('SIGKILL');
      resolve();
    }, 3000);
  });
}
```

**Windows での SIGTERM**: Windows では `SIGTERM` は `proc.kill()` と同等（プロセスを終了する）。`SIGKILL` フォールバックは Linux/macOS 向け。Windows でも `proc.killed` チェックで安全に動作する。

### 3. `electron/preload.js`

```javascript
const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  apiBaseUrl: process.argv.find(arg => arg.startsWith('--api-port='))
    ? `http://127.0.0.1:${process.argv.find(arg => arg.startsWith('--api-port=')).split('=')[1]}`
    : 'http://127.0.0.1:49152',
});
```

**ポートの渡し方**: main.js が BrowserWindow 生成時に `additionalArguments: ['--api-port=' + port]` を webPreferences に指定する。preload.js が `process.argv` から読み取る。

**選ばなかった方式**:
- IPC（`ipcMain.handle` + `ipcRenderer.invoke`）: 非同期になり、client.ts 側で await が必要。BASE_URL は同期的に参照したい
- 環境変数: preload.js では `process.env` にカスタム値を渡す標準的な方法がない

### 4. `electron/builder.config.js`

```javascript
module.exports = {
  appId: 'com.life-event-simulator',
  productName: 'ライフイベント家計シミュレーター',
  directories: {
    output: '../output/electron-dist',
  },
  files: [
    'main.js',
    'preload.js',
  ],
  extraResources: [
    {
      from: '../frontend/dist',
      to: 'frontend/dist',
    },
    {
      from: '../dist/api-server',
      to: 'api-server',
    },
  ],
  win: {
    target: 'nsis',
  },
  nsis: {
    oneClick: false,
    perMachine: false,
    allowToChangeInstallationDirectory: true,
  },
};
```

**`extraResources` vs `files`**:
- `files`: asar アーカイブに含まれる（Electron コードのみ）
- `extraResources`: asar 外に配置される（api-server.exe はバイナリなので asar に入れられない）

**パス解決（本番）**: `process.resourcesPath` で extraResources のルートを取得できる。

### 5. `frontend/vite.config.ts` の変更

```diff
 export default defineConfig({
+  base: './',
   plugins: [react()],
```

**理由**: Electron 本番ビルドでは `file://` プロトコルで index.html を読み込む。`base: '/'`（デフォルト）だと、アセットのパスが `/assets/index-xxx.js` になり、`file:///assets/index-xxx.js` に解決されて見つからない。`'./'` にすると相対パス `./assets/index-xxx.js` になり正しく解決される。

**ブラウザ開発モードへの影響**: なし。Vite dev server は `base` に関係なく正しく配信する。

### 6. `frontend/src/api/client.ts` の変更

```diff
-const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';
+const BASE_URL =
+  window.electronAPI?.apiBaseUrl
+  ?? import.meta.env.VITE_API_URL
+  ?? 'http://localhost:8000';
```

**優先順位**:
1. `window.electronAPI.apiBaseUrl` — Electron 本番/開発（preload.js が公開）
2. `import.meta.env.VITE_API_URL` — ブラウザ開発で API ポートを変えたい場合
3. `'http://localhost:8000'` — ブラウザ開発のデフォルト

**TypeScript の型定義**: `window.electronAPI` の型を `frontend/src/global.d.ts`（または `vite-env.d.ts`）に追加する。

```typescript
// frontend/src/global.d.ts
interface Window {
  electronAPI?: {
    apiBaseUrl: string;
  };
}
```

### 7. PyInstaller 設定

#### `api-server.spec`（プロジェクトルート）

```python
a = Analysis(
    ['src/api/main.py'],
    pathex=['.'],
    hiddenimports=[
        'uvicorn.logging',
        'uvicorn.loops.auto',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan.on',
        'src.api.routes.health',
        'src.api.routes.simulate',
        'src.api.routes.clients',
        'src.api.routes.comment',
        'src.api.routes.pdf',
        'src.db.sqlite_repository',
    ],
    datas=[
        ('src/output/templates', 'src/output/templates'),  # HTML テンプレート
    ],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name='api-server', console=True)
```

**`--onefile` vs `--onedir`**:
- `--onefile`（`EXE(..., a.binaries, a.datas, ...)`）: 単一 .exe、起動時に一時ディレクトリに展開するため起動が遅い（3-10秒追加）
- `--onedir`（`COLLECT` を使う）: ディレクトリにファイルが散らばるが起動が速い

**推奨: `--onedir`** にする。理由:
- 起動速度が重要（ユーザーがアプリを起動するたびに待たされる）
- electron-builder の `extraResources` でディレクトリごと含められる
- .exe 単体で配布するわけではない（Electron インストーラーに含まれる）

修正版:
```python
a = Analysis(...)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, name='api-server', console=True)
coll = COLLECT(exe, a.binaries, a.datas, name='api-server')
```

#### WeasyPrint の Windows 対応

**問題**: WeasyPrint は libpango, libcairo, libgdk-pixbuf 等の C ライブラリに依存する。Linux/macOS では `apt install` / `brew install` で導入できるが、Windows では GTK ランタイムのインストールが必要で、PyInstaller でのバンドルが困難。

**対策（段階的）**:

1. **まず WeasyPrint なしでビルドを試みる**: `api-server.spec` の `hiddenimports` から WeasyPrint 関連を除外し、`pdf.py` ルートは含めるが、WeasyPrint の import は遅延 import（既に `from weasyprint import HTML` が関数内にある）なので、PDF 生成を呼ばなければエラーにならない。

2. **PDF 機能の Graceful Degradation**: `src/api/routes/pdf.py` の `download_pdf_endpoint` で `ImportError` をキャッチし、HTTP 501 (Not Implemented) を返す。フロントエンドで「デスクトップ版では PDF ダウンロードは利用できません」と表示する。

3. **将来的な対策（今は実装しない）**: WeasyPrint を別のPDF ライブラリ（fpdf2, reportlab）に置き換える。または GTK ランタイムを extraResources に含める。

**推奨**: 対策 1 + 2 を採用。WeasyPrint の import は `src/output/pdf_writer.py` L46 で関数内 import になっているため、呼ばなければ問題ない。ルーティングレベルで ImportError を捕捉するのが最小変更。

---

## 設計判断の根拠

### なぜ Electron か

| 選択肢 | メリット | デメリット | 判定 |
| ------ | ------- | --------- | ---- |
| **Electron** | VS Code と同じ仕組み。React をそのまま使える。実績豊富 | バンドルサイズが大きい（約150MB） | 採用 |
| Tauri | バンドルサイズ小（約10MB）。Rust ベース | Rust ツールチェーンが必要。React 連携は可能だが実績が少ない | 不採用 |
| CEF (Chromium Embedded Framework) | 軽量 | Python バインディングが不安定。ビルドが複雑 | 不採用 |

Electron を選ぶ理由: 動画で「VS Code と同じ仕組み」と説明できるストーリー上の利点がある。バンドルサイズの大きさは許容範囲（VS Code も同程度）。

### なぜ `--onedir` か

起動速度 > 配布の手軽さ。Electron インストーラーに含めるため、単一 .exe である必要がない。

### なぜ `additionalArguments` でポートを渡すか

preload.js にポートを渡す方法として以下を検討した:

| 方式 | 同期/非同期 | 複雑さ |
| ---- | ---------- | ------ |
| `additionalArguments` | 同期 | 低 |
| IPC (`ipcMain.handle`) | 非同期 | 中（renderer 側で await が必要） |
| ファイル書き出し | 同期 | 中（ファイル I/O） |

BASE_URL はモジュールトップレベルで定義される定数であり、同期的に決まる必要がある。`additionalArguments` が最もシンプル。

### なぜ CORS に `*` を使うか

Electron 本番ビルドでは origin が `file://` または `null` になる。特定 origin をリストアップするより `*` が確実。通信先は `127.0.0.1` のみであり、外部ネットワークからのアクセスは不可能なためセキュリティリスクは無視できる。

---

## 実装者へのノート

### 開発モードの起動手順

3つのプロセスを別ターミナルで起動する:

```bash
# 1. API サーバー
cd /home/tmotoki/pjt/life-event-simulator
LES_PORT=49152 python -m uvicorn src.api.main:app --port 49152

# 2. Vite dev server
cd /home/tmotoki/pjt/life-event-simulator/frontend
npm run dev

# 3. Electron
cd /home/tmotoki/pjt/life-event-simulator/electron
npm run dev
```

開発モードでは Electron が API サーバーを自動起動するので、手順 1 は不要（Electron が spawn する）。ただし Electron なしで開発したい場合は手順 1 + 2 だけでブラウザ開発が可能。

### LES_DB_PATH の対応確認

`src/api/dependencies.py`（または DB 接続を初期化しているファイル）が `LES_DB_PATH` 環境変数を参照しているか確認すること。Phase 1 で `LES_DB_PATH` 対応が未実装の場合、以下の変更が必要:

```python
db_path = os.environ.get("LES_DB_PATH", "clients.db")
```

### TypeScript 型定義の追加

`window.electronAPI` の型を追加するファイルが必要。既存の `vite-env.d.ts` に追記するか、`global.d.ts` を新規作成する。

### PyInstaller の hiddenimports

FastAPI + uvicorn は動的 import が多い。ビルド後に `ModuleNotFoundError` が出たら `hiddenimports` に追加する。特に以下に注意:

- `uvicorn.logging`
- `uvicorn.loops.auto`
- `uvicorn.protocols.http.auto`
- `email.mime.multipart`（FastAPI 内部）
- `sqlalchemy.dialects.sqlite`

### Windows での SIGTERM

Windows には POSIX シグナルがない。Node.js の `proc.kill('SIGTERM')` は Windows では `TerminateProcess()` を呼ぶ。したがって SIGTERM → 3秒待ち → SIGKILL のフォールバックは Linux/macOS でのみ意味がある。Windows では最初の `kill()` で即座にプロセスが終了する。

### ビルド順序

```bash
# 1. Frontend ビルド
cd frontend && npm run build

# 2. PyInstaller ビルド
cd .. && pyinstaller api-server.spec --distpath dist

# 3. Electron ビルド
cd electron && npm run build
```

この順序は厳守。electron-builder が `frontend/dist/` と `dist/api-server/` の存在を前提とするため。
