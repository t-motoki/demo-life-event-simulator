import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  // file:// プロトコル対応: Electron 本番ビルドではアセットパスを相対パスにする必要がある
  base: './',
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/setupTests.ts'],
    pool: 'vmThreads',
  },
})
