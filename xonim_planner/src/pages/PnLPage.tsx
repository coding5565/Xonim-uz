import { useMemo } from 'react'
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ReceiptText } from 'lucide-react'
import { Card, SectionTitle } from '@/components/ui'
import { cx } from '@/components/cx'
import { Delta } from '@/components/Kpi'
import { CHART_COLORS, useChartTheme } from '@/components/chartTheme'
import { money, moneyShort, pct, safePct } from '@/core/format'
import { PERIOD_ACC_KEY } from '@/i18n/keys'
import { usePeriodView } from '@/store/useCalc'
import { useT } from '@/store/useT'

export default function PnLPage() {
  const t = useT()
  const { calc, totals, baseTotals, period, currency, simulated } = usePeriodView()
  const tt = totals
  const ct = useChartTheme()
  const periodAcc = t(PERIOD_ACC_KEY[period])

  const lines: Array<{
    label: string
    value: number
    base: number
    kind: 'revenue' | 'minus' | 'subtotal' | 'result'
    hint?: string
  }> = [
    { label: t('pnl.revenue'), value: tt.revenue, base: baseTotals.revenue, kind: 'revenue' },
    { label: t('pnl.cogs'), value: -tt.cogs, base: -baseTotals.cogs, kind: 'minus' },
    {
      label: t('pnl.grossProfit'),
      value: tt.grossProfit,
      base: baseTotals.grossProfit,
      kind: 'subtotal',
    },
    { label: t('pnl.payroll'), value: -tt.payroll, base: -baseTotals.payroll, kind: 'minus' },
    {
      label: t('pnl.variable'),
      value: -tt.variableExpenses,
      base: -baseTotals.variableExpenses,
      kind: 'minus',
    },
    {
      label: t('pnl.contribution'),
      value: tt.contribution,
      base: baseTotals.contribution,
      kind: 'subtotal',
      hint: t('pnl.contributionHint'),
    },
    {
      label: t('pnl.fixed'),
      value: -tt.fixedExpenses,
      base: -baseTotals.fixedExpenses,
      kind: 'minus',
    },
    {
      label: t('pnl.operatingProfit'),
      value: tt.operatingProfit,
      base: baseTotals.operatingProfit,
      kind: 'result',
    },
  ]

  const waterfall = useMemo(() => {
    const steps = [
      { name: t('pnl.wf.revenue'), delta: tt.revenue, color: CHART_COLORS.revenue },
      { name: t('pnl.wf.cogs'), delta: -tt.cogs, color: CHART_COLORS.cogs },
      { name: t('pnl.wf.payroll'), delta: -tt.payroll, color: CHART_COLORS.payroll },
      { name: t('pnl.wf.variable'), delta: -tt.variableExpenses, color: CHART_COLORS.variable },
      { name: t('pnl.wf.fixed'), delta: -tt.fixedExpenses, color: CHART_COLORS.fixed },
    ]
    let running = 0
    const data = steps.map((s) => {
      const from = running
      running += s.delta
      return {
        name: s.name,
        base: Math.min(from, running),
        span: Math.abs(s.delta),
        color: s.color,
        amount: s.delta,
      }
    })
    data.push({
      name: t('pnl.wf.profit'),
      base: Math.min(0, running),
      span: Math.abs(running),
      color: running >= 0 ? CHART_COLORS.profit : CHART_COLORS.loss,
      amount: running,
    })
    return data
  }, [tt, t])

  return (
    <div className="space-y-5">
      <Card>
        <SectionTitle
          icon={<ReceiptText size={18} />}
          title={t('pnl.title', { period: periodAcc })}
          subtitle={t('pnl.subtitle')}
        />

        <div className="overflow-hidden rounded-xl border border-slate-200 dark:border-slate-800">
          {lines.map((l) => {
            const share = safePct(Math.abs(l.value), Math.abs(tt.revenue))
            const deltaPct =
              simulated && l.base !== 0 ? ((l.value - l.base) / Math.abs(l.base)) * 100 : null
            return (
              <div
                key={l.label}
                className={cx(
                  'flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-slate-100 px-4 py-3 last:border-0 dark:border-slate-800/70',
                  l.kind === 'subtotal' && 'bg-slate-50 dark:bg-slate-800/40',
                  l.kind === 'result' &&
                    (l.value >= 0
                      ? 'bg-emerald-50 dark:bg-emerald-950/30'
                      : 'bg-rose-50 dark:bg-rose-950/30'),
                )}
              >
                <span
                  className={cx(
                    'mr-auto text-sm',
                    l.kind === 'minus' && 'pl-4 text-slate-600 dark:text-slate-300',
                    (l.kind === 'subtotal' || l.kind === 'revenue') &&
                      'font-semibold text-slate-900 dark:text-slate-50',
                    l.kind === 'result' && 'text-base font-bold text-slate-900 dark:text-slate-50',
                  )}
                  title={l.hint}
                >
                  {l.kind === 'minus' && <span className="mr-1 text-slate-400">−</span>}
                  {l.label}
                </span>
                {deltaPct !== null && (
                  <Delta value={deltaPct} goodWhen={l.kind === 'minus' ? 'down' : 'up'} />
                )}
                <span className="tnum w-20 text-right text-xs text-slate-500 dark:text-slate-400">
                  {pct(share)}
                </span>
                <span
                  className={cx(
                    'tnum w-44 text-right whitespace-nowrap',
                    l.kind === 'result'
                      ? cx(
                          'text-lg font-bold',
                          l.value >= 0
                            ? 'text-emerald-600 dark:text-emerald-400'
                            : 'text-rose-600 dark:text-rose-400',
                        )
                      : l.kind === 'subtotal' || l.kind === 'revenue'
                        ? 'font-semibold'
                        : 'text-slate-600 dark:text-slate-300',
                  )}
                >
                  {money(l.kind === 'minus' ? Math.abs(l.value) : l.value, currency)}
                </span>
              </div>
            )
          })}
        </div>

        <p className="mt-3 text-xs text-slate-500 dark:text-slate-400">{t('pnl.note')}</p>
      </Card>

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <SectionTitle
            title={t('pnl.waterfallTitle')}
            subtitle={t('pnl.waterfallSubtitle', { period: periodAcc })}
          />
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={waterfall} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                <XAxis
                  dataKey="name"
                  tick={{ fill: ct.axis, fontSize: 11 }}
                  axisLine={{ stroke: ct.grid }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: ct.axis, fontSize: 11 }}
                  tickFormatter={(v: number) => moneyShort(v)}
                  axisLine={false}
                  tickLine={false}
                  width={70}
                />
                <Tooltip
                  contentStyle={ct.tooltip}
                  cursor={{ fill: ct.dark ? '#ffffff10' : '#0f172a08' }}
                  formatter={(_v: unknown, _n: unknown, item?: { payload?: { amount: number } }) =>
                    [money(item?.payload?.amount, currency), t('common.change')] as [string, string]
                  }
                />
                <Bar dataKey="base" stackId="a" fill="transparent" />
                <Bar dataKey="span" stackId="a" radius={[4, 4, 0, 0]}>
                  {waterfall.map((d) => (
                    <Cell key={d.name} fill={d.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <SectionTitle
            title={t('pnl.structureTitle')}
            subtitle={t('pnl.structureSubtitle', { currency })}
          />
          <StructureBar
            items={[
              { label: t('pnl.st.cogs'), value: tt.cogs, color: CHART_COLORS.cogs },
              { label: t('pnl.st.payroll'), value: tt.payroll, color: CHART_COLORS.payroll },
              {
                label: t('pnl.st.variable'),
                value: tt.variableExpenses,
                color: CHART_COLORS.variable,
              },
              { label: t('pnl.st.fixed'), value: tt.fixedExpenses, color: CHART_COLORS.fixed },
              {
                label: t('pnl.st.profit'),
                value: Math.max(0, tt.operatingProfit),
                color: CHART_COLORS.profit,
              },
            ]}
            total={tt.revenue}
            currency={currency}
          />
          <div className="mt-4 space-y-1 text-xs text-slate-500 dark:text-slate-400">
            <div>
              {t('pnl.primeLine', {
                value: money(tt.primeCost, currency),
                share: pct(calc.ratios.primeCostPct),
              })}
            </div>
            <div>{t('pnl.marginLine', { value: pct(calc.ratios.operatingMarginPct) })}</div>
          </div>
        </Card>
      </div>
    </div>
  )
}

function StructureBar({
  items,
  total,
  currency,
}: {
  items: Array<{ label: string; value: number; color: string }>
  total: number
  currency: string
}) {
  const safeTotal = total > 0 ? total : 1
  return (
    <div>
      <div className="mb-4 flex h-3 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
        {items.map((i) => (
          <div
            key={i.label}
            style={{ width: `${Math.max(0, (i.value / safeTotal) * 100)}%`, background: i.color }}
            title={`${i.label}: ${money(i.value, currency)}`}
          />
        ))}
      </div>
      {items.map((i) => (
        <div
          key={i.label}
          className="flex items-center gap-2 border-b border-slate-100 py-2 text-sm last:border-0 dark:border-slate-800/70"
        >
          <span className="h-2.5 w-2.5 shrink-0 rounded-sm" style={{ background: i.color }} />
          <span className="mr-auto text-slate-600 dark:text-slate-300">{i.label}</span>
          <span className="tnum text-xs text-slate-500">{pct(safePct(i.value, safeTotal))}</span>
          <span className="tnum w-36 text-right font-medium whitespace-nowrap">
            {money(i.value, currency)}
          </span>
        </div>
      ))}
    </div>
  )
}
