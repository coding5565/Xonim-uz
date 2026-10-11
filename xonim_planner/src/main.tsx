import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { XONIM } from './xonim/config'
import { XonimGate } from './xonim/XonimGate'
import { startXonim } from './xonim/sync'

// Внутри Xonim: проверка входа и загрузка данных стартуют до первой отрисовки.
if (XONIM) startXonim()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {XONIM ? (
      <XonimGate>
        <App />
      </XonimGate>
    ) : (
      <App />
    )}
  </StrictMode>,
)
