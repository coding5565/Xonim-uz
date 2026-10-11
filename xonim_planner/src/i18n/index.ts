/**
 * Ядро мультиязычности.
 *
 * Русский словарь — источник истины: его ключи задают тип `TKey`, поэтому
 * отсутствие или опечатка ключа в узбекском либо английском словаре — ошибка
 * компиляции, а не пустая строка в интерфейсе.
 *
 * Множественное число берётся из `Intl.PluralRules`, а не из самодельных
 * правил: в русском три формы (гость / гостя / гостей), в английском две,
 * в узбекском одна.
 */
import { LOCALE_TAGS, type Locale } from './locales'
import type { Phrase, TVars } from './types'
import { ru } from './ru'
import { uz } from './uz'
import { en } from './en'

export type { Phrase, TVars } from './types'

export type TKey = keyof typeof ru

/** Словарь языка обязан покрывать все ключи русского. */
export type Dict = Record<TKey, Phrase>

export interface Translator {
  (key: TKey, vars?: TVars): string
  locale: Locale
}

const DICTS: Record<Locale, Dict> = { ru, uz, en }

const pluralRules = new Map<Locale, Intl.PluralRules>()
const numberFormats = new Map<string, Intl.NumberFormat>()

function pluralRuleOf(locale: Locale): Intl.PluralRules {
  let r = pluralRules.get(locale)
  if (!r) {
    r = new Intl.PluralRules(LOCALE_TAGS[locale])
    pluralRules.set(locale, r)
  }
  return r
}

function formatCount(value: number, locale: Locale): string {
  const digits = Number.isInteger(value) ? 0 : 1
  const cacheKey = `${locale}:${digits}`
  let f = numberFormats.get(cacheKey)
  if (!f) {
    f = new Intl.NumberFormat(LOCALE_TAGS[locale], { maximumFractionDigits: digits })
    numberFormats.set(cacheKey, f)
  }
  return f.format(value)
}

/** Выбирает форму множественного числа; при отсутствии точной формы берёт `other`. */
function resolvePhrase(phrase: Phrase, vars: TVars | undefined, locale: Locale): string {
  if (typeof phrase === 'string') return phrase
  const count = vars?.count
  if (typeof count !== 'number') return phrase.other
  const rule = pluralRuleOf(locale).select(count)
  return phrase[rule] ?? phrase.other
}

/** Подставляет `{name}`; числа форматируются по правилам языка. */
function interpolate(template: string, vars: TVars | undefined, locale: Locale): string {
  if (!vars) return template
  return template.replace(/\{(\w+)\}/g, (match, name: string) => {
    if (!(name in vars)) return match
    const value = vars[name]
    return typeof value === 'number' ? formatCount(value, locale) : String(value)
  })
}

export function createTranslator(locale: Locale): Translator {
  const dict = DICTS[locale] ?? DICTS.ru
  const t = ((key: TKey, vars?: TVars): string => {
    const phrase = dict[key] ?? DICTS.ru[key]
    if (phrase === undefined) return key
    return interpolate(resolvePhrase(phrase, vars, locale), vars, locale)
  }) as Translator
  t.locale = locale
  return t
}

const translators = new Map<Locale, Translator>()

/** Переводчик вне React — нужен, например, при создании демо-данных. */
export function getTranslator(locale: Locale): Translator {
  let t = translators.get(locale)
  if (!t) {
    t = createTranslator(locale)
    translators.set(locale, t)
  }
  return t
}

export { DICTS }
