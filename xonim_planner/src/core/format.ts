/**
 * Форматирование чисел, сумм и процентов.
 *
 * Разделители разрядов и дробной части зависят от языка интерфейса
 * (`125 000 000` в русском и узбекском, `125,000,000` в английском), поэтому
 * текущий язык хранится здесь и обновляется из store при переключении.
 */
import { DEFAULT_LOCALE, LOCALE_TAGS, type Locale } from '@/i18n/locales'
import { getTranslator } from '@/i18n'

let current: Locale = DEFAULT_LOCALE

/** Вызывается из store при смене языка — до того, как React перерисует дерево. */
export function setFormatLocale(locale: Locale): void {
  current = locale
}

export function formatLocale(): Locale {
  return current
}

const cache = new Map<string, Intl.NumberFormat>()

function nf(digits: number, locale: Locale = current): Intl.NumberFormat {
  const key = `${locale}:${digits}`
  let f = cache.get(key)
  if (!f) {
    f = new Intl.NumberFormat(LOCALE_TAGS[locale], { maximumFractionDigits: digits })
    cache.set(key, f)
  }
  return f
}

const isBad = (v: number | null | undefined): boolean =>
  v === null || v === undefined || !Number.isFinite(v)

/** `125 000 000 сум` — без лишних десятичных знаков. */
export function money(v: number | null | undefined, currency = ''): string {
  if (isBad(v)) return '—'
  const amount = nf(0).format(Math.round(v as number))
  return currency ? `${amount} ${currency}` : amount
}

/** Число без валюты. */
export function num(v: number | null | undefined, digits = 0): string {
  if (isBad(v)) return '—'
  return nf(digits).format(v as number)
}

/** Проценты — максимум 1–2 знака после запятой. */
export function pct(v: number | null | undefined, digits: 1 | 2 = 1): string {
  if (isBad(v)) return '—'
  return `${nf(digits).format(v as number)}%`
}

export function signedPct(v: number | null | undefined, digits: 1 | 2 = 1): string {
  if (isBad(v)) return '—'
  if (Math.abs(v as number) < 0.05) return pct(0, digits)
  return `${(v as number) > 0 ? '+' : '−'}${pct(Math.abs(v as number), digits)}`
}

/** Компактный формат для осей графиков: `125,0 млн`. */
export function moneyShort(v: number | null | undefined): string {
  if (isBad(v)) return '—'
  const t = getTranslator(current)
  const x = v as number
  const a = Math.abs(x)
  if (a >= 1e9) return `${nf(1).format(x / 1e9)} ${t('format.billion')}`
  if (a >= 1e6) return `${nf(1).format(x / 1e6)} ${t('format.million')}`
  if (a >= 1e3) return `${nf(0).format(x / 1e3)} ${t('format.thousand')}`
  return nf(0).format(x)
}

/* ───────────────────────── Ввод чисел пользователем ───────────────────────── */

interface Separators {
  group: string
  decimal: string
}

const separatorCache = new Map<Locale, Separators>()

/** Символы разделителей текущего языка — нужны, чтобы разобрать ввод обратно в число. */
export function separators(locale: Locale = current): Separators {
  let s = separatorCache.get(locale)
  if (!s) {
    const parts = new Intl.NumberFormat(LOCALE_TAGS[locale], {
      maximumFractionDigits: 1,
    }).formatToParts(12345.6)
    s = {
      group: parts.find((p) => p.type === 'group')?.value ?? ' ',
      decimal: parts.find((p) => p.type === 'decimal')?.value ?? '.',
    }
    separatorCache.set(locale, s)
  }
  return s
}

/**
 * Разбирает введённое число с учётом языка.
 *
 * Сначала убирается разделитель разрядов текущего языка, затем оставшаяся
 * запятая трактуется как дробная. Поэтому «12,5» — это 12,5 в русском и
 * узбекском, но 125 в английском, где запятая разделяет разряды: следовать
 * языку здесь обязательно, иначе «1,500» превратилось бы в полторы единицы.
 */
export function parseLocaleNumber(text: string, locale: Locale = current): number | null {
  const { group } = separators(locale)
  let cleaned = text
  // Пробелы всех видов и разделитель разрядов языка — это не часть числа.
  cleaned = cleaned.replace(/[\s   ]/g, '')
  if (group && group.trim()) cleaned = cleaned.split(group).join('')
  cleaned = cleaned.replace(',', '.')
  if (cleaned === '' || cleaned === '-' || cleaned === '.') return null
  const n = Number(cleaned)
  return Number.isFinite(n) ? n : null
}

/** Обратная операция: число в строку с разделителями разрядов текущего языка. */
export function formatLocaleNumber(v: number, digits = 4, locale: Locale = current): string {
  if (!Number.isFinite(v)) return ''
  return nf(digits, locale).format(v)
}

/** Число без группировки — показывается, пока поле в фокусе. */
export function plainNumber(v: number, locale: Locale = current): string {
  if (!Number.isFinite(v)) return ''
  const { decimal } = separators(locale)
  return String(v).replace('.', decimal)
}

/* ──────────────────────────── Безопасная арифметика ──────────────────────────── */

/** Безопасное деление: 0 в знаменателе даёт null, а не Infinity/NaN. */
export function safeDiv(a: number, b: number): number | null {
  if (!Number.isFinite(a) || !Number.isFinite(b) || b === 0) return null
  const r = a / b
  return Number.isFinite(r) ? r : null
}

/** Доля в процентах: safePct(15, 100) === 15 */
export function safePct(a: number, b: number): number | null {
  const r = safeDiv(a, b)
  return r === null ? null : r * 100
}
