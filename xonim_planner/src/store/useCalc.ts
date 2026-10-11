import { useMemo } from 'react'
import { NO_ADJUSTMENTS, calculate, scaleTotals, type Calculation, type Totals } from '@/core/engine'
import type { Period } from '@/core/types'
import { useActiveScenario, useAppStore } from './useAppStore'
import { useCurrency } from './useT'

/** Расчёт с учётом активного сценария / ручек симулятора. */
export function useCalc(): Calculation {
  const model = useAppStore((s) => s.model)
  const adj = useActiveScenario().adj
  return useMemo(() => calculate(model, adj), [model, adj])
}

/** Базовый расчёт без поправок — «как есть сейчас». */
export function useBaseCalc(): Calculation {
  const model = useAppStore((s) => s.model)
  return useMemo(() => calculate(model, NO_ADJUSTMENTS), [model])
}

export interface PeriodView {
  calc: Calculation
  base: Calculation
  totals: Totals
  baseTotals: Totals
  period: Period
  ratio: number
  currency: string
  /** Активен ли сценарий, отличающийся от базовой модели. */
  simulated: boolean
}

/** Единая точка доступа для страниц: расчёт + выбранный период отображения. */
export function usePeriodView(): PeriodView {
  const calc = useCalc()
  const base = useBaseCalc()
  const period = useAppStore((s) => s.period)
  const currency = useCurrency()
  const scenario = useActiveScenario()

  const ratio = calc.factors[period] / calc.factors.month
  return useMemo(
    () => ({
      calc,
      base,
      totals: scaleTotals(calc.totals, ratio),
      baseTotals: scaleTotals(base.totals, ratio),
      period,
      ratio,
      currency,
      simulated: scenario.kind !== 'current',
    }),
    [calc, base, ratio, period, currency, scenario.kind],
  )
}
