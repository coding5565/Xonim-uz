import type { Business, Period } from './types'

export const PERIODS: Period[] = ['day', 'week', 'month', 'year']

/**
 * Длительность периодов в рабочих днях.
 *
 * Сознательно НЕ используем «неделя × 4»: месяц — это фактическое число
 * рабочих дней, а неделя — фактическое число рабочих дней в неделе.
 * Год — ровно 12 месяцев, поэтому недельные суммы не «теряют» ~4 недели в год.
 */
export interface PeriodFactors {
  day: number
  week: number
  month: number
  year: number
}

export function factorsOf(b: Business): PeriodFactors {
  const daysPerWeek = clampPositive(b.workingDaysPerWeek, 7)
  const daysPerMonth = clampPositive(b.workingDaysPerMonth, 30)
  return {
    day: 1,
    week: daysPerWeek,
    month: daysPerMonth,
    year: daysPerMonth * 12,
  }
}

function clampPositive(v: number, fallback: number): number {
  return Number.isFinite(v) && v > 0 ? v : fallback
}

/** Приводит величину из одного периода в другой. */
export function convertPeriod(
  value: number,
  from: Period,
  to: Period,
  f: PeriodFactors,
): number {
  if (from === to) return value
  return (value / f[from]) * f[to]
}

/** Коэффициент пересчёта из месяца в произвольный период. */
export function monthRatio(to: Period, f: PeriodFactors): number {
  return f[to] / f.month
}
