/**
 * Факты Xonim → модель калькулятора.
 *
 * Цель — чтобы исходная операционная прибыль калькулятора сходилась с чистой
 * прибылью Xonim за тот же месяц, а каждое расхождение было названо:
 *
 *   операционная прибыль = чистая прибыль Xonim
 *                          + выплаченная зарплата − начисленная по табелю
 *                          − прибыль от партнёров
 *
 * (см. `reconcile`). Всё остальное переносится один в один.
 *
 * Правила раскладки:
 *  · Блюда — по средней цене меню за месяц и замороженной себестоимости.
 *    Разница между продажами по цене меню и выручкой Xonim (скидки и
 *    бесплатные бонусные порции) — отдельный расход «Скидки и бонусы» в % от
 *    выручки: цена в меню остаётся узнаваемой, а прибыль — точной.
 *  · Гости = чеки. Xonim не знает число гостей, поэтому «гостей на чек» = 1,
 *    а «позиций на гостя» — среднее число позиций в чеке.
 *  · Зарплата — по табелю: дневная ставка × отработанные дни. Расходы категории
 *    «Ish haqi» пропускаются, иначе зарплата считалась бы дважды.
 *  · Комиссии Uzum и Yandex, списания со склада и закупки «Masalliq» растут
 *    вместе с продажами — это % от выручки. Остальные расходы (аренда,
 *    коммунальные…) и питание сотрудников — постоянные.
 *  · Поставки партнёрам (школы, университеты) в модель не входят: они не
 *    связаны с гостями и чеками и исказили бы средний чек.
 */
import type { Translator } from '@/i18n'
import { emptyModel } from '@/core/defaults'
import type {
  Business,
  Category,
  Dish,
  Employee,
  FixedExpense,
  Model,
  VariableExpense,
} from '@/core/types'
import type { XonimFacts } from './facts'

/** Обычный месяц Xonim: шестидневка, воскресенье — выходной. */
const STANDARD_DAYS = 26
const STANDARD_WEEK = 6

/** Поля, которые пользователь задаёт сам: повторная загрузка их не трогает. */
export type KeptBusiness = Pick<
  Business,
  'targetProfit' | 'targetProfitPeriod' | 'planningPeriod' | 'hoursPerDay' | 'currency'
>

export function keptBusiness(b: Business): KeptBusiness {
  return {
    targetProfit: b.targetProfit,
    targetProfitPeriod: b.targetProfitPeriod,
    planningPeriod: b.planningPeriod,
    hoursPerDay: b.hoursPerDay,
    currency: b.currency,
  }
}

const round = (v: number, digits: number): number => {
  const f = 10 ** digits
  return Math.round(v * f) / f
}

const catId = (id: number) => `xonim_cat_${id}`

export function factsToModel(facts: XonimFacts, t: Translator, keep?: KeptBusiness): Model {
  const base = emptyModel(t.locale)
  const { sales } = facts
  const hasSales = sales.openDays > 0
  const openDays = hasSales ? sales.openDays : STANDARD_DAYS
  const calendarDays = facts.days > 0 ? facts.days : 30
  // Продажи по цене меню — база для всех «% от выручки».
  const menuTotal = facts.dishes.reduce((s, d) => s + d.menuValue, 0)

  const business: Business = {
    ...base.business,
    name: facts.branch.name,
    seats: facts.branch.seats,
    workingDaysPerMonth: openDays,
    workingDaysPerWeek: hasSales
      ? Math.min(7, Math.max(1, Math.round((openDays / calendarDays) * 7)))
      : STANDARD_WEEK,
    targetProfit: 0,
    targetProfitPeriod: 'month',
    planningPeriod: 'month',
    currency: '',
    guestsPerOrder: 1,
    itemsPerGuest:
      sales.orders > 0 && sales.items > 0 ? sales.items / sales.orders : base.business.itemsPerGuest,
    ...keep,
  }

  // Режим «по среднему чеку» тоже согласован: чек — по цене меню, как и
  // выручка в режиме «по меню», а скидки вычитаются той же строкой расходов.
  const avgCheckModel =
    sales.orders > 0 && menuTotal > 0
      ? {
          guestsPerDay: round(sales.orders / openDays, 1),
          avgCheck: Math.round(menuTotal / sales.orders),
          foodCostPct: round((facts.cogs / menuTotal) * 100, 2),
        }
      : base.avgCheckModel

  const categories: Category[] = facts.categories.map((c) => ({ id: catId(c.id), name: c.name }))

  const dishes: Dish[] = facts.dishes.map((d): Dish => {
    const sold = d.quantity > 0
    return {
      id: `xonim_dish_${d.id}`,
      name: d.name,
      categoryId: catId(d.categoryId),
      price: round(sold ? d.menuValue / d.quantity : d.price, 2),
      costMode: 'manual',
      manualCost: round(sold ? d.cost / d.quantity : d.unitCost, 2),
      recipe: [],
      salesQty: d.quantity,
      salesPeriod: 'month',
      active: true,
    }
  })

  const variableExpenses: VariableExpense[] = []
  const fixedExpenses: FixedExpense[] = []

  /** Расход, растущий вместе с продажами. Без продаж процент не из чего считать. */
  const ofRevenue = (id: string, name: string, monthly: number) => {
    if (Math.abs(monthly) < 0.5) return
    if (menuTotal > 0) {
      variableExpenses.push({
        id,
        name,
        type: 'pct_revenue',
        value: (monthly / menuTotal) * 100,
        baseSharePct: 100,
        period: 'month',
        active: true,
        behavior: null,
      })
    } else {
      fixedExpenses.push({ id, name, category: name, amount: monthly, period: 'month', active: true })
    }
  }

  ofRevenue('xonim_vx_discounts', t('xonim.vx.discounts'), menuTotal - sales.revenue)

  for (const c of facts.channels) {
    if (c.fee <= 0 || c.revenue <= 0) continue
    const id = `xonim_vx_fee_${c.channel}`
    const name = t('xonim.vx.platformFee', { name: c.label })
    // Ставка — как в договоре (30 %), а доля канала в выручке подобрана так,
    // чтобы сумма комиссии совпала с Xonim до сума.
    const rate = round((c.fee / c.revenue) * 100, 2)
    if (menuTotal > 0 && rate > 0) {
      variableExpenses.push({
        id,
        name,
        type: 'pct_revenue',
        value: rate,
        baseSharePct: Math.min(100, (c.fee / (rate / 100) / menuTotal) * 100),
        period: 'month',
        active: true,
        behavior: null,
      })
    } else {
      fixedExpenses.push({ id, name, category: name, amount: c.fee, period: 'month', active: true })
    }
  }

  ofRevenue('xonim_vx_waste', t('xonim.vx.waste'), facts.waste)

  facts.expenses.forEach((e, i) => {
    const name = e.category.trim() || t('xonim.fx.other')
    if (e.kind === 'salary') return
    if (e.kind === 'produce') {
      ofRevenue(`xonim_vx_expense_${i}`, name, e.amount)
      return
    }
    fixedExpenses.push({
      id: `xonim_fx_${i}`,
      name,
      category: name,
      amount: e.amount,
      period: 'month',
      active: true,
    })
  })

  if (facts.staffMeals > 0) {
    const name = t('xonim.fx.staffMeals')
    fixedExpenses.push({
      id: 'xonim_fx_staff_meals',
      name,
      category: name,
      amount: facts.staffMeals,
      period: 'month',
      active: true,
    })
  }

  // Кто работал в месяце — с фактической ставкой и днями. Кто числится, но не
  // выходил, — выключен: его можно включить и посмотреть «а если на полный месяц».
  const employees: Employee[] = facts.payroll.map((p): Employee => {
    const worked = p.days > 0
    return {
      id: `xonim_emp_${p.id}`,
      name: p.name,
      role: p.position,
      pay: worked ? round(p.accrued / p.days, 2) : p.dailyWage,
      payFrequency: 'day',
      workDaysPerMonth: worked ? p.days : STANDARD_DAYS,
      active: worked,
      behavior: 'fixed',
    }
  })

  return {
    business,
    salesMode: 'menu',
    avgCheckModel,
    categories,
    dishes,
    // Рецепты Xonim считаются партиями с ценой на каждой строке — один к
    // одному в справочник ингредиентов они не ложатся. Себестоимость блюд
    // приходит готовой, а шоки цен моделирует ручка «Себестоимость» симулятора.
    ingredients: [],
    employees,
    fixedExpenses,
    variableExpenses,
  }
}

/* ─────────────────────────────── Сверка ─────────────────────────────── */

export interface Reconciliation {
  /** Чистая прибыль на странице «Общие финансы» Xonim. */
  xonimProfit: number
  /** Расходы категории «Ish haqi» — входят в прибыль Xonim. */
  salaryPaid: number
  /** Начислено по табелю — входит в калькулятор вместо выплат. */
  salaryAccrued: number
  /** Поставки партнёрам: в прибыли Xonim есть, в калькуляторе нет. */
  partnerProfit: number
  /** Какой должна получиться операционная прибыль калькулятора. */
  expected: number
  /** Выручка Xonim — масштаб для допуска округлений. */
  revenue: number
}

export function reconcile(facts: XonimFacts): Reconciliation {
  const salaryPaid = facts.expenses
    .filter((e) => e.kind === 'salary')
    .reduce((s, e) => s + e.amount, 0)
  const salaryAccrued = facts.payroll
    .filter((p) => p.days > 0)
    .reduce((s, p) => s + p.accrued, 0)
  const partnerProfit = facts.partners.profit
  return {
    xonimProfit: facts.netProfit,
    salaryPaid,
    salaryAccrued,
    partnerProfit,
    expected: facts.netProfit + salaryPaid - salaryAccrued - partnerProfit,
    revenue: facts.sales.revenue,
  }
}

/** Цены округлены до тийинов — такие копейки не должны выглядеть расхождением. */
export function reconciles(actual: number, r: Reconciliation): boolean {
  return Math.abs(actual - r.expected) <= Math.max(1000, Math.abs(r.revenue) * 1e-5)
}
