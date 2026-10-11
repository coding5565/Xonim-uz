import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { ZERO_ADJ, defaultModel, defaultScenarios, emptyModel, uid } from '@/core/defaults'
import { setFormatLocale } from '@/core/format'
import { parseModel } from '@/core/validate'
import { detectLocale, isLocale, type Locale } from '@/i18n/locales'
import { XONIM } from '@/xonim/config'
import type { Reconciliation } from '@/xonim/toModel'
import type {
  Adjustments,
  Business,
  Category,
  Dish,
  Employee,
  FixedExpense,
  Ingredient,
  Model,
  Period,
  RecipeLine,
  SalesMode,
  Scenario,
  VariableExpense,
} from '@/core/types'

export type Theme = 'light' | 'dark'

/** Связь модели с Xonim: какой месяц загружен и что с ним стало потом. */
export interface XonimLink {
  /** 'YYYY-MM' */
  month: string
  complete: boolean
  /** Дней с продажами — для предупреждения о незаконченном месяце. */
  openDays: number
  importedAt: string
  /** Модель менялась после загрузки — автообновление её не перезапишет. */
  edited: boolean
  recon: Reconciliation
}

/** То, что реально попадает в localStorage (см. persistedPart). */
type PersistedState = Pick<
  AppState,
  'scenarios' | 'activeScenarioId' | 'period' | 'theme' | 'locale'
> & { model?: Model }

/**
 * Что пишется в localStorage.
 *
 * Внутри Xonim модель — это финансы ресторана и зарплаты сотрудников. Она
 * приходит с сервера при каждом открытии и на диск не попадает: на общем
 * кассовом компьютере её нельзя будет достать из localStorage после ухода
 * владельца. Сценарии — только проценты и ручки симулятора, их храним всегда.
 */
export function persistedPart(s: AppState, xonim: boolean): PersistedState {
  const kept = {
    scenarios: s.scenarios,
    activeScenarioId: s.activeScenarioId,
    period: s.period,
    theme: s.theme,
    locale: s.locale,
  }
  return xonim ? kept : { ...kept, model: s.model }
}

const initialLocale = detectLocale()
// Форматирование чисел должно знать язык ещё до первого рендера.
setFormatLocale(initialLocale)

export interface AppState {
  model: Model
  scenarios: Scenario[]
  activeScenarioId: string
  /** Период отображения отчётов. */
  period: Period
  theme: Theme
  locale: Locale
  /** Только в режиме Xonim: откуда взята модель. Живёт до закрытия вкладки. */
  xonim: XonimLink | null

  /* Бизнес */
  updateBusiness: (patch: Partial<Business>) => void
  setSalesMode: (mode: SalesMode) => void
  updateAvgCheck: (patch: Partial<Model['avgCheckModel']>) => void
  setPeriod: (p: Period) => void
  toggleTheme: () => void
  setLocale: (l: Locale) => void

  /* Справочники */
  addCategory: (name: string) => string
  updateCategory: (id: string, patch: Partial<Category>) => void
  removeCategory: (id: string) => void

  addIngredient: (patch?: Partial<Ingredient>) => string
  updateIngredient: (id: string, patch: Partial<Ingredient>) => void
  removeIngredient: (id: string) => void

  addDish: (patch?: Partial<Dish>) => string
  updateDish: (id: string, patch: Partial<Dish>) => void
  removeDish: (id: string) => void
  duplicateDish: (id: string, copyLabel: string) => void
  addRecipeLine: (dishId: string, line?: Partial<RecipeLine>) => void
  updateRecipeLine: (dishId: string, lineId: string, patch: Partial<RecipeLine>) => void
  removeRecipeLine: (dishId: string, lineId: string) => void

  addEmployee: (patch?: Partial<Employee>) => void
  updateEmployee: (id: string, patch: Partial<Employee>) => void
  removeEmployee: (id: string) => void

  addFixedExpense: (patch?: Partial<FixedExpense>) => void
  updateFixedExpense: (id: string, patch: Partial<FixedExpense>) => void
  removeFixedExpense: (id: string) => void

  addVariableExpense: (patch?: Partial<VariableExpense>) => void
  updateVariableExpense: (id: string, patch: Partial<VariableExpense>) => void
  removeVariableExpense: (id: string) => void

  /* Сценарии и симулятор */
  setActiveScenario: (id: string) => void
  patchAdjustments: (patch: Partial<Adjustments>) => void
  resetAdjustments: () => void
  addScenario: (name: string, from?: Adjustments) => void
  renameScenario: (id: string, name: string) => void
  removeScenario: (id: string) => void

  /* Данные целиком */
  loadDemo: () => void
  clearAll: () => void
  importModel: (m: Model) => void
  /** Модель из Xonim. Одним обновлением — так правка отличима от загрузки. */
  applyXonim: (m: Model, link: XonimLink) => void
}

const upd = <T extends { id: string }>(list: T[], id: string, patch: Partial<T>): T[] =>
  list.map((x) => (x.id === id ? { ...x, ...patch } : x))

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      model: defaultModel(initialLocale),
      scenarios: defaultScenarios(),
      activeScenarioId: 'sc_current',
      period: 'month',
      theme: 'light',
      locale: initialLocale,
      xonim: null,

      updateBusiness: (patch) =>
        set((s) => ({ model: { ...s.model, business: { ...s.model.business, ...patch } } })),

      setSalesMode: (mode) => set((s) => ({ model: { ...s.model, salesMode: mode } })),

      updateAvgCheck: (patch) =>
        set((s) => ({ model: { ...s.model, avgCheckModel: { ...s.model.avgCheckModel, ...patch } } })),

      setPeriod: (p) => set({ period: p }),

      toggleTheme: () => set((s) => ({ theme: s.theme === 'light' ? 'dark' : 'light' })),

      /**
       * Язык меняет только интерфейс и форматирование чисел.
       * Введённые пользователем названия блюд, сотрудников и расходов не трогаем.
       */
      setLocale: (l) => {
        setFormatLocale(l)
        set({ locale: l })
      },

      /* ── Категории ── */
      addCategory: (name) => {
        const id = uid('cat')
        set((s) => ({ model: { ...s.model, categories: [...s.model.categories, { id, name }] } }))
        return id
      },
      updateCategory: (id, patch) =>
        set((s) => ({ model: { ...s.model, categories: upd(s.model.categories, id, patch) } })),
      removeCategory: (id) =>
        set((s) => ({
          model: {
            ...s.model,
            categories: s.model.categories.filter((c) => c.id !== id),
            // Блюда удалённой категории не теряются — они просто становятся «без категории».
            dishes: s.model.dishes.map((d) => (d.categoryId === id ? { ...d, categoryId: '' } : d)),
          },
        })),

      /* ── Ингредиенты ── */
      addIngredient: (patch) => {
        const id = uid('ing')
        const ing: Ingredient = {
          id,
          name: '',
          baseUnit: 'g',
          purchaseQty: 1,
          purchaseUnit: 'kg',
          purchasePrice: 0,
          wastePct: 0,
          ...patch,
        }
        set((s) => ({ model: { ...s.model, ingredients: [...s.model.ingredients, ing] } }))
        return id
      },
      updateIngredient: (id, patch) =>
        set((s) => ({ model: { ...s.model, ingredients: upd(s.model.ingredients, id, patch) } })),
      removeIngredient: (id) =>
        set((s) => ({
          model: {
            ...s.model,
            ingredients: s.model.ingredients.filter((i) => i.id !== id),
            dishes: s.model.dishes.map((d) => ({
              ...d,
              recipe: d.recipe.filter((l) => l.ingredientId !== id),
            })),
          },
        })),

      /* ── Блюда ── */
      addDish: (patch) => {
        const id = uid('dish')
        const s0 = get()
        const dish: Dish = {
          id,
          name: '',
          categoryId: s0.model.categories[0]?.id ?? '',
          price: 0,
          costMode: 'manual',
          manualCost: 0,
          recipe: [],
          salesQty: 0,
          salesPeriod: 'day',
          active: true,
          ...patch,
        }
        set((s) => ({ model: { ...s.model, dishes: [...s.model.dishes, dish] } }))
        return id
      },
      updateDish: (id, patch) =>
        set((s) => ({ model: { ...s.model, dishes: upd(s.model.dishes, id, patch) } })),
      removeDish: (id) =>
        set((s) => ({ model: { ...s.model, dishes: s.model.dishes.filter((d) => d.id !== id) } })),
      duplicateDish: (id, copyLabel) =>
        set((s) => {
          const src = s.model.dishes.find((d) => d.id === id)
          if (!src) return s
          const copy: Dish = {
            ...src,
            id: uid('dish'),
            name: `${src.name} ${copyLabel}`.trim(),
            recipe: src.recipe.map((l) => ({ ...l, id: uid('r') })),
          }
          const i = s.model.dishes.findIndex((d) => d.id === id)
          const dishes = [...s.model.dishes]
          dishes.splice(i + 1, 0, copy)
          return { model: { ...s.model, dishes } }
        }),

      addRecipeLine: (dishId, line) =>
        set((s) => {
          const first = s.model.ingredients[0]
          const newLine: RecipeLine = {
            id: uid('r'),
            ingredientId: first?.id ?? '',
            qty: 0,
            unit: first?.baseUnit === 'ml' ? 'ml' : first?.baseUnit === 'pc' ? 'pc' : 'g',
            ...line,
          }
          return {
            model: {
              ...s.model,
              dishes: s.model.dishes.map((d) =>
                d.id === dishId ? { ...d, recipe: [...d.recipe, newLine] } : d,
              ),
            },
          }
        }),
      updateRecipeLine: (dishId, lineId, patch) =>
        set((s) => ({
          model: {
            ...s.model,
            dishes: s.model.dishes.map((d) =>
              d.id === dishId ? { ...d, recipe: upd(d.recipe, lineId, patch) } : d,
            ),
          },
        })),
      removeRecipeLine: (dishId, lineId) =>
        set((s) => ({
          model: {
            ...s.model,
            dishes: s.model.dishes.map((d) =>
              d.id === dishId ? { ...d, recipe: d.recipe.filter((l) => l.id !== lineId) } : d,
            ),
          },
        })),

      /* ── Сотрудники ── */
      addEmployee: (patch) =>
        set((s) => ({
          model: {
            ...s.model,
            employees: [
              ...s.model.employees,
              {
                id: uid('emp'),
                name: '',
                role: '',
                pay: 0,
                payFrequency: 'month',
                workDaysPerMonth: s.model.business.workingDaysPerMonth,
                active: true,
                behavior: 'fixed',
                ...patch,
              },
            ],
          },
        })),
      updateEmployee: (id, patch) =>
        set((s) => ({ model: { ...s.model, employees: upd(s.model.employees, id, patch) } })),
      removeEmployee: (id) =>
        set((s) => ({
          model: { ...s.model, employees: s.model.employees.filter((e) => e.id !== id) },
        })),

      /* ── Постоянные расходы ── */
      addFixedExpense: (patch) =>
        set((s) => ({
          model: {
            ...s.model,
            fixedExpenses: [
              ...s.model.fixedExpenses,
              {
                id: uid('fx'),
                name: '',
                category: '',
                amount: 0,
                period: 'month',
                active: true,
                ...patch,
              },
            ],
          },
        })),
      updateFixedExpense: (id, patch) =>
        set((s) => ({ model: { ...s.model, fixedExpenses: upd(s.model.fixedExpenses, id, patch) } })),
      removeFixedExpense: (id) =>
        set((s) => ({
          model: { ...s.model, fixedExpenses: s.model.fixedExpenses.filter((x) => x.id !== id) },
        })),

      /* ── Переменные расходы ── */
      addVariableExpense: (patch) =>
        set((s) => ({
          model: {
            ...s.model,
            variableExpenses: [
              ...s.model.variableExpenses,
              {
                id: uid('vx'),
                name: '',
                type: 'pct_revenue',
                value: 0,
                baseSharePct: 100,
                period: 'month',
                active: true,
                behavior: null,
                ...patch,
              },
            ],
          },
        })),
      updateVariableExpense: (id, patch) =>
        set((s) => ({
          model: { ...s.model, variableExpenses: upd(s.model.variableExpenses, id, patch) },
        })),
      removeVariableExpense: (id) =>
        set((s) => ({
          model: {
            ...s.model,
            variableExpenses: s.model.variableExpenses.filter((x) => x.id !== id),
          },
        })),

      /* ── Сценарии ── */
      setActiveScenario: (id) => set({ activeScenarioId: id }),

      /**
       * «Текущий» сценарий — это база, он всегда остаётся нетронутым.
       * Любая правка ручек при активном «Текущем» уходит в «Свой сценарий».
       */
      patchAdjustments: (patch) =>
        set((s) => {
          const active = s.scenarios.find((x) => x.id === s.activeScenarioId)
          if (!active || active.kind === 'current') {
            const custom = s.scenarios.find((x) => x.kind === 'custom')
            const base = active?.adj ?? ZERO_ADJ
            if (!custom) return s
            return {
              activeScenarioId: custom.id,
              scenarios: s.scenarios.map((x) =>
                x.id === custom.id ? { ...x, adj: { ...base, ...patch } } : x,
              ),
            }
          }
          return {
            scenarios: s.scenarios.map((x) =>
              x.id === active.id ? { ...x, adj: { ...x.adj, ...patch } } : x,
            ),
          }
        }),

      resetAdjustments: () =>
        set((s) => ({
          scenarios: s.scenarios.map((x) =>
            x.id === s.activeScenarioId ? { ...x, adj: { ...ZERO_ADJ } } : x,
          ),
        })),

      addScenario: (name, from) =>
        set((s) => {
          const sc: Scenario = {
            id: uid('sc'),
            name,
            kind: 'custom',
            adj: { ...(from ?? ZERO_ADJ) },
          }
          return { scenarios: [...s.scenarios, sc], activeScenarioId: sc.id }
        }),
      renameScenario: (id, name) =>
        set((s) => ({ scenarios: s.scenarios.map((x) => (x.id === id ? { ...x, name } : x)) })),
      removeScenario: (id) =>
        set((s) => {
          const target = s.scenarios.find((x) => x.id === id)
          // Базовые сценарии удалить нельзя — на них строится сравнение.
          if (
            !target ||
            target.kind !== 'custom' ||
            s.scenarios.filter((x) => x.kind === 'custom').length <= 1
          ) {
            return s
          }
          const scenarios = s.scenarios.filter((x) => x.id !== id)
          return {
            scenarios,
            activeScenarioId: s.activeScenarioId === id ? 'sc_current' : s.activeScenarioId,
          }
        }),

      /* ── Данные ── */
      loadDemo: () => set((s) => ({ model: defaultModel(s.locale) })),
      clearAll: () => set((s) => ({ model: emptyModel(s.locale) })),
      importModel: (m) => set({ model: m }),
      applyXonim: (m, link) => set({ model: m, xonim: link }),
    }),
    {
      name: 'cafe-financial-calculator',
      version: 2,
      partialize: (s) => persistedPart(s, XONIM),
      /**
       * Сохранённая модель проверяется так же, как импортируемый файл: одна
       * испорченная запись в localStorage не должна навсегда ронять приложение.
       */
      merge: (persisted, current) => {
        const saved = (persisted ?? {}) as Partial<PersistedState>
        const model = saved.model === undefined ? current.model : parseModel(saved.model)
        return { ...current, ...saved, model: model ?? current.model }
      },
      /** Версия 1 не знала о языке: валюта и названия сценариев были зашиты по-русски. */
      migrate: (persisted, version) => {
        const state = persisted as PersistedState
        if (version < 2) {
          if (state.model?.business && state.model.business.currency === 'сум') {
            state.model.business.currency = ''
          }
          const BASE_NAMES = ['Текущий', 'Оптимистичный', 'Пессимистичный', 'Свой сценарий']
          state.scenarios = state.scenarios?.map((sc) =>
            sc.kind !== 'custom' || sc.id === 'sc_custom'
              ? { ...sc, name: BASE_NAMES.includes(sc.name) ? '' : sc.name }
              : sc,
          )
          state.locale = initialLocale
        }
        return state
      },
      onRehydrateStorage: () => (state) => {
        // После восстановления из localStorage язык форматирования может отличаться.
        if (state && isLocale(state.locale)) setFormatLocale(state.locale)
      },
    },
  ),
)

export const useActiveScenario = (): Scenario => {
  const scenarios = useAppStore((s) => s.scenarios)
  const id = useAppStore((s) => s.activeScenarioId)
  return scenarios.find((x) => x.id === id) ?? scenarios[0]
}
