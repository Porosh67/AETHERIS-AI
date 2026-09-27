import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { copyFileSync, existsSync } from 'fs'
import { resolve } from 'path'

/** Copy index.html → 404.html so Vercel SPA hard-refresh never shows the platform 404. */
function spaFallback404() {
  return {
    name: 'spa-fallback-404',
    closeBundle() {
      const index = resolve(__dirname, 'dist/index.html')
      const notFound = resolve(__dirname, 'dist/404.html')
      if (existsSync(index)) copyFileSync(index, notFound)
    },
  }
}

export default defineConfig({
  plugins: [react(), spaFallback404()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})