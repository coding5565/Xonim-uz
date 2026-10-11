import type { ReactNode } from 'react'
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { cx } from './cx'
import { pct } from '@/core/format'

export type KpiTone = 'neutral' | 'good' | 'warn' | 'bad' | 'brand'

const TONE_VALUE: Record<KpiTone, string> = {
  neutral: 'text-slate-900 dark:text-slate-50',
  brand: 'text-brand-600 dark:text-brand-400',
  good: 'text-emerald-600 dark:text-emerald-400',
  warn: 'text-amber-600 dark:text-amber-400',
  bad: 'text-rose-600 dark:text-rose-400',
}

/**
 * Карточка показателя. `delta` — изменение относительно базовой модели в %,
 * показывается только когда включён сценарий или симулятор.
 */
export function Kpi({
  label,
  value,
  sub,
  tone = 'neutral',
  delta,
  deltaGoodWhen = 'up',
  icon,
  hint,
}: {
  label: string
  value: string
  sub?: ReactNode
  tone?: KpiTone
  delta?: number | null
  deltaGoodWhen?: 'up' | 'down'
  icon?: ReactNode
  hint?: string
}) {
  return (
    <div className="card card-pad" title={hint}>
      <div className="flex items-start justify-between gap-2">
        <span className="text-xs font-medium tracking-wide text-slate-500 uppercase dark:text-slate-400">
          {label}
        </span>
        {icon && <span className="text-slate-300 dark:text-slate-600">{icon}</span>}
      </div>
      <div className={cx('tnum mt-2 text-xl font-semibold break-words', TONE_VALUE[tone])}>
        {value}
      </div>
      <div className="mt-1 flex items-center gap-2">
        {sub && <span className="text-xs text-slate-500 dark:text-slate-400">{sub}</span>}
        {delta !== undefined && delta !== null && <Delta value={delta} goodWhen={deltaGoodWhen} />}
      </div>
    </div>
  )
}

export function Delta({
  value,
  goodWhen = 'up',
  suffix,
}: {
  value: number
  goodWhen?: 'up' | 'down'
  suffix?: string
}) {
  if (!Number.isFinite(value)) return null
  const flat = Math.abs(value) < 0.05
  const good = goodWhen === 'up' ? value > 0 : value < 0
  const Icon = flat ? Minus : value > 0 ? ArrowUpRight : ArrowDownRight
  return (
    <span
      className={cx(
        'tnum inline-flex items-center gap-0.5 text-xs font-semibold',
        flat
          ? 'text-slate-400'
          : good
            ? 'text-emerald-600 dark:text-emerald-400'
            : 'text-rose-600 dark:text-rose-400',
      )}
    >
      <Icon size={13} />
      {flat ? '0%' : pct(Math.abs(value), 1)}
      {suffix}
    </span>
  )
}

/** Строка «показатель — значение» для компактных списков. */
export function StatRow({
  label,
  value,
  strong,
  tone,
  indent,
  hint,
}: {
  label: string
  value: ReactNode
  strong?: boolean
  tone?: KpiTone
  indent?: boolean
  hint?: string
}) {
  return (
    <div
      className={cx(
        'flex items-baseline justify-between gap-4 border-b border-slate-100 py-2 last:border-0 dark:border-slate-800/70',
        indent && 'pl-4',
      )}
      title={hint}
    >
      <span
        className={cx(
          'text-sm',
          strong
            ? 'font-semibold text-slate-900 dark:text-slate-50'
            : 'text-slate-600 dark:text-slate-300',
        )}
      >
        {label}
      </span>
      <span
        className={cx(
          'tnum text-sm whitespace-nowrap',
          strong ? 'font-semibold' : 'font-medium',
          tone ? TONE_VALUE[tone] : 'text-slate-900 dark:text-slate-100',
        )}
      >
        {value}
      </span>
    </div>
  )
}
