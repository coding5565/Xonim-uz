import { describe, expect, it } from 'vitest'
import { DICTS, getTranslator, type Dict, type TKey } from './index'
import { LOCALES, type Locale } from './locales'
import { ru } from './ru'
import type { Phrase } from './types'
import {
  formatLocaleNumber,
  money,
  num,
  parseLocaleNumber,
  pct,
  setFormatLocale,
} from '@/core/format'

const keys = Object.keys(ru) as TKey[]

/** Все варианты фразы: строка либо все формы множественного числа. */
function variants(phrase: Phrase): string[] {
  return typeof phrase === 'string' ? [phrase] : Object.values(phrase).filter(Boolean)
}

/** Плейсхолдеры `{name}`, использованные во фразе. */
function placeholders(phrase: Phrase): Set<string> {
  const found = new Set<string>()
  for (const v of variants(phrase)) {
    for (const m of v.matchAll(/\{(\w+)\}/g)) found.add(m[1])
  }
  return found
}

describe('полнота словарей', () => {
  it.each(LOCALES)('%s содержит ровно те же ключи, что и русский', (locale) => {
    const dict = DICTS[locale] as Dict
    expect(Object.keys(dict).sort()).toEqual(keys.slice().sort())
  })

  it.each(LOCALES)('%s не содержит пустых переводов', (locale) => {
    const dict = DICTS[locale] as Dict
    const empty = keys.filter((k) => variants(dict[k]).some((v) => v.trim() === ''))
    expect(empty).toEqual([])
  })

  /**
   * Самая частая ошибка перевода — потерянная подстановка: текст выглядит
   * нормально, но в интерфейс попадает фраза без числа или названия.
   */
  it.each(LOCALES)('%s сохраняет все подстановки исходной фразы', (locale) => {
    const dict = DICTS[locale] as Dict
    const broken: string[] = []
    for (const k of keys) {
      const expected = placeholders(ru[k])
      const actual = placeholders(dict[k])
      for (const p of expected) if (!actual.has(p)) broken.push(`${k}: нет {${p}}`)
      for (const p of actual) if (!expected.has(p)) broken.push(`${k}: лишний {${p}}`)
    }
    expect(broken).toEqual([])
  })

  it.each(LOCALES)('%s объявляет форму other у всех множественных фраз', (locale) => {
    const dict = DICTS[locale] as Dict
    const plurals = keys.filter((k) => typeof ru[k] !== 'string')
    for (const k of plurals) {
      const phrase = dict[k]
      expect(typeof phrase, `${k} должен быть набором форм`).not.toBe('string')
      if (typeof phrase !== 'string') expect(phrase.other).toBeTruthy()
    }
  })
})

describe('множественное число', () => {
  it('русский выбирает три формы по правилам CLDR', () => {
    const t = getTranslator('ru')
    expect(t('be.guestsPerDayShort', { count: 1 })).toBe('1 гость в день')
    expect(t('be.guestsPerDayShort', { count: 2 })).toBe('2 гостя в день')
    expect(t('be.guestsPerDayShort', { count: 5 })).toBe('5 гостей в день')
    expect(t('be.guestsPerDayShort', { count: 21 })).toBe('21 гость в день')
    expect(t('be.guestsPerDayShort', { count: 126 })).toBe('126 гостей в день')
  })

  it('английский выбирает две формы', () => {
    const t = getTranslator('en')
    expect(t('sales.formulaDays', { count: 1 })).toBe('1 day')
    expect(t('sales.formulaDays', { count: 30 })).toBe('30 days')
  })

  it('узбекский обходится одной формой', () => {
    const t = getTranslator('uz')
    expect(t('sales.formulaDays', { count: 1 })).toBe('1 kun')
    expect(t('sales.formulaDays', { count: 30 })).toBe('30 kun')
  })

  it('числа в подстановке форматируются по правилам языка', () => {
    expect(getTranslator('ru')('be.tooltipGuests', { count: 3760 })).toBe(
      '3 760 гостей / мес',
    )
    expect(getTranslator('en')('be.tooltipGuests', { count: 3760 })).toBe('3,760 guests / month')
  })
})

describe('подстановки', () => {
  it('подставляет строковые значения', () => {
    expect(getTranslator('ru')('app.scenarioActive', { name: 'Тест' })).toContain('«Тест»')
    expect(getTranslator('en')('app.scenarioActive', { name: 'Test' })).toContain('“Test”')
  })

  it('оставляет неизвестный плейсхолдер нетронутым, а не подставляет undefined', () => {
    expect(getTranslator('ru')('app.scenarioActive', {})).toContain('{name}')
  })
})

describe('форматирование по языку', () => {
  const withLocale = <T,>(locale: Locale, fn: () => T): T => {
    setFormatLocale(locale)
    try {
      return fn()
    } finally {
      setFormatLocale('ru')
    }
  }

  it('русский и узбекский разделяют разряды пробелом, английский — запятой', () => {
    expect(withLocale('ru', () => num(125_000_000))).toBe('125 000 000')
    expect(withLocale('uz', () => num(125_000_000))).toBe('125 000 000')
    expect(withLocale('en', () => num(125_000_000))).toBe('125,000,000')
  })

  it('дробная часть процентов следует языку', () => {
    expect(withLocale('ru', () => pct(63.08, 2))).toBe('63,08%')
    expect(withLocale('en', () => pct(63.08, 2))).toBe('63.08%')
  })

  it('обозначение валюты берётся из языка, пока не задано вручную', () => {
    expect(withLocale('ru', () => money(1000, getTranslator('ru')('currency.default')))).toBe(
      '1 000 сум',
    )
    expect(withLocale('uz', () => money(1000, getTranslator('uz')('currency.default')))).toBe(
      '1 000 soʻm',
    )
    expect(withLocale('en', () => money(1000, getTranslator('en')('currency.default')))).toBe(
      '1,000 UZS',
    )
  })

  it('ввод числа разбирается обратно в каждом языке', () => {
    for (const locale of LOCALES) {
      withLocale(locale, () => {
        const text = formatLocaleNumber(1_234_567.5, 1)
        expect(parseLocaleNumber(text)).toBeCloseTo(1_234_567.5, 6)
      })
    }
  })

  it('в русском и узбекском точка и запятая одинаково означают дробную часть', () => {
    for (const locale of ['ru', 'uz'] as Locale[]) {
      withLocale(locale, () => {
        expect(parseLocaleNumber('12,5')).toBe(12.5)
        expect(parseLocaleNumber('12.5')).toBe(12.5)
      })
    }
  })

  /**
   * В английской локали запятая — разделитель разрядов, и «12,5» там значит 125.
   * Разбор обязан следовать языку, иначе «1,500» превратится в полторы единицы.
   */
  it('в английском запятая читается как разделитель разрядов', () => {
    withLocale('en', () => {
      expect(parseLocaleNumber('12.5')).toBe(12.5)
      expect(parseLocaleNumber('12,5')).toBe(125)
      expect(parseLocaleNumber('125,000,000')).toBe(125_000_000)
    })
  })

  it('компактный формат подписывает порядок на языке интерфейса', () => {
    expect(withLocale('ru', () => getTranslator('ru')('format.million'))).toBe('млн')
    expect(withLocale('uz', () => getTranslator('uz')('format.million'))).toBe('mln')
    expect(withLocale('en', () => getTranslator('en')('format.million'))).toBe('M')
  })
})
