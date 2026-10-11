/**
 * Явные таблицы «значение модели → ключ перевода».
 *
 * Собирать ключи шаблонными строками (`period.label.${p}`) нельзя: тогда
 * TypeScript перестаёт проверять их наличие в словаре. Эти таблицы дают
 * ту же краткость, но с полной проверкой на этапе компиляции.
 */
import type {
  BaseUnit,
  CostBehavior,
  MeasureUnit,
  PayFrequency,
  Period,
  VarExpenseType,
} from '@/core/types'
import type { TKey } from './index'

/** «День», «Неделя» — заголовки переключателя периода. */
export const PERIOD_LABEL_KEY: Record<Period, TKey> = {
  day: 'period.label.day',
  week: 'period.label.week',
  month: 'period.label.month',
  year: 'period.label.year',
}

/** «/ день», «/ месяц» — подписи к суммам. */
export const PERIOD_LOWER_KEY: Record<Period, TKey> = {
  day: 'period.lower.day',
  week: 'period.lower.week',
  month: 'period.lower.month',
  year: 'period.lower.year',
}

/** «за месяц», «за неделю» — в русском требуется винительный падеж. */
export const PERIOD_ACC_KEY: Record<Period, TKey> = {
  day: 'period.acc.day',
  week: 'period.acc.week',
  month: 'period.acc.month',
  year: 'period.acc.year',
}

export const UNIT_KEY: Record<MeasureUnit, TKey> = {
  kg: 'unit.kg',
  g: 'unit.g',
  l: 'unit.l',
  ml: 'unit.ml',
  pc: 'unit.pc',
}

export const BASE_UNIT_KEY: Record<BaseUnit, TKey> = {
  g: 'unit.g',
  ml: 'unit.ml',
  pc: 'unit.pc',
}

/** Подписи выбора учётной единицы ингредиента. */
export const BASE_UNIT_OPTION_KEY: Record<BaseUnit, TKey> = {
  g: 'unit.option.g',
  ml: 'unit.option.ml',
  pc: 'unit.option.pc',
}

export const PAY_FREQUENCY_KEY: Record<PayFrequency, TKey> = {
  day: 'staff.freq.day',
  week: 'staff.freq.week',
  month: 'staff.freq.month',
}

export const BEHAVIOR_KEY: Record<CostBehavior, TKey> = {
  fixed: 'behavior.fixed',
  variable: 'behavior.variable',
}

export const VAR_TYPE_KEY: Record<VarExpenseType, TKey> = {
  pct_revenue: 'var.type.pctRevenue',
  per_order: 'var.type.perOrder',
  per_guest: 'var.type.perGuest',
  fixed_period: 'var.type.fixedPeriod',
}

/** Группировка переменных расходов в разбивке расчёта. */
export const VAR_TYPE_GROUP_KEY: Record<VarExpenseType, TKey> = {
  pct_revenue: 'var.group.pctRevenue',
  per_order: 'var.group.perOrder',
  per_guest: 'var.group.perGuest',
  fixed_period: 'var.group.fixedPeriod',
}
