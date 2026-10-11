import { describe, expect, it } from 'vitest'
import { calculate } from './engine'
import { defaultModel, emptyModel } from './defaults'
import { parseModel } from './validate'

describe('проверка внешней модели', () => {
  it('исправную модель возвращает без изменений', () => {
    for (const model of [defaultModel('ru'), defaultModel('uz'), emptyModel('en')]) {
      expect(parseModel(JSON.parse(JSON.stringify(model)))).toEqual(model)
    }
  })

  it('отвергает то, что вовсе не модель калькулятора', () => {
    expect(parseModel(null)).toBeNull()
    expect(parseModel('{}')).toBeNull()
    expect(parseModel({ business: {} })).toBeNull()
    expect(parseModel({ dishes: [] })).toBeNull()
  })

  /**
   * Раньше такой файл проходил проверку и ронял движок на `model.employees`,
   * а сломанная модель оставалась в localStorage — приложение не открывалось.
   */
  it('файл без списков дополняется и считается без ошибок', () => {
    const parsed = parseModel({ business: { name: 'Кафе' }, dishes: [{ name: 'Плов', price: 45000 }] })
    expect(parsed).not.toBeNull()
    expect(parsed!.employees).toEqual([])
    expect(parsed!.variableExpenses).toEqual([])
    const calc = calculate(parsed!)
    expect(Number.isFinite(calc.totals.operatingProfit)).toBe(true)
  })

  it('мусор в полях заменяется безопасными значениями', () => {
    const parsed = parseModel({
      business: { name: 42, workingDaysPerMonth: 'много', planningPeriod: 'decade' },
      salesMode: 'magic',
      dishes: [{ id: 'd1', price: '45000', salesPeriod: 'century', recipe: 'нет' }, 'мусор'],
      variableExpenses: [{ type: 'bribe', behavior: 'sometimes' }],
    })!
    expect(parsed.business.name).toBe(emptyModel().business.name)
    expect(parsed.business.workingDaysPerMonth).toBe(emptyModel().business.workingDaysPerMonth)
    expect(parsed.business.planningPeriod).toBe('month')
    expect(parsed.salesMode).toBe('menu')
    expect(parsed.dishes).toHaveLength(1)
    expect(parsed.dishes[0]).toMatchObject({ id: 'd1', price: 45000, salesPeriod: 'day', recipe: [] })
    expect(parsed.variableExpenses[0]).toMatchObject({ type: 'pct_revenue', behavior: null })
  })
})
