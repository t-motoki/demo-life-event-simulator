const { app, BrowserWindow } = require('electron');
const { spawn } = require('child_process');
const net = require('net');
const http = require('http');
const path = require('path');

const isDev = !app.isPackaged;

let apiProcess = null;

// OS に空きポートを選ばせる
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

// /health エンドポイントをポーリングして API サーバーの起動を待つ
async function waitForHealth(port, maxRetries = 30, intervalMs = 1000) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      await new Promise((resolve, reject) => {
        const req = http.get(`http://127.0.0.1:${port}/health`, (res) => {
          if (res.statusCode === 200) resolve();
          else reject(new Error(`status ${res.statusCode}`));
        });
        req.on('error', reject);
        req.setTimeout(2000, () => {
          req.destroy();
          reject(new Error('timeout'));
        });
      });
      return;
    } catch {
      await new Promise((r) => setTimeout(r, intervalMs));
    }
  }
  throw new Error(
    `API サーバーが ${(maxRetries * intervalMs) / 1000} 秒以内に起動しませんでした`,
  );
}

// API サーバーを起動し、/health が応答するまで待つ
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
    proc = spawn(
      'python',
      ['-m', 'uvicorn', 'src.api.main:app', '--port', String(port)],
      {
        cwd: path.resolve(__dirname, '..'),
        env,
        stdio: ['ignore', 'pipe', 'pipe'],
      },
    );
  } else {
    // 本番モード: PyInstaller でバンドルしたバイナリ
    const exePath = path.join(
      process.resourcesPath,
      'api-server',
      'api-server',
    );
    proc = spawn(exePath, [], {
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  }

  proc.stdout.on('data', (data) => {
    console.log(`[api] ${data}`);
  });
  proc.stderr.on('data', (data) => {
    console.error(`[api] ${data}`);
  });
  proc.on('error', (err) => {
    console.error('API サーバーの起動に失敗しました:', err.message);
  });

  await waitForHealth(port);
  return proc;
}

// API サーバーを停止する（SIGTERM → 3秒後に SIGKILL）
async function stopApiServer(proc) {
  return new Promise((resolve) => {
    if (!proc || proc.killed) {
      resolve();
      return;
    }
    proc.on('close', resolve);
    proc.kill('SIGTERM');
    setTimeout(() => {
      if (!proc.killed) proc.kill('SIGKILL');
      resolve();
    }, 3000);
  });
}

async function createWindow(port) {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      additionalArguments: [`--api-port=${port}`],
    },
  });

  if (isDev) {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(
      path.join(process.resourcesPath, 'frontend', 'index.html'),
    );
  }
}

app.whenReady().then(async () => {
  try {
    const port = await findFreePort();
    apiProcess = await startApiServer(port);
    await createWindow(port);
  } catch (err) {
    console.error('起動エラー:', err.message);
    app.quit();
  }
});

app.on('window-all-closed', async () => {
  if (apiProcess) {
    await stopApiServer(apiProcess);
  }
  app.quit();
});
