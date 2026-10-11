import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig(({ mode }) => {
  // Режим «внутри Xonim» (см. src/xonim/config.ts): калькулятор живёт по адресу
  // /planner/ на сайте Xonim, а в разработке ходит в его API на порту 8000.
  const xonim = mode === 'xonim'
  // Backend Xonim на другом порту: XONIM_API_URL=http://127.0.0.1:8011 npm run dev:xonim
  const api = process.env.XONIM_API_URL ?? 'http://127.0.0.1:8000'
  return {
    base: xonim ? '/planner/' : '/',
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
    },
    server: xonim ? { port: 5174, strictPort: true, proxy: { '/api': api } } : undefined,
  }
})
