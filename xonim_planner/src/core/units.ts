import type { BaseUnit, MeasureUnit } from './types'

/** Сколько базовых единиц в одной единице измерения. */
const TO_BASE: Record<MeasureUnit, { base: BaseUnit; factor: number }> = {
  kg: { base: 'g', factor: 1000 },
  g: { base: 'g', factor: 1 },
  l: { base: 'ml', factor: 1000 },
  ml: { base: 'ml', factor: 1 },
  pc: { base: 'pc', factor: 1 },
}

export function baseOf(unit: MeasureUnit): BaseUnit {
  return TO_BASE[unit].base
}

/** Единицы, совместимые с данной базовой единицей. */
export function unitsFor(base: BaseUnit): MeasureUnit[] {
  return (Object.keys(TO_BASE) as MeasureUnit[]).filter((u) => TO_BASE[u].base === base)
}

export function isCompatible(unit: MeasureUnit, base: BaseUnit): boolean {
  return TO_BASE[unit].base === base
}

/**
 * Переводит количество в базовые единицы ингредиента.
 * Если единица несовместима с базовой (например «л» для мяса) — возвращает 0,
 * чтобы несогласованные данные не искажали себестоимость молча.
 */
export function toBase(qty: number, unit: MeasureUnit, base: BaseUnit): number {
  const conv = TO_BASE[unit]
  if (conv.base !== base) return 0
  return qty * conv.factor
}
