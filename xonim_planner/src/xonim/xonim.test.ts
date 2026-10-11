import { describe, expect, it } from 'vitest'
import { calculate } from '@/core/engine'
import { getTranslator } from '@/i18n'
import { EMPTY_MONTH, SEPTEMBER } from './__fixtures__/september'
import { FactsError, parseFacts } from './facts'
import { monthLabel } from './month'
import { factsToModel, keptBusiness, reconcile, reconciles } from './toModel'

const t = getTranslator('ru')
const facts = parseFacts(SEPTEMBER)

describe('разбор ответа Xonim', () => {
  it('переводит денежные строки в числа', () => {
    expect(facts.sales.revenue).toBe(174_000)
    expect(facts.netProfit).toBe(-3_564_000)
    expect(facts.sales.openDays).toBe(2)
    expect(facts.dishes[0]).toMatchObject({ categoryId: 1, menuValue: 150_000, cost: 60_000 })
  })

  it('не принимает чужую версию формата', () => {
    expect(() => parseFacts({ ...SEPTEMBER, version: 2 })).toThrow(FactsError)
  })

  it('не превращает испорченный ответ в нули', () => {
    expect(() => parseFacts({ ...SEPTEMBER, net_profit: 'abc' })).toThrow(FactsError)
    expect(() => parseFacts({ ...SEPTEMBER, dishes: null })).toThrow(FactsError)
    expect(() => parseFacts({ ...SEPTEMBER, expenses: [{ category: 'X', amount: '1', kind: 'tax' }] }))
      .toThrow(FactsError)
    expect(() => parseFacts('<html>')).toThrow(FactsError)
  })
})

describe('модель из фактов Xonim', () => {
  const model = factsToModel(facts, t)
  const calc = calculate(model)
  const recon = reconcile(facts)

  it('операционная прибыль сходится с Xonim с точностью до названных расхождений', () => {
    // −3 564 000 + 400 000 (выплачено) − 390 000 (по табелю) − 160 000 (школа)
    expect(recon.expected).toBe(-3_714_000)
    expect(calc.totals.operatingProfit).toBeCloseTo(-3_714_000, 0)
    expect(reconciles(calc.totals.operatingProfit, recon)).toBe(true)
  })

  it('выручка по цене меню минус «Скидки и бонусы» — это выручка Xonim', () => {
    expect(calc.totals.revenue).toBeCloseTo(194_000, 0)
    const discounts = calc.variableItems.find((v) => v.id === 'xonim_vx_discounts')
    expect(discounts?.monthly).toBeCloseTo(20_000, 0)
    expect(calc.totals.cogs).toBeCloseTo(71_000, 0)
  })

  it('комиссия Uzum — 30 % от доли канала и совпадает с Xonim до сума', () => {
    const fee = model.variableExpenses.find((v) => v.id === 'xonim_vx_fee_uzum')
    expect(fee?.value).toBe(30)
    expect(fee?.name).toBe('Комиссия Uzum')
    expect(calc.variableItems.find((v) => v.id === 'xonim_vx_fee_uzum')?.monthly).toBeCloseTo(15_000, 0)
    // У зала комиссии нет — строки тоже нет.
    expect(model.variableExpenses.some((v) => v.id === 'xonim_vx_fee_hall')).toBe(false)
  })

  it('чеки и гости совпадают с числом счетов Xonim', () => {
    expect(calc.totals.orders).toBeCloseTo(3, 6)
    expect(calc.totals.guests).toBeCloseTo(3, 6)
    expect(model.business.workingDaysPerMonth).toBe(2)
  })

  it('зарплата — по табелю, расход «Ish haqi» не дублируется', () => {
    expect(calc.totals.payroll).toBeCloseTo(390_000, 0)
    expect(model.fixedExpenses.map((f) => f.name)).toEqual(['Ijara', 'Kommunal', 'Питание сотрудников'])
    const vali = model.employees.find((e) => e.name === 'Vali')
    expect(vali).toMatchObject({ active: false, pay: 80_000, workDaysPerMonth: 26 })
    const gone = model.employees.find((e) => e.name === 'Ketgan')
    expect(gone).toMatchObject({ active: true, pay: 90_000, workDaysPerMonth: 1 })
  })

  it('закупки «Masalliq» и списания растут вместе с продажами', () => {
    const names = model.variableExpenses.map((v) => v.name)
    expect(names).toEqual(['Скидки и бонусы', 'Комиссия Uzum', 'Списания со склада', 'Masalliq'])
    expect(calc.variableItems.find((v) => v.name === 'Masalliq')?.monthly).toBeCloseTo(150_000, 0)
  })

  it('блюдо без продаж берёт цену меню и себестоимость сегодняшнего рецепта', () => {
    const lagmon = model.dishes.find((d) => d.name === 'Lag‘mon')
    expect(lagmon).toMatchObject({ price: 40_000, manualCost: 8_000, salesQty: 0 })
  })

  it('режим «по среднему чеку» даёт ту же прибыль', () => {
    const byCheck = calculate({ ...model, salesMode: 'avgcheck' })
    expect(reconciles(byCheck.totals.operatingProfit, recon)).toBe(true)
  })

  it('повторная загрузка сохраняет цель и свои настройки', () => {
    const own = { ...model.business, targetProfit: 30_000_000, currency: '$', hoursPerDay: 14 }
    const again = factsToModel(facts, t, keptBusiness(own))
    expect(again.business).toMatchObject({ targetProfit: 30_000_000, currency: '$', hoursPerDay: 14 })
    expect(again.business.name).toBe('Xonim')
  })

  it('названия строк — на языке интерфейса в момент загрузки', () => {
    const uz = factsToModel(facts, getTranslator('uz'))
    expect(uz.variableExpenses.find((v) => v.id === 'xonim_vx_fee_uzum')?.name).toBe('Uzum ushlanmasi')
  })
})

describe('название месяца', () => {
  it('понятно на всех трёх языках, узбекский — как в самом Xonim', () => {
    expect(monthLabel('2026-09', 'uz')).toBe('2026-yil sentabr')
    expect(monthLabel('2026-09', 'en')).toBe('September 2026')
    expect(monthLabel('2026-09', 'ru')).toMatch(/^Сентябрь 2026/)
    expect(monthLabel('сентябрь', 'ru')).toBe('сентябрь')
  })
})

describe('месяц без продаж', () => {
  const empty = parseFacts(EMPTY_MONTH)
  const model = factsToModel(empty, t)
  const calc = calculate(model)

  it('считается без деления на ноль и сходится с Xonim', () => {
    expect(Number.isFinite(calc.totals.operatingProfit)).toBe(true)
    expect(calc.totals.operatingProfit).toBeCloseTo(-150_000, 0)
    expect(reconciles(calc.totals.operatingProfit, reconcile(empty))).toBe(true)
  })

  it('закупки без выручки становятся постоянным расходом, а не процентом от нуля', () => {
    expect(model.variableExpenses).toEqual([])
    expect(model.fixedExpenses.map((f) => f.name)).toEqual(['Masalliq'])
    expect(model.business.workingDaysPerMonth).toBe(26)
  })
})
