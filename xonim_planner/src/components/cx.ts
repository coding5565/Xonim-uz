/** Склейка классов: отбрасывает false/null/undefined. */
export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(' ')
}
