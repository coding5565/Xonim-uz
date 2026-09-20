import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { ru } from './ru'
import { en } from './en'

export type Lang = 'uz' | 'ru' | 'en'

export const LANGUAGES: { code: Lang; label: string; short: string }[] = [
  { code: 'uz', label: 'O‘zbekcha', short: 'UZ' },
  { code: 'ru', label: 'Русский', short: 'RU' },
  { code: 'en', label: 'English', short: 'EN' },
]

/** Kalit — o'zbekcha matnning o'zi, shuning uchun uz lug'ati bo'sh. */
const DICTIONARIES: Record<Lang, Record<string, string>> = { uz: {}, ru, en }

const STORAGE_KEY = 'xonim-lang'

/**
 * Joriy til. Bu yerda saqlanadi, localStorage'da emas.
 *
 * Nega: maxfiy rejimda yoki sayt ma'lumotlari yopiq bo'lganda yozish
 * ishlamaydi. Ilgari `currentLang()` to'g'ridan-to'g'ri localStorage'dan
 * o'qir edi, natijada ekran ruschaga o'tar, `Accept-Language` sarlavhasi
 * va tarmoq xatolari esa eski tilda qolib ketardi — bitta sahifada
 * ikkita til.
 */
let active: Lang = 'uz'

function stored(): Lang {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    if (value === 'ru' || value === 'en' || value === 'uz') return value
  } catch {
    // Maxfiy rejimda localStorage yopiq bo'lishi mumkin — o'zbekcha qoladi.
  }
  return 'uz'
}

active = stored()

/** {name} ko'rinishidagi o'rinlarni qiymat bilan almashtiradi. */
function fill(text: string, vars?: Record<string, string | number>) {
  if (!vars) return text
  return text.replace(/\{(\w+)\}/g, (whole, name) =>
    name in vars ? String(vars[name]) : whole)
}

interface Bundle {
  lang: Lang
  setLang: (next: Lang) => void
  /** Tarjima qiladi; topilmasa o'zbekcha matnning o'zini qaytaradi. */
  t: (text: string, vars?: Record<string, string | number>) => string
  /**
   * Sanoq shakllari uchun. Rus tilida uch xil shakl bor («1 чек»,
   * «2 чека», «5 чеков»), shuning uchun brauzerning Intl.PluralRules'i
   * ishlatiladi. Kalit «one|few|many» ko'rinishida yoziladi.
   */
  tn: (text: string, count: number, vars?: Record<string, string | number>) => string
  /** Sana va vaqtni tanlangan tilda ko'rsatadi. */
  locale: string
}

const FALLBACK: Bundle = {
  lang: 'uz',
  setLang: () => {},
  t: text => text,
  tn: text => text,
  locale: 'uz-UZ',
}

const LOCALES: Record<Lang, string> = { uz: 'uz-UZ', ru: 'ru-RU', en: 'en-GB' }

const Context = createContext<Bundle>(FALLBACK)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(stored)

  // <html lang> saqlangan tilga qaytarilishi kerak: ilgari u faqat tugma
  // bosilganda yangilanardi, ya'ni sahifa qayta yuklangach brauzer va
  // skrinrider ruscha sahifani o'zbekcha deb o'qirdi.
  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const setLang = useCallback((next: Lang) => {
    // Avval xotiradagi qiymat: `currentLang()` va `translate()` shundan
    // o'qiydi, shuning uchun saqlash ishlamasa ham til hamma joyda birga
    // o'zgaradi.
    active = next
    setLangState(next)
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      // Saqlab bo'lmasa ham joriy sessiyada til o'zgaradi.
    }
  }, [])

  const bundle = useMemo<Bundle>(() => {
    const dictionary = DICTIONARIES[lang]
    const plural = new Intl.PluralRules(LOCALES[lang])

    const t = (text: string, vars?: Record<string, string | number>) =>
      fill(dictionary[text] ?? text, vars)

    const tn = (text: string, count: number, vars?: Record<string, string | number>) => {
      const forms = (dictionary[text] ?? text).split('|')
      // one | few | many tartibida; kamroq shakl berilgan bo'lsa oxirgisi olinadi.
      const rule = plural.select(count)
      const index = rule === 'one' ? 0 : rule === 'few' ? 1 : forms.length - 1
      const picked = forms[Math.min(index, forms.length - 1)] ?? forms[0]
      return fill(picked, { count, ...vars })
    }

    return { lang, setLang, t, tn, locale: LOCALES[lang] }
  }, [lang, setLang])

  return <Context.Provider value={bundle}>{children}</Context.Provider>
}

export function useI18n() {
  return useContext(Context)
}

/** Til kodini API so'rovlariga qo'shish uchun — server xabarlari ham tarjima bo'ladi. */
export function currentLang(): Lang {
  return active
}

/** Sana va raqam formati uchun. React'dan tashqarida ham kerak (api.ts). */
export function currentLocale(): string {
  return LOCALES[active]
}

/**
 * React'dan tashqarida tarjima qilish uchun (masalan api.ts dagi tarmoq
 * xatolari). Hook ishlatib bo'lmaydigan joylarda shu chaqiriladi.
 */
export function translate(text: string, vars?: Record<string, string | number>) {
  return fill(DICTIONARIES[active][text] ?? text, vars)
}
