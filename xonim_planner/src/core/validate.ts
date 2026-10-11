/**
 * Проверка модели, пришедшей извне: из JSON-файла или из localStorage.
 *
 * Раньше импорт проверял только `business` и `dishes`. Файл без списка
 * сотрудников проходил проверку, движок падал на `model.employees`, а сломанная
 * модель уже лежала в localStorage — и приложение не открывалось даже после
 * перезагрузки. Теперь недостающие списки и поля заполняются значениями по
 * умолчанию, а мусор в полях заменяется безопасными значениями.
 */
import { emptyModel, uid } from './defaults'
import { PERIODS } from './period'
import type {
  AvgCheckModel,
  BaseUnit,
  Business,
  Category,
  CostBehavior,
  Dish,
  Employee,
  FixedExpense,
  Ingredient,
  MeasureUnit,
  Model,
  PayFrequency,
  RecipeLine,
  SalesMode,
  VarExpenseType,
  VariableExpense,
} from './types'

type Obj = Record<string, unknown>

const isObj = (v: unknown): v is Obj => typeof v === 'object' && v !== null && !Array.isArray(v)

function num(v: unknown, fallback: number): number {
  const n = typeof v === 'number' ? v : typeof v === 'string' && v.trim() !== '' ? Number(v) : NaN
  return Number.isFinite(n) ? n : fallback
}

const str = (v: unknown, fallback = ''): string => (typeof v === 'string' ? v : fallback)

const bool = (v: unknown, fallback: boolean): boolean => (typeof v === 'boolean' ? v : fallback)

function oneOf<T extends string>(v: unknown, allowed: readonly T[], fallback: T): T {
  return typeof v === 'string' && (allowed as readonly string[]).includes(v) ? (v as T) : fallback
}

/** Список объектов; всё, что не объект, отбрасывается. */
function items<T>(v: unknown, read: (o: Obj) => T): T[] {
  return Array.isArray(v) ? v.filter(isObj).map(read) : []
}

const idOf = (v: unknown, prefix: string): string =>
  typeof v === 'string' && v !== '' ? v : uid(prefix)

const SALES_MODES: SalesMode[] = ['menu', 'avgcheck']
const MEASURE_UNITS: MeasureUnit[] = ['kg', 'g', 'l', 'ml', 'pc']
const BASE_UNITS: BaseUnit[] = ['g', 'ml', 'pc']
const PAY_FREQUENCIES: PayFrequency[] = ['day', 'week', 'month']
const VAR_TYPES: VarExpenseType[] = ['pct_revenue', 'per_order', 'per_guest', 'fixed_period']
const BEHAVIORS: CostBehavior[] = ['fixed', 'variable']

/**
 * Возвращает исправную модель или `null`, если это вообще не модель
 * калькулятора (нет параметров бизнеса или списка блюд).
 */
export function parseModel(raw: unknown): Model | null {
  if (!isObj(raw) || !isObj(raw.business) || !Array.isArray(raw.dishes)) return null
  const base = emptyModel()
  const b = raw.business
  const d = base.business

  const business: Business = {
    name: str(b.name, d.name),
    workingDaysPerMonth: num(b.workingDaysPerMonth, d.workingDaysPerMonth),
    workingDaysPerWeek: num(b.workingDaysPerWeek, d.workingDaysPerWeek),
    hoursPerDay: num(b.hoursPerDay, d.hoursPerDay),
    seats: num(b.seats, d.seats),
    currency: str(b.currency, d.currency),
    planningPeriod: oneOf(b.planningPeriod, PERIODS, d.planningPeriod),
    targetProfit: num(b.targetProfit, d.targetProfit),
    targetProfitPeriod: oneOf(b.targetProfitPeriod, PERIODS, d.targetProfitPeriod),
    guestsPerOrder: num(b.guestsPerOrder, d.guestsPerOrder),
    itemsPerGuest: num(b.itemsPerGuest, d.itemsPerGuest),
  }

  const a = isObj(raw.avgCheckModel) ? raw.avgCheckModel : {}
  const avgCheckModel: AvgCheckModel = {
    guestsPerDay: num(a.guestsPerDay, base.avgCheckModel.guestsPerDay),
    avgCheck: num(a.avgCheck, base.avgCheckModel.avgCheck),
    foodCostPct: num(a.foodCostPct, base.avgCheckModel.foodCostPct),
  }

  const categories = items(raw.categories, (c): Category => ({
    id: idOf(c.id, 'cat'),
    name: str(c.name),
  }))

  const ingredients = items(raw.ingredients, (i): Ingredient => ({
    id: idOf(i.id, 'ing'),
    name: str(i.name),
    baseUnit: oneOf(i.baseUnit, BASE_UNITS, 'g'),
    purchaseQty: num(i.purchaseQty, 1),
    purchaseUnit: oneOf(i.purchaseUnit, MEASURE_UNITS, 'kg'),
    purchasePrice: num(i.purchasePrice, 0),
    wastePct: num(i.wastePct, 0),
  }))

  const dishes = items(raw.dishes, (x): Dish => ({
    id: idOf(x.id, 'dish'),
    name: str(x.name),
    categoryId: str(x.categoryId),
    price: num(x.price, 0),
    costMode: oneOf(x.costMode, ['manual', 'recipe'] as const, 'manual'),
    manualCost: num(x.manualCost, 0),
    recipe: items(x.recipe, (r): RecipeLine => ({
      id: idOf(r.id, 'r'),
      ingredientId: str(r.ingredientId),
      qty: num(r.qty, 0),
      unit: oneOf(r.unit, MEASURE_UNITS, 'g'),
    })),
    salesQty: num(x.salesQty, 0),
    salesPeriod: oneOf(x.salesPeriod, PERIODS, 'day'),
    active: bool(x.active, true),
  }))

  const employees = items(raw.employees, (e): Employee => ({
    id: idOf(e.id, 'emp'),
    name: str(e.name),
    role: str(e.role),
    pay: num(e.pay, 0),
    payFrequency: oneOf(e.payFrequency, PAY_FREQUENCIES, 'month'),
    workDaysPerMonth: num(e.workDaysPerMonth, business.workingDaysPerMonth),
    active: bool(e.active, true),
    behavior: oneOf(e.behavior, BEHAVIORS, 'fixed'),
  }))

  const fixedExpenses = items(raw.fixedExpenses, (f): FixedExpense => ({
    id: idOf(f.id, 'fx'),
    name: str(f.name),
    category: str(f.category),
    amount: num(f.amount, 0),
    period: oneOf(f.period, PERIODS, 'month'),
    active: bool(f.active, true),
  }))

  const variableExpenses = items(raw.variableExpenses, (v): VariableExpense => ({
    id: idOf(v.id, 'vx'),
    name: str(v.name),
    type: oneOf(v.type, VAR_TYPES, 'pct_revenue'),
    value: num(v.value, 0),
    baseSharePct: num(v.baseSharePct, 100),
    period: oneOf(v.period, PERIODS, 'month'),
    active: bool(v.active, true),
    // null — «по типу расхода»; ручное переопределение сохраняется, мусор — нет.
    behavior: BEHAVIORS.includes(v.behavior as CostBehavior) ? (v.behavior as CostBehavior) : null,
  }))

  return {
    business,
    salesMode: oneOf(raw.salesMode, SALES_MODES, 'menu'),
    avgCheckModel,
    categories,
    dishes,
    ingredients,
    employees,
    fixedExpenses,
    variableExpenses,
  }
}
