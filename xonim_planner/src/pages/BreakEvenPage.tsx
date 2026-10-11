import { useMemo } from 'react'
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { ShieldCheck, Target } from 'lucide-react'
import { Card, SectionTitle } from '@/components/ui'
import { cx } from '@/components/cx'
import { Kpi, StatRow } from '@/components/Kpi'
import { CHART_COLORS, tooltipLabel, tooltipMoney, useChartTheme } from '@/components/chartTheme'
import { money, moneyShort, num, pct } from '@/core/format'
import { convertPeriod } from '@/core/period'
import { PERIOD_ACC_KEY, PERIOD_LOWER_KEY } from '@/i18n/keys'
import { usePeriodView } from '@/store/useCalc'
import { useT } from '@/store/useT'

export default function BreakEvenPage() {
  const t = useT()
  const { calc, totals, period, ratio, currency } = usePeriodView()
  const be = calc.breakEven
  const ct = useChartTheme()
  const f = calc.factors
  const periodAcc = t(PERIOD_ACC_KEY[period])
  const periodLower = t(PERIOD_LOWER_KEY[period])

  const avgCheck = calc.ratios.avgCheck ?? 0
  const varRatio = calc.totals.revenue > 0 ? be.variableCosts / calc.totals.revenue : 0

  /** График CVP: как ведут себя выручка и суммарные затраты при росте трафика. */
  const chart = useMemo(() => {
    const maxGuests = Math.max(calc.totals.guests, be.guestsMonth ?? 0) * 1.35 || 100
    const steps = 24
    return Array.from({ length: steps + 1 }, (_, i) => {
      const guests = (maxGuests / steps) * i
      const revenue = guests * avgCheck
      return {
        guests,
        revenue,
        costs: be.fixedCosts + revenue * varRatio,
      }
    })
  }, [calc.totals.guests, be.guestsMonth, be.fixedCosts, avgCheck, varRatio])

  const mosTone = (() => {
    const v = be.marginOfSafetyPct
    if (v === null) return 'neutral' as const
    if (v >= 25) return 'good' as const
    if (v >= 10) return 'warn' as const
    return 'bad' as const
  })()

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          label={t('be.cm')}
          value={money(be.contributionMargin * ratio, currency)}
          sub={t('be.cmSub', { period: periodAcc })}
          tone="brand"
        />
        <Kpi label={t('be.cmRatio')} value={pct(be.cmRatioPct)} sub={t('be.cmRatioSub')} />
        <Kpi
          label={t('be.point', { period: periodLower })}
          value={money(be.revenue === null ? null : be.revenue * ratio, currency)}
          tone="warn"
        />
        <Kpi
          label={t('be.safety')}
          value={pct(be.marginOfSafetyPct)}
          sub={money(be.marginOfSafety === null ? null : be.marginOfSafety * ratio, currency)}
          tone={mosTone}
        />
      </div>

      {!be.reachable && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800 dark:border-rose-900/50 dark:bg-rose-950/40 dark:text-rose-200">
          {t('be.unreachable')}
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
        <Card>
          <SectionTitle
            icon={<Target size={18} />}
            title={t('be.chartTitle')}
            subtitle={t('be.chartSubtitle')}
          />
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart} margin={{ top: 8, right: 12, left: 8, bottom: 8 }}>
                <CartesianGrid stroke={ct.grid} strokeDasharray="3 3" vertical={false} />
                <XAxis
                  dataKey="guests"
                  tick={{ fill: ct.axis, fontSize: 11 }}
                  tickFormatter={(v: number) => moneyShort(v)}
                  axisLine={{ stroke: ct.grid }}
                  tickLine={false}
                  label={{
                    value: t('be.axisGuests'),
                    position: 'insideBottomRight',
                    offset: -4,
                    fill: ct.axis,
                    fontSize: 11,
                  }}
                />
                <YAxis
                  tick={{ fill: ct.axis, fontSize: 11 }}
                  tickFormatter={(v: number) => moneyShort(v)}
                  axisLine={false}
                  tickLine={false}
                  width={72}
                />
                <Tooltip
                  contentStyle={ct.tooltip}
                  labelFormatter={tooltipLabel((v) => t('be.tooltipGuests', { count: v }))}
                  formatter={tooltipMoney(currency)}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line
                  type="monotone"
                  dataKey="revenue"
                  name={t('be.lineRevenue')}
                  stroke={CHART_COLORS.revenue}
                  strokeWidth={2}
                  dot={false}
                />
                <Line
                  type="monotone"
                  dataKey="costs"
                  name={t('be.lineCosts')}
                  stroke={CHART_COLORS.cogs}
                  strokeWidth={2}
                  dot={false}
                />
                {be.guestsMonth !== null && (
                  <ReferenceLine
                    x={be.guestsMonth}
                    stroke={CHART_COLORS.accent}
                    strokeDasharray="4 4"
                    label={{
                      value: t('be.markZero'),
                      fill: ct.axis,
                      fontSize: 11,
                      position: 'top',
                    }}
                  />
                )}
                <ReferenceLine
                  x={calc.totals.guests}
                  stroke={ct.axis}
                  strokeDasharray="2 6"
                  label={{
                    value: t('be.markNow'),
                    fill: ct.axis,
                    fontSize: 11,
                    position: 'insideTopRight',
                  }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <div className="space-y-5">
          <Card>
            <SectionTitle title={t('be.needTitle')} subtitle={t('be.needSubtitle')} />
            <StatRow label={t('be.revenueMonth')} value={money(be.revenue, currency)} strong />
            <StatRow
              label={t('be.revenueDay')}
              value={money(
                be.revenue === null ? null : convertPeriod(be.revenue, 'month', 'day', f),
                currency,
              )}
            />
            <StatRow label={t('be.guestsMonth')} value={num(be.guestsMonth)} strong />
            <StatRow label={t('be.guestsDay')} value={num(be.guestsDay)} tone="brand" />
            <StatRow label={t('be.ordersMonth')} value={num(be.ordersMonth)} />
            <StatRow label={t('be.ordersDay')} value={num(be.ordersDay)} tone="brand" />
            <StatRow label={t('be.avgCheckUsed')} value={money(calc.ratios.avgCheck, currency)} />
            <StatRow label={t('be.avgOrder')} value={money(calc.ratios.avgOrder, currency)} />
          </Card>

          <Card>
            <SectionTitle
              icon={<ShieldCheck size={18} />}
              title={t('be.safety')}
              subtitle={t('be.safetySubtitle')}
            />
            <div
              className={cx(
                'tnum mb-3 text-3xl font-semibold',
                mosTone === 'good'
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : mosTone === 'warn'
                    ? 'text-amber-600 dark:text-amber-400'
                    : 'text-rose-600 dark:text-rose-400',
              )}
            >
              {pct(be.marginOfSafetyPct)}
            </div>
            <StatRow label={t('be.actualRevenue')} value={money(totals.revenue, currency)} />
            <StatRow
              label={t('dash.breakeven')}
              value={money(be.revenue === null ? null : be.revenue * ratio, currency)}
            />
            <StatRow
              label={t('be.difference')}
              value={money(be.marginOfSafety === null ? null : be.marginOfSafety * ratio, currency)}
              strong
              tone={be.marginOfSafety !== null && be.marginOfSafety >= 0 ? 'good' : 'bad'}
            />
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div
                className="h-full rounded-full bg-emerald-500"
                style={{ width: `${Math.max(0, Math.min(100, be.marginOfSafetyPct ?? 0))}%` }}
              />
            </div>
          </Card>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <SectionTitle title={t('be.varTitle')} subtitle={t('be.varSubtitle')} />
          <StatRow label={t('be.cogs')} value={money(calc.totals.cogs * ratio, currency)} />
          <StatRow
            label={t('be.varPayroll')}
            value={money(calc.totals.payrollVariable * ratio, currency)}
          />
          <StatRow
            label={t('be.varOpex')}
            value={money(calc.totals.variableExpensesVariable * ratio, currency)}
          />
          <StatRow
            label={t('be.totalVar')}
            value={money(be.variableCosts * ratio, currency)}
            strong
          />
          <StatRow label={t('be.cmPerGuest')} value={money(be.cmPerGuest, currency)} tone="brand" />
        </Card>

        <Card>
          <SectionTitle title={t('be.fixedTitle')} subtitle={t('be.fixedSubtitle')} />
          <StatRow
            label={t('be.fixedExpenses')}
            value={money(calc.totals.fixedExpenses * ratio, currency)}
          />
          <StatRow
            label={t('be.fixedPayroll')}
            value={money(calc.totals.payrollFixed * ratio, currency)}
            hint={t('be.fixedPayrollHint')}
          />
          <StatRow
            label={t('be.fixedFromVar')}
            value={money(calc.totals.variableExpensesFixed * ratio, currency)}
          />
          <StatRow label={t('be.totalFixed')} value={money(be.fixedCosts * ratio, currency)} strong />
          <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-800/50 dark:text-slate-300">
            {t('be.formula', {
              fixed: money(be.fixedCosts, currency),
              ratio: pct(be.cmRatioPct),
              result: money(be.revenue, currency),
            })}
          </div>
        </Card>
      </div>
    </div>
  )
}
