import { useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { FlaskConical, RotateCcw, Save } from 'lucide-react'
import { Card, NumberInput, SectionTitle, Slider, TextInput } from '@/components/ui'
import { cx } from '@/components/cx'
import { Delta, Kpi } from '@/components/Kpi'
import { CHART_COLORS, useChartTheme } from '@/components/chartTheme'
import { money, moneyShort, num, pct } from '@/core/format'
import { PERIOD_ACC_KEY, PERIOD_LOWER_KEY } from '@/i18n/keys'
import { useActiveScenario, useAppStore } from '@/store/useAppStore'
import { usePeriodView } from '@/store/useCalc'
import { useScenarioLabel, useT } from '@/store/useT'

export default function SimulatorPage() {
  const t = useT()
  const scenario = useActiveScenario()
  const scenarioLabel = useScenarioLabel()
  const patch = useAppStore((s) => s.patchAdjustments)
  const reset = useAppStore((s) => s.resetAdjustments)
  const addScenario = useAppStore((s) => s.addScenario)
  const salesMode = useAppStore((s) => s.model.salesMode)
  const { calc, base, totals, baseTotals, period, currency } = usePeriodView()
  const ct = useChartTheme()
  const [name, setName] = useState('')

  const adj = scenario.adj
  const periodAcc = t(PERIOD_ACC_KEY[period])
  const periodLower = t(PERIOD_LOWER_KEY[period])
  const rel = (a: number, b: number) => (b === 0 ? null : ((a - b) / Math.abs(b)) * 100)

  const compare = [
    {
      label: t('sim.row.revenue'),
      now: baseTotals.revenue,
      next: totals.revenue,
      fmt: (v: number) => money(v, currency),
      good: 'up' as const,
    },
    {
      label: t('sim.row.cogs'),
      now: baseTotals.cogs,
      next: totals.cogs,
      fmt: (v: number) => money(v, currency),
      good: 'down' as const,
    },
    {
      label: t('sim.row.gross'),
      now: baseTotals.grossProfit,
      next: totals.grossProfit,
      fmt: (v: number) => money(v, currency),
      good: 'up' as const,
    },
    {
      label: t('sim.row.payroll'),
      now: baseTotals.payroll,
      next: totals.payroll,
      fmt: (v: number) => money(v, currency),
      good: 'down' as const,
    },
    {
      label: t('sim.row.variable'),
      now: baseTotals.variableExpenses,
      next: totals.variableExpenses,
      fmt: (v: number) => money(v, currency),
      good: 'down' as const,
    },
    {
      label: t('sim.row.fixed'),
      now: baseTotals.fixedExpenses,
      next: totals.fixedExpenses,
      fmt: (v: number) => money(v, currency),
      good: 'down' as const,
    },
    {
      label: t('sim.row.profit'),
      now: baseTotals.operatingProfit,
      next: totals.operatingProfit,
      fmt: (v: number) => money(v, currency),
      good: 'up' as const,
    },
    {
      label: t('sim.row.guests'),
      now: baseTotals.guests,
      next: totals.guests,
      fmt: (v: number) => num(v),
      good: 'up' as const,
    },
    {
      label: t('sim.row.avgCheck'),
      now: base.ratios.avgCheck ?? 0,
      next: calc.ratios.avgCheck ?? 0,
      fmt: (v: number) => money(v, currency),
      good: 'up' as const,
    },
    {
      label: t('sim.row.breakeven'),
      now: base.breakEven.revenue ?? 0,
      next: calc.breakEven.revenue ?? 0,
      fmt: (v: number) => money(v, currency),
      good: 'down' as const,
    },
  ]

  const chartData = [
    { name: t('sim.chart.revenue'), now: baseTotals.revenue, next: totals.revenue },
    { name: t('sim.chart.gross'), now: baseTotals.grossProfit, next: totals.grossProfit },
    { name: t('sim.chart.profit'), now: baseTotals.operatingProfit, next: totals.operatingProfit },
  ]

  const profitDelta = totals.operatingProfit - baseTotals.operatingProfit

  return (
    <div className="grid gap-5 xl:grid-cols-[400px_1fr]">
      {/* Ручки */}
      <div className="space-y-5">
        <Card>
          <SectionTitle
            icon={<FlaskConical size={18} />}
            title={t('sim.title')}
            subtitle={
              scenario.kind === 'current'
                ? t('sim.subtitleCurrent')
                : t('sim.subtitleScenario', { name: scenarioLabel(scenario) })
            }
            right={
              <button className="btn btn-ghost" onClick={reset} title={t('sim.reset')}>
                <RotateCcw size={16} />
              </button>
            }
          />

          <div className="space-y-4">
            <Group title={t('sim.groupSales')} />
            <Slider
              label={t('sim.guests')}
              value={adj.guestsPct}
              onChange={(v) => patch({ guestsPct: v })}
              min={-80}
              max={150}
              hint={salesMode === 'menu' ? t('sim.guestsHintMenu') : t('sim.guestsHintAvg')}
            />
            <Slider
              label={t('sim.avgCheck')}
              value={adj.avgCheckPct}
              onChange={(v) => patch({ avgCheckPct: v })}
              min={-50}
              max={100}
              hint={t('sim.avgCheckHint')}
            />
            <Slider
              label={t('sim.prices')}
              value={adj.menuPricePct}
              onChange={(v) => patch({ menuPricePct: v })}
              min={-50}
              max={100}
            />
            <Slider
              label={t('sim.salesQty')}
              value={adj.menuSalesPct}
              onChange={(v) => patch({ menuSalesPct: v })}
              min={-80}
              max={150}
            />

            <Group title={t('sim.groupCost')} />
            <Slider
              label={t('sim.cogs')}
              value={adj.cogsPct}
              onChange={(v) => patch({ cogsPct: v })}
              min={-50}
              max={100}
              hint={t('sim.cogsHint')}
            />
            <Slider
              label={t('sim.ingredients')}
              value={adj.ingredientPricePct}
              onChange={(v) => patch({ ingredientPricePct: v })}
              min={-50}
              max={150}
              hint={t('sim.ingredientsHint')}
            />

            <Group title={t('sim.groupStaff')} />
            <Slider
              label={t('sim.payroll')}
              value={adj.payrollPct}
              onChange={(v) => patch({ payrollPct: v })}
              min={-50}
              max={100}
            />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <span className="label">{t('sim.extraStaff')}</span>
                <NumberInput
                  value={adj.extraStaff}
                  min={0}
                  max={50}
                  onChange={(v) => patch({ extraStaff: v })}
                />
              </div>
              <div>
                <span className="label">{t('sim.extraStaffCost')}</span>
                <NumberInput
                  value={adj.extraStaffCost}
                  min={0}
                  onChange={(v) => patch({ extraStaffCost: v })}
                />
              </div>
            </div>

            <Group title={t('sim.groupExpenses')} />
            <Slider
              label={t('sim.fixed')}
              value={adj.fixedPct}
              onChange={(v) => patch({ fixedPct: v })}
              min={-50}
              max={100}
            />
            <Slider
              label={t('sim.variable')}
              value={adj.variablePct}
              onChange={(v) => patch({ variablePct: v })}
              min={-50}
              max={100}
            />
          </div>
        </Card>

        <Card>
          <SectionTitle title={t('sim.saveTitle')} subtitle={t('sim.saveSubtitle')} />
          <div className="flex gap-2">
            <TextInput value={name} onChange={setName} placeholder={t('sim.savePlaceholder')} />
            <button
              className="btn btn-primary shrink-0"
              onClick={() => {
                addScenario(name.trim() || t('sim.newScenario'), adj)
                setName('')
              }}
            >
              <Save size={16} /> {t('sim.save')}
            </button>
          </div>
        </Card>
      </div>

      {/* Результат */}
      <div className="space-y-5">
        <div
          className={cx(
            'rounded-xl border px-4 py-3 text-sm',
            profitDelta > 0
              ? 'border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-100'
              : profitDelta < 0
                ? 'border-rose-200 bg-rose-50 text-rose-900 dark:border-rose-900/50 dark:bg-rose-950/30 dark:text-rose-100'
                : 'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-800/40 dark:text-slate-200',
          )}
        >
          {profitDelta === 0
            ? t('sim.neutral')
            : t(profitDelta > 0 ? 'sim.profitUp' : 'sim.profitDown', {
                period: periodAcc,
                delta: money(Math.abs(profitDelta), currency),
                from: money(baseTotals.operatingProfit, currency),
                to: money(totals.operatingProfit, currency),
              })}
        </div>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            label={t('dash.revenue', { period: periodLower })}
            value={money(totals.revenue, currency)}
            delta={rel(totals.revenue, baseTotals.revenue)}
          />
          <Kpi
            label={t('sim.row.profit')}
            value={money(totals.operatingProfit, currency)}
            tone={totals.operatingProfit >= 0 ? 'good' : 'bad'}
            delta={rel(totals.operatingProfit, baseTotals.operatingProfit)}
          />
          <Kpi
            label={t('sim.kpiMargin')}
            value={pct(calc.ratios.operatingMarginPct)}
            sub={t('common.was', { value: pct(base.ratios.operatingMarginPct) })}
          />
          <Kpi
            label={t('sim.kpiSafety')}
            value={pct(calc.breakEven.marginOfSafetyPct)}
            sub={t('common.was', { value: pct(base.breakEven.marginOfSafetyPct) })}
          />
        </div>

        <Card>
          <SectionTitle
            title={t('sim.compareTitle')}
            subtitle={t('sim.compareSubtitle', { period: periodAcc })}
          />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[560px]">
              <thead>
                <tr className="border-b border-slate-200 dark:border-slate-800">
                  <th className="th">{t('common.metric')}</th>
                  <th className="th text-right">{t('common.now')}</th>
                  <th className="th text-right">{t('sim.colNext')}</th>
                  <th className="th text-right">{t('common.change')}</th>
                </tr>
              </thead>
              <tbody>
                {compare.map((c) => {
                  const d = rel(c.next, c.now)
                  return (
                    <tr
                      key={c.label}
                      className="border-b border-slate-100 last:border-0 dark:border-slate-800/70"
                    >
                      <td className="td">{c.label}</td>
                      <td className="td tnum text-right text-slate-500 dark:text-slate-400">
                        {c.fmt(c.now)}
                      </td>
                      <td className="td tnum text-right font-medium">{c.fmt(c.next)}</td>
                      <td className="td text-right">
                        {d === null ? (
                          <span className="text-slate-400">—</span>
                        ) : (
                          <Delta value={d} goodWhen={c.good} />
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Card>

        <Card>
          <SectionTitle title={t('sim.chartTitle')} />
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                <CartesianGrid stroke={ct.grid} strokeDasharray="3 3" vertical={false} />
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
                  width={72}
                />
                <Tooltip
                  contentStyle={ct.tooltip}
                  formatter={(v: unknown, n: unknown): [string, string] => [
                    money(Number(v), currency),
                    n === 'now' ? t('common.now') : t('sim.colNext'),
                  ]}
                />
                <Bar
                  dataKey="now"
                  name={t('common.now')}
                  fill={ct.dark ? '#475569' : '#cbd5e1'}
                  radius={[4, 4, 0, 0]}
                />
                <Bar dataKey="next" name={t('sim.colNext')} radius={[4, 4, 0, 0]}>
                  {chartData.map((d) => (
                    <Cell
                      key={d.name}
                      fill={d.next >= d.now ? CHART_COLORS.revenue : CHART_COLORS.cogs}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-2 text-xs text-slate-500 dark:text-slate-400">
            {t('sim.footnote', {
              profit: money(calc.ratios.profitPerGuest, currency),
              profitBase: money(base.ratios.profitPerGuest, currency),
              be: num(calc.breakEven.guestsDay),
              beBase: num(base.breakEven.guestsDay),
            })}
          </div>
        </Card>
      </div>
    </div>
  )
}

function Group({ title }: { title: string }) {
  return (
    <div className="border-t border-slate-100 pt-3 text-xs font-semibold tracking-wide text-slate-400 uppercase first:border-0 first:pt-0 dark:border-slate-800">
      {title}
    </div>
  )
}
