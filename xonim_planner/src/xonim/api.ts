/**
 * Обращения к API Xonim.
 *
 * Калькулятор и Xonim — один сайт, поэтому сессионная cookie Xonim уходит
 * с каждым запросом сама: отдельного входа нет. Запросы только на чтение —
 * CSRF-токен не нужен.
 */
import { XONIM_API } from './config'
import { parseFacts, type XonimFacts } from './facts'

/** Сессии нет или она не даёт прав — нужен вход в Xonim. */
export class XonimAuthError extends Error {
  constructor() {
    super('xonim: нет доступа')
    this.name = 'XonimAuthError'
  }
}

/** Сервер ответил ошибкой или не ответил вовсе. */
export class XonimHttpError extends Error {
  status: number
  constructor(status: number) {
    super(`xonim: HTTP ${status}`)
    this.name = 'XonimHttpError'
    this.status = status
  }
}

async function get(path: string): Promise<unknown> {
  const res = await fetch(`${XONIM_API}/${path}`, {
    credentials: 'same-origin',
    headers: { Accept: 'application/json' },
  })
  // Django REST при сессионной авторизации отвечает 403 и без входа.
  if (res.status === 401 || res.status === 403) throw new XonimAuthError()
  if (!res.ok) throw new XonimHttpError(res.status)
  return res.json()
}

export type XonimRole = 'owner' | 'cashier' | 'kitchen' | string

/** Кто вошёл в Xonim. Без входа — XonimAuthError. */
export async function fetchRole(): Promise<XonimRole> {
  const me = await get('auth/me/')
  const role = typeof me === 'object' && me !== null ? (me as { role?: unknown }).role : null
  return typeof role === 'string' ? role : ''
}

/** Факты месяца; без `month` сервер берёт последний полный месяц. */
export async function fetchFacts(month?: string): Promise<XonimFacts> {
  const query = month ? `?month=${encodeURIComponent(month)}` : ''
  return parseFacts(await get(`finance/planner/${query}`))
}
