export type Locale = 'ru' | 'uz' | 'en'

export const LOCALES: Locale[] = ['ru', 'uz', 'en']

/** BCP 47 теги для Intl: форматирование чисел и правила множественного числа. */
export const LOCALE_TAGS: Record<Locale, string> = {
  ru: 'ru-RU',
  uz: 'uz-Latn-UZ',
  en: 'en-US',
}

/** Название языка на нём самом — так принято в переключателях языка. */
export const LOCALE_NAMES: Record<Locale, string> = {
  ru: 'Русский',
  uz: 'Oʻzbekcha',
  en: 'English',
}

export const LOCALE_SHORT: Record<Locale, string> = {
  ru: 'RU',
  uz: 'UZ',
  en: 'EN',
}

/** Язык по умолчанию — источник истины для словарей. */
export const DEFAULT_LOCALE: Locale = 'ru'

export function isLocale(v: unknown): v is Locale {
  return typeof v === 'string' && (LOCALES as string[]).includes(v)
}

/** Подбирает язык интерфейса по настройкам браузера. */
export function detectLocale(): Locale {
  if (typeof navigator === 'undefined') return DEFAULT_LOCALE
  for (const lang of navigator.languages ?? [navigator.language]) {
    const base = lang?.toLowerCase().split('-')[0]
    if (isLocale(base)) return base
  }
  return DEFAULT_LOCALE
}
