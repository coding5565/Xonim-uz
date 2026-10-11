import { useAppStore } from '@/store/useAppStore'
import { useT } from '@/store/useT'
import { monthLabel } from './month'
import { applyFacts, loadMonth, useXonim } from './sync'

/**
 * Строка под шапкой: ошибка связи с Xonim, свежие данные, отложенные из-за
 * ручных правок, или незаконченный месяц. Показывается одна, самая важная.
 */
export function XonimBanner() {
  const t = useT()
  const locale = useAppStore((s) => s.locale)
  const link = useAppStore((s) => s.xonim)
  const failed = useXonim((s) => s.failed)
  const pending = useXonim((s) => s.pending)

  if (failed) {
    return (
      <div className="border-t border-rose-200 bg-rose-50 px-4 py-1.5 text-xs text-rose-800 sm:px-6 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200">
        {t('xonim.syncError')}{' '}
        <button
          className="cursor-pointer font-semibold underline"
          onClick={() => void loadMonth(undefined, { auto: true })}
        >
          {t('xonim.retry')}
        </button>
      </div>
    )
  }

  if (pending) {
    const replace = () => {
      if (confirm(t('xonim.confirmReplace', { month: monthLabel(pending.month, locale) }))) {
        applyFacts(pending)
      }
    }
    return (
      <div className="border-t border-sky-200 bg-sky-50 px-4 py-1.5 text-xs text-sky-800 sm:px-6 dark:border-sky-900/50 dark:bg-sky-950/40 dark:text-sky-200">
        {t('xonim.pending')}{' '}
        <button className="cursor-pointer font-semibold underline" onClick={replace}>
          {t('xonim.refresh')}
        </button>
      </div>
    )
  }

  if (link && !link.complete) {
    return (
      <div className="border-t border-amber-200 bg-amber-50 px-4 py-1.5 text-xs text-amber-800 sm:px-6 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200">
        {t('xonim.partial', { count: link.openDays })}
      </div>
    )
  }

  return null
}
