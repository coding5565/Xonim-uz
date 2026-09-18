import { currentLang } from './i18n'

let csrf = ''

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message)
  }
}

function message(data: unknown): string {
  if (typeof data === 'string') return data
  if (Array.isArray(data)) return data.map(message).join(' ')
  if (data && typeof data === 'object') {
    return Object.entries(data)
      .map(([key, value]) => {
        const prefix = key === 'detail' || key === 'non_field_errors' ? '' : `${key}: `
        return `${prefix}${message(value)}`
      })
      .join(' ')
  }
  return 'So‘rov bajarilmadi.'
}

export async function refreshCsrf() {
  const response = await fetch('/api/v1/auth/csrf/', { credentials: 'same-origin' })
  if (!response.ok) throw new Error('Serverga ulanib bo‘lmadi.')
  csrf = (await response.json()).csrfToken
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = options.method || 'GET'
  if (method !== 'GET' && !csrf) await refreshCsrf()

  let response: Response
  try {
    response = await fetch(`/api/v1/${path}`, {
      ...options,
      credentials: 'same-origin',
      headers: {
        ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
        // Server xabarlari ham tanlangan tilda kelishi uchun.
        'Accept-Language': currentLang(),
        ...(method !== 'GET' ? { 'X-CSRFToken': csrf } : {}),
        ...options.headers,
      },
    })
  } catch {
    throw new Error('Mahalliy server bilan aloqa yo‘q. Kiritilgan ma’lumotlarni saqlab turing.')
  }

  const body: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    throw new ApiError(body ? message(body) : 'Server javob bermadi. Qayta urinib ko‘ring.', response.status)
  }
  return body as T
}

/** Follows DRF pagination until every page is collected. */
export async function list<T>(path: string): Promise<T[]> {
  const first = await api<{ results: T[]; next: string | null }>(path)
  const result = [...first.results]
  let next = first.next
  while (next) {
    const url = new URL(next, window.location.origin)
    const page = await api<{ results: T[]; next: string | null }>(url.pathname.replace('/api/v1/', '') + url.search)
    result.push(...page.results)
    next = page.next
  }
  return result
}

export async function download(path: string, filename: string) {
  let response: Response
  try {
    response = await fetch(`/api/v1/${path}`, { credentials: 'same-origin' })
  } catch {
    throw new Error('Hisobot faylini yuklab bo‘lmadi. Server bilan aloqani tekshiring.')
  }
  if (!response.ok) {
    const body: unknown = await response.json().catch(() => null)
    throw new ApiError(body ? message(body) : 'Excel fayli tayyorlanmadi.', response.status)
  }
  const url = URL.createObjectURL(await response.blob())
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export const money = (value: string | number) =>
  new Intl.NumberFormat('uz-UZ', { maximumFractionDigits: 2 }).format(Number(value))

export const dateLabel = (value: string) =>
  new Intl.DateTimeFormat('uz-UZ', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Tashkent',
  }).format(new Date(value))

export const today = () =>
  new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Tashkent',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
