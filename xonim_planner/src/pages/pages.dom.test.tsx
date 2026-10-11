// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import App from '@/App'
import { defaultModel, defaultScenarios, emptyModel } from '@/core/defaults'
import { setFormatLocale } from '@/core/format'
import { getTranslator } from '@/i18n'
import { ru } from '@/i18n/ru'
import { LOCALES, type Locale } from '@/i18n/locales'
import { useAppStore } from '@/store/useAppStore'

/** recharts измеряет контейнер — в jsdom этого API нет. */
beforeAll(() => {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
})

afterEach(cleanup)

const DICT_KEYS = Object.keys(ru)

const PAGES = [
  'dashboard',
  'pnl',
  'sales',
  'menu',
  'ingredients',
  'staff',
  'fixed',
  'variable',
  'breakeven',
  'target',
  'simulator',
  'scenarios',
  'settings',
]

function open(page: string, locale: Locale, empty = false) {
  window.location.hash = page
  setFormatLocale(locale)
  useAppStore.setState({
    locale,
    model: empty ? emptyModel(locale) : defaultModel(locale),
    scenarios: defaultScenarios(),
    activeScenarioId: 'sc_current',
    period: 'month',
  })
  render(<App />)
  return document.querySelector('main')?.textContent ?? ''
}

describe('страницы отрисовываются', () => {
  it.each(PAGES)('%s — с демо-данными', (page) => {
    expect(open(page, 'ru')).not.toBe('')
  })

  it.each(PAGES)('%s — на пустой модели без деления на ноль', (page) => {
    const text = open(page, 'ru', true)
    expect(text).not.toBe('')
    expect(text).not.toMatch(/NaN|Infinity|undefined/)
  })
})

describe('мультиязычность', () => {
  it.each(LOCALES)('%s: все страницы рендерятся без сырых ключей и подстановок', (locale) => {
    const problems: string[] = []
    for (const page of PAGES) {
      const text = open(page, locale)
      if (text === '') problems.push(`${page}: пустая страница`)
      // Непереведённый ключ утёк бы в интерфейс дословно, как «dash.revenue».
      for (const key of DICT_KEYS) {
        if (text.includes(key)) problems.push(`${page}: виден ключ ${key}`)
      }
      const leftover = text.match(/\{[a-zA-Z]+\}/)
      if (leftover) problems.push(`${page}: незаполненная подстановка ${leftover[0]}`)
      cleanup()
    }
    expect(problems).toEqual([])
  })

  it.each(LOCALES)('%s: навигация подписана на выбранном языке', (locale) => {
    const t = getTranslator(locale)
    open('dashboard', locale)
    expect(screen.getAllByText(t('nav.dashboard')).length).toBeGreaterThan(0)
    expect(screen.getAllByText(t('nav.breakeven')).length).toBeGreaterThan(0)
  })

  it('смена языка не трогает введённые пользователем названия', () => {
    open('menu', 'ru')
    const before = useAppStore.getState().model
    useAppStore.getState().setLocale('en')
    const after = useAppStore.getState().model
    expect(after).toEqual(before)
    expect(after.dishes[0].name).toBe(getTranslator('ru')('demo.dish.plov'))
  })

  it('демо-данные создаются на текущем языке', () => {
    useAppStore.getState().setLocale('uz')
    useAppStore.getState().loadDemo()
    const model = useAppStore.getState().model
    expect(model.dishes[0].name).toBe(getTranslator('uz')('demo.dish.plov'))
    expect(model.business.name).toBe(getTranslator('uz')('demo.business'))
  })

  it('обозначение валюты следует языку, пока не задано вручную', () => {
    open('dashboard', 'en')
    expect(document.querySelector('main')?.textContent).toContain('UZS')
    useAppStore.getState().updateBusiness({ currency: '$' })
    cleanup()
    render(<App />)
    expect(document.querySelector('main')?.textContent).toContain('$')
  })
})

describe('переключение периода и сценария', () => {
  it('меняет отображаемые суммы, не трогая модель', () => {
    open('dashboard', 'ru')
    const monthly = useAppStore.getState().model

    useAppStore.setState({ period: 'day' })
    useAppStore.getState().setActiveScenario('sc_optimistic')

    expect(useAppStore.getState().model).toEqual(monthly)
    expect(screen.getAllByText(new RegExp(getTranslator('ru')('scenario.optimistic'))).length)
      .toBeGreaterThan(0)
  })
})
