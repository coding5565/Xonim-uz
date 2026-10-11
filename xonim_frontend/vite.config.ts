import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/media': 'http://127.0.0.1:8000',
      // Kalkulyator alohida dev-serverda: xonim_planner ichida `npm run dev:xonim`.
      '/planner': { target: 'http://127.0.0.1:5174', ws: true },
    },
  },
})
