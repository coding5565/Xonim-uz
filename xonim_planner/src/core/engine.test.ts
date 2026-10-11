import { describe, expect, it } from 'vitest'
import { calculate, employeeMonthlyPay, ingredientCost, recipeCost } from './engine'
import { convertPeriod, factorsOf } from './period'
import { defaultModel } from './defaults'
import type { Employee, Model } from './types'

const model = (): Model => defaultModel()

describe('нормализация периодов', () => {
  it('переводит дневную оплату в месячную по числу рабочих дней', () => {
    const f = factorsOf({ ...model().business, workingDaysPerMonth: 30, workingDaysPerWeek: 7 })
    const e: Employee = {
      id: 'x',
      name: 'Официант',
      role: 'Зал',
      pay: 250_000,
      payFrequency: 'day',
      workDaysPerMonth: 30,
      active: true,
      behavior: 'fixed',
    }
    expect(employeeMonthlyPay(e, f)).toBe(7_500_000)
  })

  it('переводит недельную оплату без правила «неделя × 4»', () => {
    const f = factorsOf({ ...model().business, workingDaysPerMonth: 26, workingDaysPerWeek: 6 })
    const e: Employee = {
      id: 'x',
      name: 'Повар',
      role: 'Кухня',
      pay: 1_500_000,
      payFrequency: 'week',
      workDaysPerMonth: 26,
      active: true,
      behavior: 'fixed',
    }
    // 26 рабочих дней / 6 дней в неделе = 4,333 недели, а не 4.
    expect(employeeMonthlyPay(e, f)).toBeCloseTo(6_500_000, 6)
  })

  it('год равен ровно двенадцати месяцам', () => {
    const f = factorsOf(model().business)
    expect(convertPeriod(1_000_000, 'month', 'year', f)).toBe(12_000_000)
  })

  it('дневная зарплата 200 000 при 26 днях даёт 5 200 000 в месяц', () => {
    const f = factorsOf(model().business)
    const e = model().employees.find((x) => x.name === 'Официант 1')!
    expect(employeeMonthlyPay(e, f)).toBe(5_200_000)
  })
})

describe('ингредиенты и техкарта', () => {
  it('считает стоимость базовой единицы', () => {
    const beef = model().ingredients.find((i) => i.name === 'Говядина')!
    const c = ingredientCost(beef)
    expect(c.perBase).toBe(95) // 95 000 сум / 1000 г
    expect(180 * c.effectivePerBase).toBe(17_100)
  })

  it('учитывает потери через выход годного продукта', () => {
    const beef = { ...model().ingredients.find((i) => i.name === 'Говядина')!, wastePct: 10 }
    const c = ingredientCost(beef)
    expect(c.effectivePerBase).toBeCloseTo(95 / 0.9, 6)
    expect(180 * c.effectivePerBase).toBeCloseTo(19_000, 6)
  })

  it('собирает себестоимость бургера из техкарты', () => {
    const m = model()
    const burger = m.dishes.find((d) => d.name === 'Бургер фирменный')!
    const map = new Map(m.ingredients.map((i) => [i.id, i]))
    const { total, lines } = recipeCost(burger, map)
    expect(lines.map((l) => Math.round(l.cost))).toEqual([4_000, 17_100, 5_000, 1_350, 2_500])
    expect(total).toBe(29_950)
  })

  it('пересчитывает все блюда с ингредиентом при изменении его цены', () => {
    const m = model()
    const before = calculate(m).dishes.find((d) => d.name === 'Бургер фирменный')!.cost
    m.ingredients = m.ingredients.map((i) =>
      i.name === 'Говядина' ? { ...i, purchasePrice: 110_000 } : i,
    )
    const after = calculate(m).dishes.find((d) => d.name === 'Бургер фирменный')!.cost
    expect(before).toBe(29_950)
    expect(after).toBe(29_950 + 180 * (110 - 95))
  })
})

describe('режим «по меню»', () => {
  it('считает экономику плова так же, как в задании', () => {
    const calc = calculate(model())
    const plov = calc.dishes.find((d) => d.name === 'Плов')!
    const f = calc.factors
    expect(convertPeriod(plov.revenueMonth, 'month', 'day', f)).toBe(4_550_000)
    expect(convertPeriod(plov.cogsMonth, 'month', 'day', f)).toBe(1_680_000)
    expect(convertPeriod(plov.grossMonth, 'month', 'day', f)).toBe(2_870_000)
    expect(plov.marginPct).toBeCloseTo(63.08, 2)
    expect(plov.foodCostPct).toBeCloseTo(36.92, 2)
    expect(plov.cmPerUnit).toBe(41_000)
  })

  it('выводит гостей из проданных позиций и не складывает режимы', () => {
    const m = model()
    const menu = calculate(m)
    const avg = calculate({ ...m, salesMode: 'avgcheck' })
    expect(menu.totals.revenue).not.toBe(avg.totals.revenue)
    expect(menu.totals.guests).toBeCloseTo(menu.totals.items / m.business.itemsPerGuest, 6)
    // Выручка режима меню не содержит вклад среднего чека и наоборот.
    expect(avg.totals.revenue).toBe(150 * 120_000 * 30)
  })
})

describe('режим «гости и средний чек»', () => {
  it('считает выручку как гости × чек × рабочие дни', () => {
    const m = { ...model(), salesMode: 'avgcheck' as const }
    const calc = calculate(m)
    expect(calc.totals.revenue).toBe(540_000_000)
    expect(calc.totals.cogs).toBeCloseTo(540_000_000 * 0.35, 6)
    expect(calc.ratios.avgCheck).toBeCloseTo(120_000, 6)
  })
})

describe('P&L', () => {
  it('сходится сверху вниз', () => {
    const t = calculate(model()).totals
    expect(t.grossProfit).toBeCloseTo(t.revenue - t.cogs, 6)
    expect(t.contribution).toBeCloseTo(t.grossProfit - t.payroll - t.variableExpenses, 6)
    expect(t.operatingProfit).toBeCloseTo(t.contribution - t.fixedExpenses, 6)
    expect(t.primeCost).toBeCloseTo(t.cogs + t.payroll, 6)
  })

  it('операционная прибыль совпадает с маржинальным расчётом', () => {
    const c = calculate(model())
    expect(c.totals.operatingProfit).toBeCloseTo(
      c.breakEven.contributionMargin - c.breakEven.fixedCosts,
      6,
    )
  })
})

describe('точка безубыточности', () => {
  it('постоянный ФОТ попадает в постоянную нагрузку, а не в переменные затраты', () => {
    const c = calculate(model())
    expect(c.breakEven.fixedCosts).toBeCloseTo(
      c.totals.fixedExpenses + c.totals.payrollFixed + c.totals.variableExpensesFixed,
      6,
    )
    expect(c.breakEven.variableCosts).toBeCloseTo(
      c.totals.cogs + c.totals.payrollVariable + c.totals.variableExpensesVariable,
      6,
    )
  })

  it('в точке безубыточности прибыль равна нулю', () => {
    const c = calculate(model())
    const beRevenue = c.breakEven.revenue!
    const cmr = c.breakEven.cmRatioPct! / 100
    expect(beRevenue * cmr - c.breakEven.fixedCosts).toBeCloseTo(0, 4)
  })

  it('пересчитывает безубыточность в гостей и заказы', () => {
    const c = calculate(model())
    expect(c.breakEven.guestsMonth).toBeCloseTo(c.breakEven.revenue! / c.ratios.avgCheck!, 6)
    expect(c.breakEven.guestsDay).toBeCloseTo(c.breakEven.guestsMonth! / c.factors.month, 6)
    expect(c.breakEven.ordersMonth).toBeCloseTo(c.breakEven.revenue! / c.ratios.avgOrder!, 6)
  })

  it('считает запас финансовой прочности', () => {
    const c = calculate(model())
    expect(c.breakEven.marginOfSafety).toBeCloseTo(c.totals.revenue - c.breakEven.revenue!, 6)
    expect(c.breakEven.marginOfSafetyPct).toBeCloseTo(
      ((c.totals.revenue - c.breakEven.revenue!) / c.totals.revenue) * 100,
      6,
    )
  })

  it('сообщает о недостижимости, если переменные затраты съедают всю выручку', () => {
    const m = model()
    m.dishes = m.dishes.map((d) => ({ ...d, costMode: 'manual', manualCost: d.price * 1.2 }))
    const c = calculate(m)
    expect(c.breakEven.reachable).toBe(false)
    expect(c.breakEven.revenue).toBeNull()
  })
})

describe('целевая прибыль', () => {
  it('требуемая выручка действительно даёт целевую прибыль', () => {
    const c = calculate(model())
    const required = c.target.requiredRevenue!
    const cmr = c.breakEven.cmRatioPct! / 100
    expect(required * cmr - c.breakEven.fixedCosts).toBeCloseTo(c.target.targetMonthly, 4)
  })

  it('пересчитывает цель в гостей, заказы и средний чек', () => {
    const c = calculate(model())
    expect(c.target.requiredGuestsMonth).toBeCloseTo(
      c.target.requiredRevenue! / c.ratios.avgCheck!,
      6,
    )
    expect(c.target.requiredGuestsDay).toBeCloseTo(
      c.target.requiredGuestsMonth! / c.factors.month,
      6,
    )
    expect(c.target.requiredAvgCheck).toBeCloseTo(c.target.requiredRevenue! / c.totals.guests, 6)
  })
})

describe('переменные расходы', () => {
  it('считает каждый тип по своей базе', () => {
    const c = calculate(model())
    const byName = new Map(c.variableItems.map((i) => [i.name, i.monthly]))
    expect(byName.get('Эквайринг')).toBeCloseTo(c.totals.revenue * 0.7 * 0.01, 6)
    expect(byName.get('Упаковка')).toBeCloseTo(4_000 * c.totals.orders, 6)
    expect(byName.get('Гостевые расходники')).toBeCloseTo(1_500 * c.totals.guests, 6)
    expect(byName.get('Прочие операционные расходы')).toBe(5_000_000)
  })

  it('фиксированная сумма ведёт себя как постоянный расход', () => {
    const c = calculate(model())
    expect(c.variableItems.find((i) => i.name === 'Прочие операционные расходы')!.behavior).toBe(
      'fixed',
    )
    expect(c.variableItems.find((i) => i.name === 'Эквайринг')!.behavior).toBe('variable')
  })
})

describe('симулятор', () => {
  it('рост трафика поднимает выручку пропорционально', () => {
    const m = model()
    const base = calculate(m)
    const up = calculate(m, {
      guestsPct: 20,
      avgCheckPct: 0,
      menuPricePct: 0,
      menuSalesPct: 0,
      cogsPct: 0,
      ingredientPricePct: 0,
      payrollPct: 0,
      extraStaff: 0,
      extraStaffCost: 0,
      fixedPct: 0,
      variablePct: 0,
    })
    expect(up.totals.revenue).toBeCloseTo(base.totals.revenue * 1.2, 4)
    expect(up.totals.fixedExpenses).toBeCloseTo(base.totals.fixedExpenses, 6)
    // Прибыль растёт быстрее выручки — постоянные расходы не меняются.
    expect(up.totals.operatingProfit).toBeGreaterThan(base.totals.operatingProfit * 1.2)
  })

  it('дополнительные сотрудники увеличивают постоянный ФОТ', () => {
    const m = model()
    const base = calculate(m)
    const withStaff = calculate(m, {
      guestsPct: 0,
      avgCheckPct: 0,
      menuPricePct: 0,
      menuSalesPct: 0,
      cogsPct: 0,
      ingredientPricePct: 0,
      payrollPct: 0,
      extraStaff: 2,
      extraStaffCost: 5_000_000,
      fixedPct: 0,
      variablePct: 0,
    })
    expect(withStaff.totals.payroll - base.totals.payroll).toBe(10_000_000)
    expect(withStaff.breakEven.fixedCosts - base.breakEven.fixedCosts).toBe(10_000_000)
  })
})
