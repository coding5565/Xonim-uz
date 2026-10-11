import { DEFAULT_LOCALE, type Locale } from '@/i18n/locales'
import { getTranslator } from '@/i18n'
import type { Adjustments, Model, Scenario } from './types'

let seq = 0
/** Идентификаторы генерируются локально — бэкенд не требуется. */
export function uid(prefix = 'id'): string {
  seq += 1
  return `${prefix}_${Date.now().toString(36)}_${seq.toString(36)}`
}

export const ZERO_ADJ: Adjustments = {
  guestsPct: 0,
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
}

/**
 * Сценарии хранят только «ручки». Названия берутся из словаря по `kind`,
 * поэтому смена языка переименовывает базовые сценарии, но не пользовательские.
 */
export function defaultScenarios(): Scenario[] {
  return [
    { id: 'sc_current', name: '', kind: 'current', adj: { ...ZERO_ADJ } },
    {
      id: 'sc_optimistic',
      name: '',
      kind: 'optimistic',
      adj: { ...ZERO_ADJ, guestsPct: 20, avgCheckPct: 5, cogsPct: -3 },
    },
    {
      id: 'sc_pessimistic',
      name: '',
      kind: 'pessimistic',
      adj: { ...ZERO_ADJ, guestsPct: -20, avgCheckPct: -5, cogsPct: 8, fixedPct: 5 },
    },
    { id: 'sc_custom', name: '', kind: 'custom', adj: { ...ZERO_ADJ } },
  ]
}

const CAT = {
  main: 'cat_main',
  salad: 'cat_salad',
  drink: 'cat_drink',
  dessert: 'cat_dessert',
  breakfast: 'cat_breakfast',
  fast: 'cat_fast',
}

const ING = {
  beef: 'ing_beef',
  bun: 'ing_bun',
  cheese: 'ing_cheese',
  sauce: 'ing_sauce',
  veg: 'ing_veg',
  rice: 'ing_rice',
  carrot: 'ing_carrot',
  oil: 'ing_oil',
  chicken: 'ing_chicken',
  potato: 'ing_potato',
  coffee: 'ing_coffee',
  milk: 'ing_milk',
}

/**
 * Демонстрационная модель реального кафе.
 * Названия берутся из словаря выбранного языка — это данные пользователя,
 * поэтому они фиксируются в момент создания и потом языком не меняются.
 */
export function defaultModel(locale: Locale = DEFAULT_LOCALE): Model {
  const t = getTranslator(locale)
  return {
    business: {
      name: t('demo.business'),
      workingDaysPerMonth: 30,
      workingDaysPerWeek: 7,
      hoursPerDay: 12,
      seats: 60,
      currency: '',
      planningPeriod: 'month',
      targetProfit: 150_000_000,
      targetProfitPeriod: 'month',
      guestsPerOrder: 2.2,
      itemsPerGuest: 2.5,
    },
    salesMode: 'menu',
    avgCheckModel: { guestsPerDay: 150, avgCheck: 120_000, foodCostPct: 35 },
    categories: [
      { id: CAT.main, name: t('demo.cat.main') },
      { id: CAT.salad, name: t('demo.cat.salad') },
      { id: CAT.drink, name: t('demo.cat.drink') },
      { id: CAT.dessert, name: t('demo.cat.dessert') },
      { id: CAT.breakfast, name: t('demo.cat.breakfast') },
      { id: CAT.fast, name: t('demo.cat.fast') },
    ],
    ingredients: [
      { id: ING.beef, name: t('demo.ing.beef'), baseUnit: 'g', purchaseQty: 1, purchaseUnit: 'kg', purchasePrice: 95_000, wastePct: 0 },
      { id: ING.bun, name: t('demo.ing.bun'), baseUnit: 'pc', purchaseQty: 1, purchaseUnit: 'pc', purchasePrice: 4_000, wastePct: 0 },
      { id: ING.cheese, name: t('demo.ing.cheese'), baseUnit: 'pc', purchaseQty: 1, purchaseUnit: 'pc', purchasePrice: 2_500, wastePct: 0 },
      { id: ING.sauce, name: t('demo.ing.sauce'), baseUnit: 'g', purchaseQty: 1, purchaseUnit: 'kg', purchasePrice: 45_000, wastePct: 0 },
      { id: ING.veg, name: t('demo.ing.veg'), baseUnit: 'g', purchaseQty: 1, purchaseUnit: 'kg', purchasePrice: 31_250, wastePct: 0 },
      { id: ING.rice, name: t('demo.ing.rice'), baseUnit: 'g', purchaseQty: 1, purchaseUnit: 'kg', purchasePrice: 22_000, wastePct: 0 },
      { id: ING.carrot, name: t('demo.ing.carrot'), baseUnit: 'g', purchaseQty: 1, purchaseUnit: 'kg', purchasePrice: 6_000, wastePct: 12 },
      { id: ING.oil, name: t('demo.ing.oil'), baseUnit: 'ml', purchaseQty: 1, purchaseUnit: 'l', purchasePrice: 28_000, wastePct: 0 },
      { id: ING.chicken, name: t('demo.ing.chicken'), baseUnit: 'g', purchaseQty: 1, purchaseUnit: 'kg', purchasePrice: 42_000, wastePct: 8 },
      { id: ING.potato, name: t('demo.ing.potato'), baseUnit: 'g', purchaseQty: 1, purchaseUnit: 'kg', purchasePrice: 7_000, wastePct: 15 },
      { id: ING.coffee, name: t('demo.ing.coffee'), baseUnit: 'g', purchaseQty: 1, purchaseUnit: 'kg', purchasePrice: 180_000, wastePct: 0 },
      { id: ING.milk, name: t('demo.ing.milk'), baseUnit: 'ml', purchaseQty: 1, purchaseUnit: 'l', purchasePrice: 14_000, wastePct: 0 },
    ],
    dishes: [
      {
        id: 'dish_plov',
        name: t('demo.dish.plov'),
        categoryId: CAT.main,
        price: 65_000,
        costMode: 'manual',
        manualCost: 24_000,
        recipe: [],
        salesQty: 70,
        salesPeriod: 'day',
        active: true,
      },
      {
        id: 'dish_burger',
        name: t('demo.dish.burger'),
        categoryId: CAT.fast,
        price: 55_000,
        costMode: 'recipe',
        manualCost: 30_000,
        recipe: [
          { id: 'r1', ingredientId: ING.bun, qty: 1, unit: 'pc' },
          { id: 'r2', ingredientId: ING.beef, qty: 180, unit: 'g' },
          { id: 'r3', ingredientId: ING.cheese, qty: 2, unit: 'pc' },
          { id: 'r4', ingredientId: ING.sauce, qty: 30, unit: 'g' },
          { id: 'r5', ingredientId: ING.veg, qty: 80, unit: 'g' },
        ],
        salesQty: 45,
        salesPeriod: 'day',
        active: true,
      },
      {
        id: 'dish_lagman',
        name: t('demo.dish.lagman'),
        categoryId: CAT.main,
        price: 48_000,
        costMode: 'manual',
        manualCost: 17_000,
        recipe: [],
        salesQty: 35,
        salesPeriod: 'day',
        active: true,
      },
      {
        id: 'dish_shashlik',
        name: t('demo.dish.shashlik'),
        categoryId: CAT.main,
        price: 38_000,
        costMode: 'manual',
        manualCost: 16_000,
        recipe: [],
        salesQty: 50,
        salesPeriod: 'day',
        active: true,
      },
      {
        id: 'dish_achichuk',
        name: t('demo.dish.achichuk'),
        categoryId: CAT.salad,
        price: 25_000,
        costMode: 'manual',
        manualCost: 7_000,
        recipe: [],
        salesQty: 40,
        salesPeriod: 'day',
        active: true,
      },
      {
        id: 'dish_cappuccino',
        name: t('demo.dish.cappuccino'),
        categoryId: CAT.drink,
        price: 25_000,
        costMode: 'recipe',
        manualCost: 6_000,
        recipe: [
          { id: 'r6', ingredientId: ING.coffee, qty: 18, unit: 'g' },
          { id: 'r7', ingredientId: ING.milk, qty: 150, unit: 'ml' },
        ],
        salesQty: 60,
        salesPeriod: 'day',
        active: true,
      },
      {
        id: 'dish_tea',
        name: t('demo.dish.tea'),
        categoryId: CAT.drink,
        price: 8_000,
        costMode: 'manual',
        manualCost: 1_200,
        recipe: [],
        salesQty: 120,
        salesPeriod: 'day',
        active: true,
      },
      {
        id: 'dish_cola',
        name: t('demo.dish.bottled'),
        categoryId: CAT.drink,
        price: 12_000,
        costMode: 'manual',
        manualCost: 6_000,
        recipe: [],
        salesQty: 45,
        salesPeriod: 'day',
        active: true,
      },
      {
        id: 'dish_cheesecake',
        name: t('demo.dish.cheesecake'),
        categoryId: CAT.dessert,
        price: 32_000,
        costMode: 'manual',
        manualCost: 11_000,
        recipe: [],
        salesQty: 25,
        salesPeriod: 'day',
        active: true,
      },
      {
        id: 'dish_omelette',
        name: t('demo.dish.omelette'),
        categoryId: CAT.breakfast,
        price: 28_000,
        costMode: 'manual',
        manualCost: 9_000,
        recipe: [],
        salesQty: 30,
        salesPeriod: 'day',
        active: true,
      },
    ],
    employees: [
      { id: 'emp_1', name: t('demo.emp.manager'), role: t('demo.role.management'), pay: 9_000_000, payFrequency: 'month', workDaysPerMonth: 26, active: true, behavior: 'fixed' },
      { id: 'emp_2', name: t('demo.emp.chef'), role: t('demo.role.kitchen'), pay: 12_000_000, payFrequency: 'month', workDaysPerMonth: 26, active: true, behavior: 'fixed' },
      { id: 'emp_3', name: t('demo.emp.cook1'), role: t('demo.role.kitchen'), pay: 350_000, payFrequency: 'day', workDaysPerMonth: 26, active: true, behavior: 'fixed' },
      { id: 'emp_4', name: t('demo.emp.cook2'), role: t('demo.role.kitchen'), pay: 350_000, payFrequency: 'day', workDaysPerMonth: 26, active: true, behavior: 'fixed' },
      { id: 'emp_5', name: t('demo.emp.waiter1'), role: t('demo.role.hall'), pay: 200_000, payFrequency: 'day', workDaysPerMonth: 26, active: true, behavior: 'fixed' },
      { id: 'emp_6', name: t('demo.emp.waiter2'), role: t('demo.role.hall'), pay: 200_000, payFrequency: 'day', workDaysPerMonth: 26, active: true, behavior: 'fixed' },
      { id: 'emp_7', name: t('demo.emp.waiter3'), role: t('demo.role.hall'), pay: 1_400_000, payFrequency: 'week', workDaysPerMonth: 26, active: true, behavior: 'variable' },
      { id: 'emp_8', name: t('demo.emp.bartender'), role: t('demo.role.bar'), pay: 250_000, payFrequency: 'day', workDaysPerMonth: 26, active: true, behavior: 'fixed' },
      { id: 'emp_9', name: t('demo.emp.cashier'), role: t('demo.role.hall'), pay: 4_500_000, payFrequency: 'month', workDaysPerMonth: 26, active: true, behavior: 'fixed' },
      { id: 'emp_10', name: t('demo.emp.dishwasher'), role: t('demo.role.kitchen'), pay: 150_000, payFrequency: 'day', workDaysPerMonth: 26, active: true, behavior: 'fixed' },
      { id: 'emp_11', name: t('demo.emp.cleaner'), role: t('demo.role.facilities'), pay: 3_000_000, payFrequency: 'month', workDaysPerMonth: 26, active: true, behavior: 'fixed' },
    ],
    fixedExpenses: [
      { id: 'fx_1', name: t('demo.fx.rent'), category: t('demo.fxcat.rent'), amount: 25_000_000, period: 'month', active: true },
      { id: 'fx_2', name: t('demo.fx.utilities'), category: t('demo.fxcat.utilities'), amount: 6_000_000, period: 'month', active: true },
      { id: 'fx_3', name: t('demo.fx.internet'), category: t('demo.fxcat.communication'), amount: 500_000, period: 'month', active: true },
      { id: 'fx_4', name: t('demo.fx.security'), category: t('demo.fxcat.security'), amount: 2_500_000, period: 'month', active: true },
      { id: 'fx_5', name: t('demo.fx.accounting'), category: t('demo.fxcat.admin'), amount: 3_000_000, period: 'month', active: true },
      { id: 'fx_6', name: t('demo.fx.software'), category: t('demo.fxcat.software'), amount: 1_200_000, period: 'month', active: true },
      { id: 'fx_7', name: t('demo.fx.marketing'), category: t('demo.fxcat.marketing'), amount: 5_000_000, period: 'month', active: true },
      { id: 'fx_8', name: t('demo.fx.household'), category: t('demo.fxcat.other'), amount: 2_000_000, period: 'month', active: true },
    ],
    variableExpenses: [
      { id: 'vx_1', name: t('demo.vx.acquiring'), type: 'pct_revenue', value: 1, baseSharePct: 70, period: 'month', active: true, behavior: null },
      { id: 'vx_2', name: t('demo.vx.aggregators'), type: 'pct_revenue', value: 25, baseSharePct: 15, period: 'month', active: true, behavior: null },
      { id: 'vx_3', name: t('demo.vx.packaging'), type: 'per_order', value: 4_000, baseSharePct: 100, period: 'month', active: true, behavior: null },
      { id: 'vx_4', name: t('demo.vx.guestSupplies'), type: 'per_guest', value: 1_500, baseSharePct: 100, period: 'month', active: true, behavior: null },
      { id: 'vx_5', name: t('demo.vx.otherOperating'), type: 'fixed_period', value: 5_000_000, baseSharePct: 100, period: 'month', active: true, behavior: null },
    ],
  }
}

/** Пустая модель — для старта «с нуля». */
export function emptyModel(locale: Locale = DEFAULT_LOCALE): Model {
  const t = getTranslator(locale)
  const m = defaultModel(locale)
  return {
    ...m,
    business: { ...m.business, name: t('demo.myCafe'), targetProfit: 0 },
    dishes: [],
    ingredients: [],
    employees: [],
    fixedExpenses: [],
    variableExpenses: [],
    avgCheckModel: { guestsPerDay: 0, avgCheck: 0, foodCostPct: 30 },
  }
}
