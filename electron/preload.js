const { contextBridge } = require('electron');

// main.js が additionalArguments で渡した --api-port=XXXXX を解析する
const portArg = process.argv.find((arg) => arg.startsWith('--api-port='));
const port = portArg ? portArg.split('=')[1] : '49152';

contextBridge.exposeInMainWorld('electronAPI', {
  apiBaseUrl: `http://127.0.0.1:${port}`,
});
