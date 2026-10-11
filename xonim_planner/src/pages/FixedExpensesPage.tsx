import { useMemo } from 'react'
import { Building2, Plus } from 'lucide-react'
import {
  Card,
  DeleteButton,
  EmptyState,
  SectionTitle,
  Select,
  Switch,
  Table,
  TextInput,
  Thead,
  Tr,
  NumberInput,
} from '@/components/ui'
import { Kpi, StatRow } from '@/components/Kpi'
import { money, pct, safePct } from '@/core/format'
import { PERIODS, convertPeriod } from '@/core/period'
import type { Period } from '@/core/types'
import type { TKey } from '@/i18n'
import { PERIOD_ACC_KEY, PERIOD_LABEL_KEY, PERIOD_LOWER_KEY } from '@/i18n/keys'
import { useAppStore } from '@/store/useAppStore'
import { usePeriodView } from '@/store/useCalc'
import { useT } from '@/store/useT'

/** Подсказки для поля категории — обычные значения, а не закрытый список. */
const SUGGESTED_KEYS: TKey[] = [
  'demo.fxcat.rent',
  'demo.fxcat.utilities',
  'demo.fxcat.communication',
  'demo.fxcat.security',
  'demo.fxcat.admin',
  'demo.fxcat.software',
  'demo.fxcat.marketing',
  'demo.fxcat.other',
]

export default function FixedExpensesPage() {
  const t = useT()
  const items = useAppStore((s) => s.model.fixedExpenses)
  const add = useAppStore((s) => s.addFixedExpense)
  const update = useAppStore((s) => s.updateFixedExpense)
  const remove = useAppStore((s) => s.removeFixedExpense)
  const { calc, totals, period, ratio, currency } = usePeriodView()

  const periodOptions = PERIODS.map((p) => ({ value: p, label: t(PERIOD_LABEL_KEY[p]) }))
  const periodAcc = t(PERIOD_ACC_KEY[period])
  const periodLower = t(PERIOD_LOWER_KEY[period])

  const byCategory = useMemo(() => {
    const map = new Map<string, number>()
    for (const i of calc.fixedItems) {
      const key = i.group || t('common.uncategorized')
      map.set(key, (map.get(key) ?? 0) + i.monthly)
    }
    return [...map.entries()].sort((a, b) => b[1] - a[1])
  }, [calc.fixedItems, t])

  const categories = useMemo(
    () => [
      ...new Set([...SUGGESTED_KEYS.map((k) => t(k)), ...items.map((i) => i.category).filter(Boolean)]),
    ],
    [items, t],
  )

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-3">
        <Kpi
          label={t('fixed.kpi', { period: periodLower })}
          value={money(totals.fixedExpenses, currency)}
          tone="brand"
        />
        <Kpi label={t('fixed.shareOfRevenue')} value={pct(calc.ratios.fixedPct)} />
        <Kpi
          label={t('fixed.withFixedPayroll')}
          value={money(calc.breakEven.fixedCosts * ratio, currency)}
          sub={t('fixed.withFixedPayrollSub')}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <Card>
          <SectionTitle
            icon={<Building2 size={18} />}
            title={t('fixed.title')}
            subtitle={t('fixed.subtitle')}
            right={
              <button className="btn btn-primary" onClick={() => add()}>
                <Plus size={16} /> {t('fixed.addExpense')}
              </button>
            }
          />

          {items.length === 0 ? (
            <EmptyState
              title={t('fixed.emptyTitle')}
              description={t('fixed.emptyDesc')}
              action={
                <button className="btn btn-primary" onClick={() => add()}>
                  <Plus size={16} /> {t('fixed.emptyAction')}
                </button>
              }
            />
          ) : (
            <Table className="min-w-[900px]">
              <Thead>
                <tr>
                  <th className="th w-[24%]">{t('common.name')}</th>
                  <th className="th">{t('common.category')}</th>
                  <th className="th text-right">{t('common.amount')}</th>
                  <th className="th">{t('common.frequency')}</th>
                  <th className="th text-right">{t('common.forPeriod', { period: periodAcc })}</th>
                  <th className="th text-right">{t('common.shareOfRevenue')}</th>
                  <th className="th text-center">{t('common.active')}</th>
                  <th className="th w-10" />
                </tr>
              </Thead>
              <tbody>
                {items.map((x) => {
                  const monthly = convertPeriod(x.amount, x.period, 'month', calc.factors)
                  return (
                    <Tr key={x.id} muted={!x.active}>
                      <td className="td">
                        <TextInput
                          value={x.name}
                          placeholder={t('fixed.namePlaceholder')}
                          onChange={(v) => update(x.id, { name: v })}
                        />
                      </td>
                      <td className="td">
                        <input
                          className="input"
                          list="fixed-categories"
                          value={x.category}
                          onChange={(e) => update(x.id, { category: e.target.value })}
                        />
                      </td>
                      <td className="td">
                        <NumberInput
                          className="w-36"
                          value={x.amount}
                          min={0}
                          onChange={(v) => update(x.id, { amount: v })}
                        />
                      </td>
                      <td className="td">
                        <Select<Period>
                          className="w-28"
                          value={x.period}
                          options={periodOptions}
                          onChange={(v) => update(x.id, { period: v })}
                        />
                      </td>
                      <td className="td tnum text-right font-medium whitespace-nowrap">
                        {money(convertPeriod(monthly, 'month', period, calc.factors), currency)}
                      </td>
                      <td className="td tnum text-right text-slate-500">
                        {x.active ? pct(safePct(monthly, calc.totals.revenue)) : '—'}
                      </td>
                      <td className="td text-center">
                        <Switch checked={x.active} onChange={(v) => update(x.id, { active: v })} />
                      </td>
                      <td className="td text-right">
                        <DeleteButton title={t('common.delete')} onClick={() => remove(x.id)} />
                      </td>
                    </Tr>
                  )
                })}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-200 dark:border-slate-700">
                  <td className="td font-semibold" colSpan={4}>
                    {t('common.totalFor', { period: periodAcc })}
                  </td>
                  <td className="td tnum text-right font-semibold whitespace-nowrap">
                    {money(totals.fixedExpenses, currency)}
                  </td>
                  <td className="td tnum text-right font-semibold">{pct(calc.ratios.fixedPct)}</td>
                  <td colSpan={2} />
                </tr>
              </tfoot>
            </Table>
          )}
          <datalist id="fixed-categories">
            {categories.map((c) => (
              <option key={c} value={c} />
            ))}
          </datalist>
        </Card>

        <div className="space-y-5">
          <Card>
            <SectionTitle
              title={t('fixed.structureTitle')}
              subtitle={t('fixed.structureSubtitle', { period: periodAcc })}
            />
            {byCategory.length === 0 ? (
              <p className="text-sm text-slate-500">{t('fixed.noActive')}</p>
            ) : (
              byCategory.map(([name, monthly]) => (
                <div key={name} className="py-2">
                  <div className="mb-1 flex items-baseline justify-between gap-3 text-sm">
                    <span className="text-slate-600 dark:text-slate-300">{name}</span>
                    <span className="tnum font-medium whitespace-nowrap">
                      {money(convertPeriod(monthly, 'month', period, calc.factors), currency)}
                    </span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                    <div
                      className="h-full rounded-full bg-brand-500"
                      style={{
                        width: `${Math.min(100, (monthly / (calc.totals.fixedExpenses || 1)) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              ))
            )}
          </Card>

          <Card>
            <SectionTitle title={t('fixed.dailyTitle')} />
            <StatRow
              label={t('fixed.dailyFixed')}
              value={money(
                convertPeriod(calc.totals.fixedExpenses, 'month', 'day', calc.factors),
                currency,
              )}
            />
            <StatRow
              label={t('fixed.withFixedPayroll')}
              value={money(
                convertPeriod(calc.breakEven.fixedCosts, 'month', 'day', calc.factors),
                currency,
              )}
              strong
            />
            <div className="mt-3 text-xs text-slate-500 dark:text-slate-400">
              {t('fixed.dailyNote')}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
