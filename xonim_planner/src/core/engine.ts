/**
 * ЕДИНЫЙ ФИНАНСОВЫЙ ДВИЖОК.
 *
 * Все формулы приложения живут здесь. Компоненты интерфейса не считают ничего —
 * они только отображают то, что вернул `calculate`. Любое изменение модели или
 * «ручек» симулятора приводит к полному пересчёту всей цепочки показателей.
 *
 * Канонический период расчёта — МЕСЯЦ. Любой другой период получается
 * масштабированием через `scaleTotals` (коэффициенты — в period.ts).
 */
import { convertPeriod, factorsOf, type PeriodFactors } from './period'
import { safeDiv, safePct } from './format'
import { toBase } from './units'
import type {
  Adjustments,
  CostBehavior,
  Dish,
  Employee,
  Ingredient,
  Model,
  Period,
  VariableExpense,
} from './types'

export const NO_ADJUSTMENTS: Adjustments = {
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

const mult = (pctDelta: number): number => 1 + (Number.isFinite(pctDelta) ? pctDelta : 0) / 100

function clamp(v: number, lo: number, hi: number): number {
  if (!Number.isFinite(v)) return lo
  return Math.min(hi, Math.max(lo, v))
}

/* ───────────────────────────── Ингредиенты ───────────────────────────── */

export interface IngredientCost {
  /** Цена одной базовой единицы (г / мл / шт) без учёта потерь. */
  perBase: number
  /** Эффективная цена с учётом отхода: списанный продукт удорожает полезный. */
  effectivePerBase: number
}

export function ingredientCost(ing: Ingredient, ingredientPricePct = 0): IngredientCost {
  const packBase = toBase(ing.purchaseQty, ing.purchaseUnit, ing.baseUnit)
  const price = ing.purchasePrice * mult(ingredientPricePct)
  const perBase = packBase > 0 ? price / packBase : 0
  const yieldRatio = 1 - clamp(ing.wastePct, 0, 99) / 100
  return { perBase, effectivePerBase: yieldRatio > 0 ? perBase / yieldRatio : perBase }
}

export interface RecipeLineCost {
  lineId: string
  ingredientId: string
  name: string
  qtyBase: number
  cost: number
}

/** Стоимость техкарты = сумма строк. Меняется цена ингредиента — меняются все блюда с ним. */
export function recipeCost(
  dish: Dish,
  ingredients: Map<string, Ingredient>,
  ingredientPricePct = 0,
): { total: number; lines: RecipeLineCost[] } {
  const lines: RecipeLineCost[] = []
  let total = 0
  for (const line of dish.recipe) {
    const ing = ingredients.get(line.ingredientId)
    if (!ing) {
      lines.push({
        lineId: line.id,
        ingredientId: line.ingredientId,
        name: '—',
        qtyBase: 0,
        cost: 0,
      })
      continue
    }
    const { effectivePerBase } = ingredientCost(ing, ingredientPricePct)
    const qtyBase = toBase(line.qty, line.unit, ing.baseUnit)
    const cost = qtyBase * effectivePerBase
    total += cost
    lines.push({ lineId: line.id, ingredientId: ing.id, name: ing.name, qtyBase, cost })
  }
  return { total, lines }
}

/** Себестоимость блюда: ручная или собранная из техкарты, плюс поправки симулятора. */
export function dishCost(
  dish: Dish,
  ingredients: Map<string, Ingredient>,
  adj: Adjustments,
): number {
  const base =
    dish.costMode === 'recipe'
      ? recipeCost(dish, ingredients, adj.ingredientPricePct).total
      : dish.manualCost
  return base * mult(adj.cogsPct)
}

/* ───────────────────────────────── ФОТ ───────────────────────────────── */

/** Месячный ФОТ сотрудника. Периодичность выплаты приводится к месяцу. */
export function employeeMonthlyPay(e: Employee, f: PeriodFactors): number {
  const days =
    Number.isFinite(e.workDaysPerMonth) && e.workDaysPerMonth > 0 ? e.workDaysPerMonth : f.month
  switch (e.payFrequency) {
    case 'day':
      return e.pay * days
    case 'week':
      // Не «× 4»: сколько недель фактически укладывается в отработанные дни.
      return e.pay * (days / f.week)
    case 'month':
    default:
      return e.pay
  }
}

/* ────────────────────────── Переменные расходы ────────────────────────── */

/** Идентификатор строки ФОТ, добавленной ручкой «доп. сотрудники» в симуляторе. */
export const EXTRA_STAFF_ID = '__extra__'

/** Поведение расхода для точки безубыточности: авто по типу или ручное переопределение. */
export function varExpenseBehavior(v: VariableExpense): CostBehavior {
  if (v.behavior) return v.behavior
  return v.type === 'fixed_period' ? 'fixed' : 'variable'
}

/* ───────────────────────────── Результат ───────────────────────────── */

export interface DishRow {
  id: string
  name: string
  categoryId: string
  active: boolean
  price: number
  cost: number
  foodCostPct: number | null
  marginPct: number | null
  cmPerUnit: number
  qtyMonth: number
  revenueMonth: number
  cogsMonth: number
  grossMonth: number
}

export interface BreakdownItem {
  id: string
  name: string
  /**
   * Группировка. Значение приходит из данных пользователя (должность,
   * категория расхода) либо равно типу переменного расхода — движок
   * сознательно не хранит здесь текст интерфейса, чтобы не зависеть от языка.
   */
  group: string
  monthly: number
  behavior: CostBehavior
}

export interface Totals {
  revenue: number
  cogs: number
  grossProfit: number
  payroll: number
  payrollFixed: number
  payrollVariable: number
  variableExpenses: number
  variableExpensesVariable: number
  variableExpensesFixed: number
  /** Операционный результат до постоянных расходов. */
  contribution: number
  fixedExpenses: number
  operatingProfit: number
  primeCost: number
  guests: number
  orders: number
  items: number
}

export interface Ratios {
  grossMarginPct: number | null
  foodCostPct: number | null
  laborCostPct: number | null
  primeCostPct: number | null
  variablePct: number | null
  fixedPct: number | null
  operatingMarginPct: number | null
  avgCheck: number | null
  avgOrder: number | null
  revenuePerGuest: number | null
  profitPerGuest: number | null
}

export interface BreakEven {
  variableCosts: number
  fixedCosts: number
  contributionMargin: number
  cmRatioPct: number | null
  cmPerGuest: number | null
  revenue: number | null
  guestsMonth: number | null
  guestsDay: number | null
  ordersMonth: number | null
  ordersDay: number | null
  marginOfSafety: number | null
  marginOfSafetyPct: number | null
  /** false, если удельная маржа ≤ 0 — тогда безубыточность недостижима. */
  reachable: boolean
}

export interface TargetResult {
  targetMonthly: number
  requiredRevenue: number | null
  requiredGuestsMonth: number | null
  requiredGuestsDay: number | null
  requiredOrdersMonth: number | null
  requiredOrdersDay: number | null
  requiredAvgCheck: number | null
  revenueGap: number | null
  revenueGapPct: number | null
  guestsGap: number | null
  reachable: boolean
}

export interface Calculation {
  factors: PeriodFactors
  totals: Totals
  ratios: Ratios
  breakEven: BreakEven
  target: TargetResult
  dishes: DishRow[]
  payrollItems: BreakdownItem[]
  fixedItems: BreakdownItem[]
  variableItems: BreakdownItem[]
}

/* ───────────────────────────── Главный расчёт ───────────────────────────── */

export function calculate(model: Model, adj: Adjustments = NO_ADJUSTMENTS): Calculation {
  const b = model.business
  const f = factorsOf(b)
  const ingredients = new Map(model.ingredients.map((i) => [i.id, i]))

  /* 1. Продажи ------------------------------------------------------------ */
  const qtyMult = mult(adj.menuSalesPct) * mult(adj.guestsPct)
  const priceMult = mult(adj.menuPricePct) * mult(adj.avgCheckPct)

  const dishes: DishRow[] = model.dishes.map((d) => {
    const price = d.price * priceMult
    const cost = dishCost(d, ingredients, adj)
    const qtyMonth = d.active ? convertPeriod(d.salesQty, d.salesPeriod, 'month', f) * qtyMult : 0
    const revenueMonth = price * qtyMonth
    const cogsMonth = cost * qtyMonth
    return {
      id: d.id,
      name: d.name,
      categoryId: d.categoryId,
      active: d.active,
      price,
      cost,
      foodCostPct: safePct(cost, price),
      marginPct: safePct(price - cost, price),
      cmPerUnit: price - cost,
      qtyMonth,
      revenueMonth,
      cogsMonth,
      grossMonth: revenueMonth - cogsMonth,
    }
  })

  let revenue = 0
  let cogs = 0
  let guests = 0
  let items = 0

  // Активен ровно один режим — выручка двух режимов никогда не складывается.
  if (model.salesMode === 'menu') {
    for (const row of dishes) {
      revenue += row.revenueMonth
      cogs += row.cogsMonth
      items += row.qtyMonth
    }
    const perGuest = b.itemsPerGuest > 0 ? b.itemsPerGuest : 1
    guests = items / perGuest
  } else {
    const m = model.avgCheckModel
    const avgCheckAdj = m.avgCheck * priceMult
    guests = m.guestsPerDay * mult(adj.guestsPct) * f.month
    revenue = guests * avgCheckAdj
    cogs = revenue * (clamp(m.foodCostPct, 0, 100) / 100) * mult(adj.cogsPct)
    items = guests * (b.itemsPerGuest > 0 ? b.itemsPerGuest : 1)
  }

  const guestsPerOrder = b.guestsPerOrder > 0 ? b.guestsPerOrder : 1
  const orders = guests / guestsPerOrder
  const grossProfit = revenue - cogs

  /* 2. ФОТ ---------------------------------------------------------------- */
  const payrollItems: BreakdownItem[] = []
  let payrollFixed = 0
  let payrollVariable = 0
  for (const e of model.employees) {
    if (!e.active) continue
    const monthly = employeeMonthlyPay(e, f) * mult(adj.payrollPct)
    payrollItems.push({
      id: e.id,
      name: e.name || e.role,
      group: e.role,
      monthly,
      behavior: e.behavior,
    })
    if (e.behavior === 'variable') payrollVariable += monthly
    else payrollFixed += monthly
  }
  const extraStaffCost = Math.max(0, adj.extraStaff) * Math.max(0, adj.extraStaffCost)
  if (extraStaffCost > 0) {
    // Сотрудники «из симулятора» не имеют названия: подпись задаёт интерфейс.
    payrollItems.push({
      id: EXTRA_STAFF_ID,
      name: '',
      group: '',
      monthly: extraStaffCost,
      behavior: 'fixed',
    })
    payrollFixed += extraStaffCost
  }
  const payroll = payrollFixed + payrollVariable

  /* 3. Переменные расходы -------------------------------------------------- */
  const variableItems: BreakdownItem[] = []
  let varVariable = 0
  let varFixed = 0
  for (const v of model.variableExpenses) {
    if (!v.active) continue
    let monthly = 0
    switch (v.type) {
      case 'pct_revenue':
        monthly = revenue * (clamp(v.baseSharePct, 0, 100) / 100) * (v.value / 100)
        break
      case 'per_order':
        monthly = v.value * orders
        break
      case 'per_guest':
        monthly = v.value * guests
        break
      case 'fixed_period':
        monthly = convertPeriod(v.value, v.period, 'month', f)
        break
    }
    monthly *= mult(adj.variablePct)
    const behavior = varExpenseBehavior(v)
    variableItems.push({ id: v.id, name: v.name, group: v.type, monthly, behavior })
    if (behavior === 'variable') varVariable += monthly
    else varFixed += monthly
  }
  const variableExpenses = varVariable + varFixed

  /* 4. Постоянные расходы --------------------------------------------------- */
  const fixedItems: BreakdownItem[] = []
  let fixedExpenses = 0
  for (const x of model.fixedExpenses) {
    if (!x.active) continue
    const monthly = convertPeriod(x.amount, x.period, 'month', f) * mult(adj.fixedPct)
    fixedItems.push({
      id: x.id,
      name: x.name,
      group: x.category,
      monthly,
      behavior: 'fixed',
    })
    fixedExpenses += monthly
  }

  /* 5. P&L ------------------------------------------------------------------ */
  const contribution = grossProfit - payroll - variableExpenses
  const operatingProfit = contribution - fixedExpenses
  const primeCost = cogs + payroll

  const totals: Totals = {
    revenue,
    cogs,
    grossProfit,
    payroll,
    payrollFixed,
    payrollVariable,
    variableExpenses,
    variableExpensesVariable: varVariable,
    variableExpensesFixed: varFixed,
    contribution,
    fixedExpenses,
    operatingProfit,
    primeCost,
    guests,
    orders,
    items,
  }

  const avgCheck = safeDiv(revenue, guests)
  const avgOrder = safeDiv(revenue, orders)
  const ratios: Ratios = {
    grossMarginPct: safePct(grossProfit, revenue),
    foodCostPct: safePct(cogs, revenue),
    laborCostPct: safePct(payroll, revenue),
    primeCostPct: safePct(primeCost, revenue),
    variablePct: safePct(variableExpenses, revenue),
    fixedPct: safePct(fixedExpenses, revenue),
    operatingMarginPct: safePct(operatingProfit, revenue),
    avgCheck,
    avgOrder,
    revenuePerGuest: avgCheck,
    profitPerGuest: safeDiv(operatingProfit, guests),
  }

  /* 6. Точка безубыточности -------------------------------------------------
   * Переменными считаются только те затраты, которые реально растут вместе с
   * объёмом: себестоимость блюд, % от выручки, расходы на заказ и на гостя.
   * ФОТ по умолчанию постоянный — периодичность выплаты не делает его переменным.
   */
  const variableCosts = cogs + payrollVariable + varVariable
  const fixedCosts = fixedExpenses + payrollFixed + varFixed
  const contributionMargin = revenue - variableCosts
  const cmRatio = safeDiv(contributionMargin, revenue)
  const reachable = cmRatio !== null && cmRatio > 0
  const beRevenue = reachable ? fixedCosts / (cmRatio as number) : null
  const beGuestsMonth = beRevenue !== null && avgCheck ? safeDiv(beRevenue, avgCheck) : null
  const beOrdersMonth = beRevenue !== null && avgOrder ? safeDiv(beRevenue, avgOrder) : null

  const breakEven: BreakEven = {
    variableCosts,
    fixedCosts,
    contributionMargin,
    cmRatioPct: cmRatio === null ? null : cmRatio * 100,
    cmPerGuest: safeDiv(contributionMargin, guests),
    revenue: beRevenue,
    guestsMonth: beGuestsMonth,
    guestsDay: beGuestsMonth === null ? null : safeDiv(beGuestsMonth, f.month),
    ordersMonth: beOrdersMonth,
    ordersDay: beOrdersMonth === null ? null : safeDiv(beOrdersMonth, f.month),
    marginOfSafety: beRevenue === null ? null : revenue - beRevenue,
    marginOfSafetyPct: beRevenue === null ? null : safePct(revenue - beRevenue, revenue),
    reachable,
  }

  /* 7. Целевая прибыль ------------------------------------------------------ */
  const targetMonthly = convertPeriod(b.targetProfit, b.targetProfitPeriod, 'month', f)
  const requiredRevenue = reachable ? (fixedCosts + targetMonthly) / (cmRatio as number) : null
  const requiredGuestsMonth =
    requiredRevenue !== null && avgCheck ? safeDiv(requiredRevenue, avgCheck) : null
  const requiredOrdersMonth =
    requiredRevenue !== null && avgOrder ? safeDiv(requiredRevenue, avgOrder) : null

  const target: TargetResult = {
    targetMonthly,
    requiredRevenue,
    requiredGuestsMonth,
    requiredGuestsDay: requiredGuestsMonth === null ? null : safeDiv(requiredGuestsMonth, f.month),
    requiredOrdersMonth,
    requiredOrdersDay: requiredOrdersMonth === null ? null : safeDiv(requiredOrdersMonth, f.month),
    requiredAvgCheck: requiredRevenue === null ? null : safeDiv(requiredRevenue, guests),
    revenueGap: requiredRevenue === null ? null : requiredRevenue - revenue,
    revenueGapPct: requiredRevenue === null ? null : safePct(requiredRevenue - revenue, revenue),
    guestsGap: requiredGuestsMonth === null ? null : requiredGuestsMonth - guests,
    reachable,
  }

  return {
    factors: f,
    totals,
    ratios,
    breakEven,
    target,
    dishes,
    payrollItems,
    fixedItems,
    variableItems,
  }
}

/* ──────────────────── Представление в выбранном периоде ──────────────────── */

/**
 * Масштабирует «объёмные» показатели (выручка, затраты, гости, заказы) из месяца
 * в выбранный период. Относительные показатели (%, средний чек) не масштабируются.
 */
export function scaleTotals(t: Totals, ratio: number): Totals {
  const s = (v: number) => v * ratio
  return {
    revenue: s(t.revenue),
    cogs: s(t.cogs),
    grossProfit: s(t.grossProfit),
    payroll: s(t.payroll),
    payrollFixed: s(t.payrollFixed),
    payrollVariable: s(t.payrollVariable),
    variableExpenses: s(t.variableExpenses),
    variableExpensesVariable: s(t.variableExpensesVariable),
    variableExpensesFixed: s(t.variableExpensesFixed),
    contribution: s(t.contribution),
    fixedExpenses: s(t.fixedExpenses),
    operatingProfit: s(t.operatingProfit),
    primeCost: s(t.primeCost),
    guests: s(t.guests),
    orders: s(t.orders),
    items: s(t.items),
  }
}

export function periodRatio(calc: Calculation, period: Period): number {
  return calc.factors[period] / calc.factors.month
}
