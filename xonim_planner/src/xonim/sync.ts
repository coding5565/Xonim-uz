/**
 * Связь с Xonim во время работы: проверка входа, загрузка фактов месяца,
 * отслеживание ручных правок модели и общий с Xonim язык интерфейса.
 */
import { create } from 'zustand'
import { getTranslator } from '@/i18n'
import { isLocale, type Locale } from '@/i18n/locales'
import { useAppStore } from '@/store/useAppStore'
import { XonimAuthError, fetchFacts, fetchRole } from './api'
import { XONIM_LANG_KEY } from './config'
import type { XonimFacts } from './facts'
import { factsToModel, keptBusiness, reconcile } from './toModel'

/**
 * checking  — ждём ответа Xonim;
 * owner     — суперадмин, можно работать;
 * forbidden — вошёл кассир или повар;
 * anonymous — входа нет;
 * offline   — Xonim не ответил, проверить вход нельзя.
 */
export type Access = 'checking' | 'owner' | 'forbidden' | 'anonymous' | 'offline'

interface XonimRuntime {
  access: Access
  loading: boolean
  /** Последняя загрузка не удалась. */
  failed: boolean
  /** Месяцы с данными в Xonim, новые первыми. */
  months: string[]
  /** Свежие факты, не применённые из-за ручных правок модели. */
  pending: XonimFacts | null
}

export const useXonim = create<XonimRuntime>(() => ({
  access: 'checking',
  loading: false,
  failed: false,
  months: [],
  pending: null,
}))

/** Применяет факты к модели. Цель по прибыли и прочие свои настройки сохраняются. */
export function applyFacts(facts: XonimFacts): void {
  const app = useAppStore.getState()
  const keep = app.xonim ? keptBusiness(app.model.business) : undefined
  app.applyXonim(factsToModel(facts, getTranslator(app.locale), keep), {
    month: facts.month,
    complete: facts.complete,
    openDays: facts.sales.openDays,
    importedAt: new Date().toISOString(),
    edited: false,
    recon: reconcile(facts),
  })
  useXonim.setState({ pending: null })
}

// Ответ на старый запрос не должен перезаписать ответ на новый.
let latest = 0

/**
 * Загружает месяц из Xonim; без `month` сервер берёт последний полный.
 * `auto` — загрузка при открытии: ручные правки модели она не стирает, а
 * откладывает свежие данные в `pending` до решения пользователя.
 */
export async function loadMonth(month?: string, { auto = false } = {}): Promise<void> {
  const request = ++latest
  useXonim.setState({ loading: true, failed: false })
  try {
    const facts = await fetchFacts(month)
    if (request !== latest) return
    useXonim.setState({ months: facts.months })
    if (auto && useAppStore.getState().xonim?.edited) useXonim.setState({ pending: facts })
    else applyFacts(facts)
  } catch (err) {
    if (request !== latest) return
    if (err instanceof XonimAuthError) useXonim.setState({ access: 'anonymous' })
    else useXonim.setState({ failed: true })
  } finally {
    if (request === latest) useXonim.setState({ loading: false })
  }
}

/** Проверяет вход; суперадмину сразу подгружает свежие данные. */
export async function checkAccess(): Promise<void> {
  useXonim.setState({ access: 'checking' })
  try {
    const role = await fetchRole()
    if (role !== 'owner') {
      useXonim.setState({ access: 'forbidden' })
      return
    }
  } catch (err) {
    useXonim.setState({ access: err instanceof XonimAuthError ? 'anonymous' : 'offline' })
    return
  }
  useXonim.setState({ access: 'owner' })
  await loadMonth(undefined, { auto: true })
}

/** Язык Xonim. Если его ещё не выбирали, Xonim показывает узбекский. */
function xonimLocale(): Locale {
  try {
    const stored = localStorage.getItem(XONIM_LANG_KEY)
    if (isLocale(stored)) return stored
  } catch {
    // Закрытое хранилище (приватный режим) — остаёмся на языке Xonim по умолчанию.
  }
  return 'uz'
}

let started = false

/** Запуск режима Xonim. Вызывается один раз, до первой отрисовки. */
export function startXonim(): void {
  if (started) return
  started = true

  // Открыли калькулятор из узбекского Xonim — он тоже на узбекском.
  const app = useAppStore.getState()
  const locale = xonimLocale()
  if (app.locale !== locale) app.setLocale(locale)

  useAppStore.subscribe((s, prev) => {
    // И обратно: язык, выбранный здесь, Xonim подхватит при следующем открытии.
    if (s.locale !== prev.locale) {
      try {
        localStorage.setItem(XONIM_LANG_KEY, s.locale)
      } catch {
        // Без хранилища язык просто не запомнится.
      }
    }
    // Правка модели после загрузки. Сама загрузка меняет модель и связь
    // одним обновлением — её здесь отличаем по новой связи.
    if (s.model !== prev.model && s.xonim && s.xonim === prev.xonim && !s.xonim.edited) {
      useAppStore.setState({ xonim: { ...s.xonim, edited: true } })
    }
  })

  void checkAccess()
}
