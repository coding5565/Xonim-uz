import { LOCALE_TAGS, type Locale } from '@/i18n/locales'

/**
 * Узбекских названий месяцев нет в ICU части браузеров: Chrome показывает
 * «2026 M09». Поэтому для узбекского — свой список и формат, как в самом
 * Xonim («2026-yil sentabr»).
 */
const UZ_MONTHS = [
  'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
  'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr',
]

/** 'YYYY-MM' → «Сентябрь 2026 г.» / «2026-yil sentabr» / «September 2026». */
export function monthLabel(key: string, locale: Locale): string {
  const [year, month] = key.split('-').map(Number)
  if (!year || !month || month > 12) return key
  if (locale === 'uz') return `${year}-yil ${UZ_MONTHS[month - 1]}`
  const text = new Intl.DateTimeFormat(LOCALE_TAGS[locale], { month: 'long', year: 'numeric' })
    .format(new Date(year, month - 1, 1))
  return text.charAt(0).toUpperCase() + text.slice(1)
}
