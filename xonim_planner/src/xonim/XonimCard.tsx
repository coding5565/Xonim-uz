import { useState } from 'react'
import { CircleCheck, RefreshCw } from 'lucide-react'
import { Card, Field, SectionTitle, Select } from '@/components/ui'
import { StatRow } from '@/components/Kpi'
import { money } from '@/core/format'
import { useAppStore } from '@/store/useAppStore'
import { useBaseCalc } from '@/store/useCalc'
import { useCurrency, useT } from '@/store/useT'
import { monthLabel } from './month'
import { loadMonth, useXonim } from './sync'
import { reconciles } from './toModel'

/** Настройки → «Данные из Xonim»: выбор месяца, обновление и сверка с Xonim. */
export function XonimCard() {
  const t = useT()
  const locale = useAppStore((s) => s.locale)
  const link = useAppStore((s) => s.xonim)
  const months = useXonim((s) => s.months)
  const loading = useXonim((s) => s.loading)
  const failed = useXonim((s) => s.failed)
  const pending = useXonim((s) => s.pending)
  const currency = useCurrency()
  // Сверка — с исходной моделью: сценарий меняет цифры намеренно.
  const base = useBaseCalc()
  const [chosen, setChosen] = useState<string | null>(null)

  const month = chosen ?? link?.month ?? months[0] ?? ''
  const known = months.length > 0 ? months : link ? [link.month] : []
  const options = known.map((m) => ({ value: m, label: monthLabel(m, locale) }))

  const refresh = () => {
    if (
      link?.edited &&
      !confirm(t('xonim.confirmReplace', { month: monthLabel(month || link.month, locale) }))
    ) {
      return
    }
    void loadMonth(month || undefined)
  }

  const r = link?.recon
  const actual = base.totals.operatingProfit

  return (
    <Card>
      <SectionTitle
        icon={<RefreshCw size={18} />}
        title={t('xonim.cardTitle')}
        subtitle={t('xonim.cardSubtitle')}
      />
      <div className="flex flex-wrap items-end gap-3">
        <Field label={t('xonim.month')} className="w-56">
          <Select value={month} onChange={setChosen} options={options} disabled={loading} />
        </Field>
        <button className="btn btn-primary" onClick={refresh} disabled={loading}>
          <RefreshCw size={16} className={loading ? 'animate-spin' : undefined} />
          {loading ? t('xonim.loading') : t('xonim.refresh')}
        </button>
      </div>

      <div className="mt-3 space-y-1 text-sm text-slate-600 dark:text-slate-300">
        {link && <p>{t('xonim.loaded', { month: monthLabel(link.month, locale) })}</p>}
        {link && !link.complete && (
          <p className="text-amber-700 dark:text-amber-300">
            {t('xonim.partial', { count: link.openDays })}
          </p>
        )}
        {link?.edited && <p>{t('xonim.edited')}</p>}
        {pending && <p className="text-sky-700 dark:text-sky-300">{t('xonim.pending')}</p>}
        {failed && <p className="text-rose-700 dark:text-rose-300">{t('xonim.syncError')}</p>}
      </div>

      {r && (
        <div className="mt-4">
          <div className="mb-1 text-sm font-semibold text-slate-900 dark:text-slate-50">
            {t('xonim.recon.title')}
          </div>
          <StatRow label={t('xonim.recon.xonimProfit')} value={money(r.xonimProfit, currency)} />
          <StatRow
            label={t('xonim.recon.salaryPaid')}
            value={money(r.salaryPaid, currency)}
            indent
          />
          <StatRow
            label={t('xonim.recon.salaryAccrued')}
            value={money(r.salaryAccrued, currency)}
            indent
          />
          <StatRow
            label={t('xonim.recon.partners')}
            value={money(r.partnerProfit, currency)}
            indent
          />
          <StatRow label={t('xonim.recon.expected')} value={money(r.expected, currency)} strong />
          {reconciles(actual, r) ? (
            <p className="mt-2 flex items-center gap-1.5 text-xs text-emerald-700 dark:text-emerald-300">
              <CircleCheck size={14} /> {t('xonim.recon.ok')}
            </p>
          ) : (
            <p className="mt-2 text-xs text-amber-700 dark:text-amber-300">
              {t('xonim.recon.diff', { value: money(actual, currency) })}
            </p>
          )}
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">{t('xonim.recon.hint')}</p>
        </div>
      )}
    </Card>
  )
}
