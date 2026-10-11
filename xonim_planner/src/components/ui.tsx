import { useEffect, useId, useRef, useState, type ReactNode } from 'react'
import { useAppStore } from '@/store/useAppStore'
import { Info } from 'lucide-react'
import { cx } from './cx'
import { formatLocaleNumber, num, parseLocaleNumber, plainNumber } from '@/core/format'

/* ─────────────────────────────── Контейнеры ─────────────────────────────── */

export function Card({
  children,
  className,
  pad = true,
}: {
  children: ReactNode
  className?: string
  pad?: boolean
}) {
  return <div className={cx('card', pad && 'card-pad', className)}>{children}</div>
}

export function SectionTitle({
  title,
  subtitle,
  right,
  icon,
}: {
  title: string
  subtitle?: ReactNode
  right?: ReactNode
  icon?: ReactNode
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div className="flex items-start gap-3">
        {icon && (
          <div className="mt-0.5 rounded-lg bg-brand-50 p-2 text-brand-600 dark:bg-brand-900/30 dark:text-brand-300">
            {icon}
          </div>
        )}
        <div>
          <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-50">{title}</h2>
          {subtitle && (
            <p className="mt-0.5 max-w-2xl text-sm text-slate-500 dark:text-slate-400">{subtitle}</p>
          )}
        </div>
      </div>
      {right && <div className="flex items-center gap-2">{right}</div>}
    </div>
  )
}

export function Hint({ text }: { text: string }) {
  return (
    <span
      title={text}
      className="inline-flex cursor-help align-middle text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
    >
      <Info size={14} />
    </span>
  )
}

export function Field({
  label,
  hint,
  children,
  className,
}: {
  label: string
  hint?: string
  children: ReactNode
  className?: string
}) {
  return (
    <div className={className}>
      <span className="label">
        {label} {hint && <Hint text={hint} />}
      </span>
      {children}
    </div>
  )
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 px-6 py-12 text-center dark:border-slate-700">
      <p className="font-medium text-slate-700 dark:text-slate-200">{title}</p>
      {description && (
        <p className="mt-1 max-w-md text-sm text-slate-500 dark:text-slate-400">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

/* ──────────────────────────────── Поля ввода ──────────────────────────────── */

/**
 * Числовое поле с разделителями разрядов текущего языка.
 * Во время ввода показывается «сырое» значение, после потери фокуса — сгруппированное.
 * Разбор ввода учитывает язык: `125 000` и `125,000` — одно и то же число.
 */
export function NumberInput({
  value,
  onChange,
  suffix,
  min,
  max,
  placeholder,
  disabled,
  className,
}: {
  value: number
  onChange: (v: number) => void
  suffix?: string
  min?: number
  max?: number
  placeholder?: string
  disabled?: boolean
  className?: string
}) {
  const locale = useAppStore((s) => s.locale)
  const [focused, setFocused] = useState(false)
  const [text, setText] = useState(() => formatLocaleNumber(value))
  const focusedRef = useRef(false)

  // Смена языка меняет разделители — поле перерисовывается под новый формат.
  useEffect(() => {
    if (!focusedRef.current) setText(formatLocaleNumber(value))
  }, [value, locale])

  const commit = (raw: string) => {
    const n = parseLocaleNumber(raw)
    if (n === null) return
    let v = n
    if (min !== undefined) v = Math.max(min, v)
    if (max !== undefined) v = Math.min(max, v)
    onChange(v)
  }

  return (
    <div className={cx('relative', className)}>
      <input
        className={cx('input tnum text-right', suffix && 'pr-12')}
        inputMode="decimal"
        disabled={disabled}
        placeholder={placeholder}
        value={text}
        onFocus={(e) => {
          focusedRef.current = true
          setFocused(true)
          setText(plainNumber(value))
          requestAnimationFrame(() => e.target.select())
        }}
        onChange={(e) => {
          setText(e.target.value)
          commit(e.target.value)
        }}
        onBlur={() => {
          focusedRef.current = false
          setFocused(false)
          const n = parseLocaleNumber(text)
          const v = n === null ? 0 : n
          commit(n === null ? '0' : text)
          setText(formatLocaleNumber(clampTo(v, min, max)))
        }}
      />
      {suffix && !focused && (
        <span className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-xs text-slate-400">
          {suffix}
        </span>
      )}
    </div>
  )
}

function clampTo(v: number, min?: number, max?: number): number {
  let x = v
  if (min !== undefined) x = Math.max(min, x)
  if (max !== undefined) x = Math.min(max, x)
  return x
}

export function TextInput({
  value,
  onChange,
  placeholder,
  className,
  disabled,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  className?: string
  disabled?: boolean
}) {
  return (
    <input
      className={cx('input', className)}
      value={value}
      disabled={disabled}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

export function Select<T extends string>({
  value,
  onChange,
  options,
  className,
  disabled,
}: {
  value: T
  onChange: (v: T) => void
  options: Array<{ value: T; label: string }>
  className?: string
  disabled?: boolean
}) {
  return (
    <select
      className={cx('input cursor-pointer appearance-none pr-8', className)}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value as T)}
      style={{
        backgroundImage:
          "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2394a3b8' stroke-width='2' stroke-linecap='round'%3E%3Cpath d='m6 9 6 6 6-6'/%3E%3C/svg%3E\")",
        backgroundRepeat: 'no-repeat',
        backgroundPosition: 'right 8px center',
      }}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

export function Segmented<T extends string>({
  value,
  onChange,
  options,
  size = 'md',
  className,
}: {
  value: T
  onChange: (v: T) => void
  options: Array<{ value: T; label: string; icon?: ReactNode }>
  size?: 'sm' | 'md'
  className?: string
}) {
  return (
    <div
      className={cx(
        'inline-flex rounded-lg bg-slate-100 p-0.5 dark:bg-slate-800',
        size === 'sm' ? 'text-xs' : 'text-sm',
        className,
      )}
    >
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          className={cx(
            'inline-flex cursor-pointer items-center gap-1.5 rounded-md font-medium transition',
            size === 'sm' ? 'px-2.5 py-1' : 'px-3 py-1.5',
            value === o.value
              ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-950 dark:text-white'
              : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-100',
          )}
        >
          {o.icon}
          {o.label}
        </button>
      ))}
    </div>
  )
}

export function Switch({
  checked,
  onChange,
  label,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label?: string
}) {
  const id = useId()
  return (
    <label htmlFor={id} className="inline-flex cursor-pointer items-center gap-2 select-none">
      <button
        id={id}
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={cx(
          'relative h-5 w-9 shrink-0 cursor-pointer rounded-full transition',
          checked ? 'bg-brand-600' : 'bg-slate-300 dark:bg-slate-700',
        )}
      >
        <span
          className={cx(
            'absolute top-0.5 left-0.5 h-4 w-4 rounded-full bg-white shadow transition',
            checked && 'translate-x-4',
          )}
        />
      </button>
      {label && <span className="text-sm text-slate-600 dark:text-slate-300">{label}</span>}
    </label>
  )
}

/** Ползунок «ручки» симулятора с числовым полем рядом. */
export function Slider({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
  suffix = '%',
  hint,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  min: number
  max: number
  step?: number
  suffix?: string
  hint?: string
}) {
  const neutral = Math.abs(value) < 1e-9
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-slate-600 dark:text-slate-300">
          {label} {hint && <Hint text={hint} />}
        </span>
        <span
          className={cx(
            'tnum text-xs font-semibold',
            neutral
              ? 'text-slate-400'
              : value > 0
                ? 'text-brand-600 dark:text-brand-400'
                : 'text-amber-600 dark:text-amber-400',
          )}
        >
          {value > 0 ? '+' : ''}
          {num(value, 2)}
          {suffix}
        </span>
      </div>
      <div className="flex items-center gap-3">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-slate-200 accent-brand-600 dark:bg-slate-700"
        />
        <div className="w-24 shrink-0">
          <NumberInput value={value} onChange={onChange} min={min} max={max} />
        </div>
      </div>
    </div>
  )
}

/* ──────────────────────────────── Таблица ──────────────────────────────── */

export function Table({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className="-mx-4 overflow-x-auto sm:mx-0">
      <table className={cx('w-full min-w-[720px] border-collapse', className)}>{children}</table>
    </div>
  )
}

export function Thead({ children }: { children: ReactNode }) {
  return (
    <thead className="border-b border-slate-200 bg-slate-50/60 dark:border-slate-800 dark:bg-slate-800/40">
      {children}
    </thead>
  )
}

export function Tr({
  children,
  muted,
  className,
}: {
  children: ReactNode
  muted?: boolean
  className?: string
}) {
  return (
    <tr
      className={cx(
        'border-b border-slate-100 transition last:border-0 hover:bg-slate-50/70 dark:border-slate-800/70 dark:hover:bg-slate-800/30',
        muted && 'opacity-50',
        className,
      )}
    >
      {children}
    </tr>
  )
}

/* ─────────────────────────────── Индикаторы ─────────────────────────────── */

export function Badge({
  children,
  tone = 'slate',
}: {
  children: ReactNode
  tone?: 'slate' | 'green' | 'amber' | 'rose' | 'blue'
}) {
  const tones: Record<string, string> = {
    slate: 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300',
    green: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300',
    amber: 'bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300',
    rose: 'bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300',
    blue: 'bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300',
  }
  return <span className={cx('chip', tones[tone])}>{children}</span>
}

export function DeleteButton({ onClick, title = 'Удалить' }: { onClick: () => void; title?: string }) {
  return (
    <button type="button" onClick={onClick} title={title} className="btn btn-danger px-2 py-1">
      ✕
    </button>
  )
}
