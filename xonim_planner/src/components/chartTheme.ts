import { money } from '@/core/format'
import { useAppStore } from '@/store/useAppStore'

export const CHART_COLORS = {
  revenue: '#10b981',
  cogs: '#f43f5e',
  payroll: '#f59e0b',
  variable: '#8b5cf6',
  fixed: '#64748b',
  profit: '#059669',
  loss: '#e11d48',
  accent: '#0ea5e9',
}

/** Палитра для круговых диаграмм — контрастная и стабильная по порядку. */
export const PIE_COLORS = [
  '#10b981',
  '#0ea5e9',
  '#8b5cf6',
  '#f59e0b',
  '#f43f5e',
  '#14b8a6',
  '#6366f1',
  '#ec4899',
  '#84cc16',
  '#64748b',
]

export function useChartTheme() {
  const theme = useAppStore((s) => s.theme)
  const dark = theme === 'dark'
  return {
    dark,
    axis: dark ? '#94a3b8' : '#64748b',
    grid: dark ? '#1e293b' : '#e2e8f0',
    tooltip: {
      backgroundColor: dark ? '#0f172a' : '#ffffff',
      border: `1px solid ${dark ? '#1e293b' : '#e2e8f0'}`,
      borderRadius: 12,
      fontSize: 12,
      color: dark ? '#e2e8f0' : '#0f172a',
      boxShadow: '0 8px 24px rgba(15,23,42,0.12)',
    } as React.CSSProperties,
  }
}

/* Обёртки для подписей recharts: библиотека типизирует значения широко,
   поэтому принимаем unknown и приводим к числу сами. */
export function tooltipMoney(currency: string, label?: string) {
  return (value: unknown, name?: unknown): [string, string] => [
    money(Number(value), currency),
    label ?? String(name ?? ''),
  ]
}

export function tooltipLabel(fn: (v: number) => string) {
  return (label: unknown): string => fn(Number(label))
}
