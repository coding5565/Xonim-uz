// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defaultModel, defaultScenarios } from '@/core/defaults'
import { setFormatLocale } from '@/core/format'
import { getTranslator } from '@/i18n'
import { ru } from '@/i18n/ru'
import { LOCALES, type Locale } from '@/i18n/locales'
import { useAppStore } from '@/store/useAppStore'
import { EMPTY_MONTH, SEPTEMBER } from './__fixtures__/september'
import { parseFacts } from './facts'
import { applyFacts, checkAccess, loadMonth, startXonim, useXonim } from './sync'
import { XonimBanner } from './XonimBanner'
import { XonimCard } from './XonimCard'
import { XonimGate } from './XonimGate'

const DICT_KEYS = Object.keys(ru)

/** Ответ fetch: ровно то, что читает api.ts. */
const reply = (body: unknown, status = 200) => ({
  ok: status >= 200 && status < 300,
  status,
  json: async () => body,
})

/** Подменяет fetch: адрес → ответ; всё прочее — 404. */
function serve(routes: Record<string, () => unknown>) {
  const fetchMock = vi.fn(async (url: string) => {
    for (const [prefix, answer] of Object.entries(routes)) {
      if (url.startsWith(prefix)) return answer()
    }
    return reply({ detail: 'not found' }, 404)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

const ME = '/api/v1/auth/me/'
const FACTS = '/api/v1/finance/planner/'

function reset(locale: Locale = 'ru') {
  setFormatLocale(locale)
  useAppStore.setState({
    locale,
    model: defaultModel(locale),
    scenarios: defaultScenarios(),
    activeScenarioId: 'sc_current',
    period: 'month',
    xonim: null,
  })
  useXonim.setState({ access: 'checking', loading: false, failed: false, months: [], pending: null })
}

beforeEach(() => reset())
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('вход через Xonim', () => {
  it('суперадмин сразу получает последний полный месяц', async () => {
    serve({ [ME]: () => reply({ role: 'owner' }), [FACTS]: () => reply(SEPTEMBER) })
    await checkAccess()
    expect(useXonim.getState().access).toBe('owner')
    expect(useXonim.getState().months).toEqual(['2026-10', '2026-09'])
    const app = useAppStore.getState()
    expect(app.xonim).toMatchObject({ month: '2026-09', complete: true, edited: false })
    expect(app.model.business.name).toBe('Xonim')
    expect(app.model.dishes.map((d) => d.name)).toContain('Osh')
  })

  it('кассир не получает финансовых данных', async () => {
    const fetchMock = serve({ [ME]: () => reply({ role: 'cashier' }), [FACTS]: () => reply(SEPTEMBER) })
    await checkAccess()
    expect(useXonim.getState().access).toBe('forbidden')
    expect(fetchMock.mock.calls.some(([url]) => String(url).startsWith(FACTS))).toBe(false)
    expect(useAppStore.getState().xonim).toBeNull()
  })

  it('без входа — экран входа, без связи — повтор', async () => {
    serve({ [ME]: () => reply({ detail: 'no' }, 403) })
    await checkAccess()
    expect(useXonim.getState().access).toBe('anonymous')

    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('offline'))))
    await checkAccess()
    expect(useXonim.getState().access).toBe('offline')
  })

  it('сбой загрузки не трогает сохранённую модель', async () => {
    applyFacts(parseFacts(SEPTEMBER))
    const before = useAppStore.getState().model
    serve({ [FACTS]: () => reply({ detail: 'boom' }, 500) })
    await loadMonth()
    expect(useXonim.getState().failed).toBe(true)
    expect(useAppStore.getState().model).toBe(before)
  })
})

describe('экран-заслон', () => {
  const app = () => render(<XonimGate><p>калькулятор</p></XonimGate>)

  it('пускает только подтверждённого суперадмина с данными', () => {
    useXonim.setState({ access: 'owner' })
    app()
    // Данных из Xonim ещё нет — сохранённую в браузере модель не показываем.
    expect(screen.queryByText('калькулятор')).toBeNull()
    expect(screen.getByText(getTranslator('ru')('xonim.loadingFirst'))).toBeTruthy()
    cleanup()

    applyFacts(parseFacts(SEPTEMBER))
    app()
    expect(screen.getByText('калькулятор')).toBeTruthy()
  })

  it.each([
    ['anonymous', 'xonim.loginTitle'],
    ['forbidden', 'xonim.forbiddenTitle'],
    ['offline', 'xonim.offlineTitle'],
    ['checking', 'xonim.checking'],
  ] as const)('%s → свой экран, калькулятор скрыт', (access, title) => {
    applyFacts(parseFacts(SEPTEMBER))
    useXonim.setState({ access })
    app()
    expect(screen.queryByText('калькулятор')).toBeNull()
    expect(screen.getByText(getTranslator('ru')(title))).toBeTruthy()
  })
})

describe('карточка и баннер Xonim', () => {
  it.each(LOCALES)('%s: без сырых ключей и пустых подстановок, сверка сходится', (locale) => {
    reset(locale)
    applyFacts(parseFacts(SEPTEMBER))
    render(
      <>
        <XonimBanner />
        <XonimCard />
      </>,
    )
    const text = document.body.textContent ?? ''
    for (const key of DICT_KEYS) expect(text).not.toContain(key)
    expect(text).not.toMatch(/\{[a-zA-Z]+\}/)
    expect(text).not.toMatch(/NaN|Infinity|undefined/)
    expect(text).toContain(getTranslator(locale)('xonim.recon.ok'))
  })

  it('незаконченный месяц предупреждает, сколько в нём дней', () => {
    applyFacts(parseFacts({ ...EMPTY_MONTH, sales: { ...EMPTY_MONTH.sales, open_days: 5 } }))
    render(<XonimBanner />)
    expect(screen.getByText(getTranslator('ru')('xonim.partial', { count: 5 }))).toBeTruthy()
  })

  it('правка модели после загрузки показывается как расхождение', () => {
    applyFacts(parseFacts(SEPTEMBER))
    useAppStore.getState().addFixedExpense({ name: 'Охрана', amount: 1_000_000 })
    render(<XonimCard />)
    expect(screen.queryByText(getTranslator('ru')('xonim.recon.ok'))).toBeNull()
  })
})

describe('запуск режима Xonim', () => {
  it('берёт язык Xonim, бережёт ручные правки и сохраняет цель при обновлении', async () => {
    localStorage.setItem('xonim-lang', 'en')
    serve({ [ME]: () => reply({ role: 'owner' }), [FACTS]: () => reply(SEPTEMBER) })
    startXonim()
    await vi.waitFor(() => expect(useAppStore.getState().xonim).not.toBeNull())
    expect(useAppStore.getState().locale).toBe('en')

    // Язык, выбранный в калькуляторе, уходит обратно в Xonim.
    useAppStore.getState().setLocale('uz')
    expect(localStorage.getItem('xonim-lang')).toBe('uz')

    // Ручная правка помечается, и фоновая загрузка её не стирает.
    useAppStore.getState().updateBusiness({ name: 'Мой план', targetProfit: 25_000_000 })
    expect(useAppStore.getState().xonim?.edited).toBe(true)
    await loadMonth(undefined, { auto: true })
    expect(useAppStore.getState().model.business.name).toBe('Мой план')
    const pending = useXonim.getState().pending
    expect(pending?.month).toBe('2026-09')

    // Явное обновление заменяет модель, но цель по прибыли остаётся.
    applyFacts(pending!)
    const app = useAppStore.getState()
    expect(app.xonim?.edited).toBe(false)
    expect(app.model.business.name).toBe('Xonim')
    expect(app.model.business.targetProfit).toBe(25_000_000)
    expect(useXonim.getState().pending).toBeNull()
  })
})
