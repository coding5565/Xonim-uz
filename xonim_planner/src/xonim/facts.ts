/**
 * Факты одного месяца из Xonim — ответ `GET /api/v1/finance/planner/`.
 *
 * Сервер отдаёт только то, что знает точно: продажи по блюдам, начисленную
 * по табелю зарплату, расходы по категориям, комиссии платформ. Как из этого
 * собрать модель (что постоянное, что переменное) — решает `toModel.ts`.
 *
 * Суммы приходят строками (`"125000.00"`): Xonim считает деньги в Decimal и
 * не отдаёт числа с плавающей точкой. Разбор строгий — испорченный ответ
 * должен остановить загрузку, а не превратиться в нули в отчёте.
 */

/** Версия формата, которую понимает калькулятор. */
export const FACTS_VERSION = 1

export type ExpenseKind = 'salary' | 'produce' | 'other'

export interface XonimFacts {
  version: number
  /** 'YYYY-MM' */
  month: string
  /** Месяц закончился — цифры полные. */
  complete: boolean
  /** Календарных дней в выборке (для текущего месяца — по сегодняшний день). */
  days: number
  /** Месяцы с данными, новые первыми. */
  months: string[]
  branch: { name: string; seats: number }
  sales: {
    /** Выручка Xonim: сумма оплаченных счетов после скидок, без сервисного сбора. */
    revenue: number
    orders: number
    items: number
    discounts: number
    /** Дней, в которые были продажи. */
    openDays: number
  }
  cogs: number
  platformFee: number
  waste: number
  staffMeals: number
  partners: { revenue: number; cogs: number; profit: number }
  /** Чистая прибыль со страницы «Общие финансы» Xonim за тот же период. */
  netProfit: number
  channels: Array<{ channel: string; label: string; revenue: number; fee: number; orders: number }>
  expenses: Array<{ category: string; amount: number; kind: ExpenseKind }>
  categories: Array<{ id: number; name: string }>
  dishes: Array<{
    id: number
    name: string
    categoryId: number
    /** Текущая цена меню. */
    price: number
    /** Себестоимость порции по сегодняшнему рецепту — для блюд без продаж. */
    unitCost: number
    archived: boolean
    quantity: number
    /** Продажи по цене меню на момент продажи (бонусные порции тоже). */
    menuValue: number
    /** Себестоимость проданного, замороженная в момент продажи. */
    cost: number
  }>
  payroll: Array<{
    id: number
    name: string
    position: string
    active: boolean
    dailyWage: number
    /** Отработано дней в периоде. */
    days: number
    /** Начислено по табелю за период. */
    accrued: number
  }>
}

export class FactsError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'FactsError'
  }
}

type Obj = Record<string, unknown>

function obj(v: unknown, path: string): Obj {
  if (typeof v !== 'object' || v === null || Array.isArray(v)) {
    throw new FactsError(`${path}: ожидается объект`)
  }
  return v as Obj
}

function list(v: unknown, path: string): unknown[] {
  if (!Array.isArray(v)) throw new FactsError(`${path}: ожидается список`)
  return v
}

/** Число из числа или денежной строки Xonim. */
function amount(v: unknown, path: string): number {
  const n = typeof v === 'number' ? v : typeof v === 'string' && v.trim() !== '' ? Number(v) : NaN
  if (!Number.isFinite(n)) throw new FactsError(`${path}: ожидается число`)
  return n
}

function text(v: unknown, path: string): string {
  if (typeof v !== 'string') throw new FactsError(`${path}: ожидается строка`)
  return v
}

function flag(v: unknown, path: string): boolean {
  if (typeof v !== 'boolean') throw new FactsError(`${path}: ожидается да/нет`)
  return v
}

const MONTH = /^\d{4}-\d{2}$/
const KINDS: ExpenseKind[] = ['salary', 'produce', 'other']

export function parseFacts(raw: unknown): XonimFacts {
  const r = obj(raw, 'ответ')
  const version = amount(r.version, 'version')
  if (version !== FACTS_VERSION) {
    throw new FactsError(`неизвестная версия формата: ${version}`)
  }
  const month = text(r.month, 'month')
  if (!MONTH.test(month)) throw new FactsError('month: ожидается YYYY-MM')

  const branch = obj(r.branch, 'branch')
  const sales = obj(r.sales, 'sales')
  const partners = obj(r.partners, 'partners')

  return {
    version,
    month,
    complete: flag(r.complete, 'complete'),
    days: amount(r.days, 'days'),
    months: list(r.months, 'months').map((m, i) => {
      const key = text(m, `months[${i}]`)
      if (!MONTH.test(key)) throw new FactsError(`months[${i}]: ожидается YYYY-MM`)
      return key
    }),
    branch: { name: text(branch.name, 'branch.name'), seats: amount(branch.seats, 'branch.seats') },
    sales: {
      revenue: amount(sales.revenue, 'sales.revenue'),
      orders: amount(sales.orders, 'sales.orders'),
      items: amount(sales.items, 'sales.items'),
      discounts: amount(sales.discounts, 'sales.discounts'),
      openDays: amount(sales.open_days, 'sales.open_days'),
    },
    cogs: amount(r.cogs, 'cogs'),
    platformFee: amount(r.platform_fee, 'platform_fee'),
    waste: amount(r.waste, 'waste'),
    staffMeals: amount(r.staff_meals, 'staff_meals'),
    partners: {
      revenue: amount(partners.revenue, 'partners.revenue'),
      cogs: amount(partners.cogs, 'partners.cogs'),
      profit: amount(partners.profit, 'partners.profit'),
    },
    netProfit: amount(r.net_profit, 'net_profit'),
    channels: list(r.channels, 'channels').map((raw, i) => {
      const c = obj(raw, `channels[${i}]`)
      return {
        channel: text(c.channel, `channels[${i}].channel`),
        label: text(c.label, `channels[${i}].label`),
        revenue: amount(c.revenue, `channels[${i}].revenue`),
        fee: amount(c.fee, `channels[${i}].fee`),
        orders: amount(c.orders, `channels[${i}].orders`),
      }
    }),
    expenses: list(r.expenses, 'expenses').map((raw, i) => {
      const e = obj(raw, `expenses[${i}]`)
      const kind = text(e.kind, `expenses[${i}].kind`) as ExpenseKind
      if (!KINDS.includes(kind)) throw new FactsError(`expenses[${i}].kind: ${kind}`)
      return {
        category: text(e.category, `expenses[${i}].category`),
        amount: amount(e.amount, `expenses[${i}].amount`),
        kind,
      }
    }),
    categories: list(r.categories, 'categories').map((raw, i) => {
      const c = obj(raw, `categories[${i}]`)
      return { id: amount(c.id, `categories[${i}].id`), name: text(c.name, `categories[${i}].name`) }
    }),
    dishes: list(r.dishes, 'dishes').map((raw, i) => {
      const d = obj(raw, `dishes[${i}]`)
      const p = `dishes[${i}]`
      return {
        id: amount(d.id, `${p}.id`),
        name: text(d.name, `${p}.name`),
        categoryId: amount(d.category_id, `${p}.category_id`),
        price: amount(d.price, `${p}.price`),
        unitCost: amount(d.unit_cost, `${p}.unit_cost`),
        archived: flag(d.archived, `${p}.archived`),
        quantity: amount(d.quantity, `${p}.quantity`),
        menuValue: amount(d.menu_value, `${p}.menu_value`),
        cost: amount(d.cost, `${p}.cost`),
      }
    }),
    payroll: list(r.payroll, 'payroll').map((raw, i) => {
      const e = obj(raw, `payroll[${i}]`)
      const p = `payroll[${i}]`
      return {
        id: amount(e.id, `${p}.id`),
        name: text(e.name, `${p}.name`),
        position: text(e.position, `${p}.position`),
        active: flag(e.active, `${p}.active`),
        dailyWage: amount(e.daily_wage, `${p}.daily_wage`),
        days: amount(e.days, `${p}.days`),
        accrued: amount(e.accrued, `${p}.accrued`),
      }
    }),
  }
}
