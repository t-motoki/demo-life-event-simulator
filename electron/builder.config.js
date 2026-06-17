module.exports = {
  appId: 'com.life-event-simulator',
  productName: 'ライフイベント家計シミュレーター',
  directories: {
    output: '../output/electron-dist',
  },
  files: ['main.js', 'preload.js'],
  extraResources: [
    {
      from: '../frontend/dist',
      to: 'frontend',
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
