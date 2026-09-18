import { useSyncExternalStore } from 'react'
import { ApiError, api } from './api'
import type { User } from './types'

export interface SessionState {
  user: User | null
  ready: boolean
}

export type Role = User['role']

/** Where a role lands when it opens a page it is not allowed to see. */
export function homeFor(role: Role) {
  if (role === 'owner') return '/'
  if (role === 'kitchen') return '/kitchen'
  return '/pos'
}

let state: SessionState = { user: null, ready: false }
const listeners = new Set<() => void>()

function emit() {
  for (const listener of listeners) listener()
}

export const session = {
  get current() {
    return state
  },
  set(patch: Partial<SessionState>) {
    state = { ...state, ...patch }
    emit()
  },
  subscribe(listener: () => void) {
    listeners.add(listener)
    return () => listeners.delete(listener)
  },
}

/** Subscribes a component to the session held outside React. */
export function useSession(): SessionState {
  return useSyncExternalStore(session.subscribe, () => state)
}

/** Loads the signed-in user once. A 403 means nobody is signed in, which is not an error. */
export async function ensureSession() {
  if (state.ready) return
  try {
    session.set({ user: await api<User>('auth/me/') })
  } catch (exception) {
    if (!(exception instanceof ApiError) || exception.status !== 403) throw exception
  }
  session.set({ ready: true })
}
