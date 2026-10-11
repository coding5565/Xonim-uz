/**
 * Доменная модель приложения.
 * Здесь только данные — никакой логики расчёта (она целиком в engine.ts).
 */

export type Period = 'day' | 'week' | 'month' | 'year'

/** Базовая (учётная) единица ингредиента — в ней хранится вся себестоимость. */
export type BaseUnit = 'g' | 'ml' | 'pc'

/** Единица, которой пользователь оперирует при закупке и в техкарте. */
export type MeasureUnit = 'kg' | 'g' | 'l' | 'ml' | 'pc'

/** Режим расчёта продаж. Активен всегда ровно один — выручка режимов не складывается. */
export type SalesMode = 'menu' | 'avgcheck'

/** Экономическое поведение расхода. Не путать с периодичностью выплаты. */
export type CostBehavior = 'fixed' | 'variable'

export type PayFrequency = 'day' | 'week' | 'month'

export type VarExpenseType =
  | 'pct_revenue' /** % от (доли) выручки — эквайринг, агрегаторы */
  | 'per_order' /** сумма × количество заказов — упаковка */
  | 'per_guest' /** сумма × количество гостей — расходники */
  | 'fixed_period' /** фиксированная сумма за период */

export interface Business {
  name: string
  workingDaysPerMonth: number
  workingDaysPerWeek: number
  hoursPerDay: number
  seats: number
  currency: string
  /** Период, в котором показываются все отчёты по умолчанию. */
  planningPeriod: Period
  /** Желаемая операционная прибыль. */
  targetProfit: number
  targetProfitPeriod: Period
  /** Среднее количество гостей на один чек — для перевода гостей в заказы. */
  guestsPerOrder: number
  /** Среднее число позиций меню на гостя — нужно режиму «По меню», чтобы вывести трафик. */
  itemsPerGuest: number
}

export interface Ingredient {
  id: string
  name: string
  /** Учётная единица: в ней задаётся расход в техкарте. */
  baseUnit: BaseUnit
  /** Сколько закупочных единиц входит в закупку по цене purchasePrice. */
  purchaseQty: number
  purchaseUnit: MeasureUnit
  purchasePrice: number
  /** Потери / отход, %. Необязательно, 0 = без потерь. */
  wastePct: number
}

export interface RecipeLine {
  id: string
  ingredientId: string
  qty: number
  unit: MeasureUnit
}

export interface Category {
  id: string
  name: string
}

export interface Dish {
  id: string
  name: string
  categoryId: string
  price: number
  costMode: 'manual' | 'recipe'
  manualCost: number
  recipe: RecipeLine[]
  /** Продажи вводятся в любом периоде — остальные считаются автоматически. */
  salesQty: number
  salesPeriod: Period
  active: boolean
}

export interface Employee {
  id: string
  name: string
  role: string
  pay: number
  payFrequency: PayFrequency
  /** Рабочих дней в месяц (для дневной и недельной оплаты). */
  workDaysPerMonth: number
  active: boolean
  /** По умолчанию ФОТ — постоянный расход, независимо от периодичности выплаты. */
  behavior: CostBehavior
}

export interface FixedExpense {
  id: string
  name: string
  category: string
  amount: number
  period: Period
  active: boolean
}

export interface VariableExpense {
  id: string
  name: string
  type: VarExpenseType
  /** % (для pct_revenue) либо сумма (для остальных типов). */
  value: number
  /** Доля выручки, к которой применяется процент (напр. 70% безнала). */
  baseSharePct: number
  /** Период — только для type = 'fixed_period'. */
  period: Period
  active: boolean
  /** Переопределение поведения для точки безубыточности. null = авто по типу. */
  behavior: CostBehavior | null
}

export interface AvgCheckModel {
  guestsPerDay: number
  avgCheck: number
  foodCostPct: number
}

/** Набор «ручек» симулятора. Нули = базовая модель без изменений. */
export interface Adjustments {
  guestsPct: number
  avgCheckPct: number
  menuPricePct: number
  menuSalesPct: number
  /** Изменение себестоимости блюд / Food Cost, %. */
  cogsPct: number
  /** Изменение закупочных цен ингредиентов, % (только блюда с техкартой). */
  ingredientPricePct: number
  payrollPct: number
  /** Дополнительные сотрудники сверх штата. */
  extraStaff: number
  extraStaffCost: number
  fixedPct: number
  variablePct: number
}

export type ScenarioKind = 'current' | 'optimistic' | 'pessimistic' | 'custom'

export interface Scenario {
  id: string
  name: string
  kind: ScenarioKind
  adj: Adjustments
}

export interface Model {
  business: Business
  salesMode: SalesMode
  avgCheckModel: AvgCheckModel
  categories: Category[]
  dishes: Dish[]
  ingredients: Ingredient[]
  employees: Employee[]
  fixedExpenses: FixedExpense[]
  variableExpenses: VariableExpense[]
}
