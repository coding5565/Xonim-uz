import { useMemo } from 'react'
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
import { Check, GitCompareArrows, Plus } from 'lucide-react'
import { Card, DeleteButton, SectionTitle } from '@/components/ui'
import { cx } from '@/components/cx'
import { CHART_COLORS, tooltipMoney, useChartTheme } from '@/components/chartTheme'
import { calculate, scaleTotals } from '@/core/engine'
import { money, moneyShort, num, pct } from '@/core/format'
import type { Adjustments } from '@/core/types'
import type { TKey } from '@/i18n'
import { PERIOD_ACC_KEY } from '@/i18n/keys'
import { useAppStore } from '@/store/useAppStore'
import { usePeriodView } from '@/store/useCalc'
import { useScenarioLabel, useT } from '@/store/useT'

const ADJ_LABEL_KEY: Record<keyof Adjustments, TKey> = {
  guestsPct: 'adj.guestsPct',
  avgCheckPct: 'adj.avgCheckPct',
  menuPricePct: 'adj.menuPricePct',
  menuSalesPct: 'adj.menuSalesPct',
  cogsPct: 'adj.cogsPct',
  ingredientPricePct: 'adj.ingredientPricePct',
  payrollPct: 'adj.payrollPct',
  extraStaff: 'adj.extraStaff',
  extraStaffCost: 'adj.extraStaffCost',
  fixedPct: 'adj.fixedPct',
  variablePct: 'adj.variablePct',
}

/** Эти ручки задаются числом, а не процентом. */
const ABSOLUTE_ADJ: Array<keyof Adjustments> = ['extraStaff', 'extraStaffCost']

export default function ScenariosPage() {
  const t = useT()
  const model = useAppStore((s) => s.model)
  const scenarios = useAppStore((s) => s.scenarios)
  const activeId = useAppStore((s) => s.activeScenarioId)
  const setActive = useAppStore((s) => s.setActiveScenario)
  const rename = useAppStore((s) => s.renameScenario)
  const removeScenario = useAppStore((s) => s.removeScenario)
  const addScenario = useAppStore((s) => s.addScenario)
  const scenarioLabel = useScenarioLabel()
  const { period, ratio, currency } = usePeriodView()
  const ct = useChartTheme()
  const periodAcc = t(PERIOD_ACC_KEY[period])

  const computed = useMemo(
    () =>
      scenarios.map((s) => {
        const calc = calculate(model, s.adj)
        return { scenario: s, calc, totals: scaleTotals(calc.totals, ratio) }
      }),
    [scenarios, model, ratio],
  )

  const baseProfit = computed.find((c) => c.scenario.kind === 'current')?.totals.operatingProfit ?? 0

  const chartData = computed.map((c) => ({
    name: scenarioLabel(c.scenario),
    profit: c.totals.operatingProfit,
  }))

  const rows: Array<{
    label: string
    get: (c: (typeof computed)[number]) => string
    strong?: boolean
  }> = [
    { label: t('sim.row.revenue'), get: (c) => money(c.totals.revenue, currency), strong: true },
    { label: t('sim.row.guests'), get: (c) => num(c.totals.guests) },
    { label: t('sim.row.avgCheck'), get: (c) => money(c.calc.ratios.avgCheck, currency) },
    { label: t('sim.row.cogs'), get: (c) => money(c.totals.cogs, currency) },
    { label: t('scen.foodCost'), get: (c) => pct(c.calc.ratios.foodCostPct) },
    { label: t('sim.row.gross'), get: (c) => money(c.totals.grossProfit, currency) },
    { label: t('sim.row.payroll'), get: (c) => money(c.totals.payroll, currency) },
    { label: t('scen.laborCost'), get: (c) => pct(c.calc.ratios.laborCostPct) },
    { label: t('scen.primeCost'), get: (c) => pct(c.calc.ratios.primeCostPct) },
    { label: t('sim.row.variable'), get: (c) => money(c.totals.variableExpenses, currency) },
    { label: t('sim.row.fixed'), get: (c) => money(c.totals.fixedExpenses, currency) },
    {
      label: t('sim.row.profit'),
      get: (c) => money(c.totals.operatingProfit, currency),
      strong: true,
    },
    { label: t('scen.operatingMargin'), get: (c) => pct(c.calc.ratios.operatingMarginPct) },
    {
      label: t('sim.row.breakeven'),
      get: (c) =>
        money(c.calc.breakEven.revenue === null ? null : c.calc.breakEven.revenue * ratio, currency),
    },
    { label: t('scen.beGuestsDay'), get: (c) => num(c.calc.breakEven.guestsDay) },
    { label: t('scen.safety'), get: (c) => pct(c.calc.breakEven.marginOfSafetyPct) },
    { label: t('scen.profitPerGuest'), get: (c) => money(c.calc.ratios.profitPerGuest, currency) },
  ]

  return (
    <div className="space-y-5">
      <Card>
        <SectionTitle
          icon={<GitCompareArrows size={18} />}
          title={t('scen.title')}
          subtitle={t('scen.subtitle', { period: periodAcc })}
          right={
            <button className="btn btn-primary" onClick={() => addScenario(t('scen.newScenario'))}>
              <Plus size={16} /> {t('scen.addScenario')}
            </button>
          }
        />

        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse">
            <thead>
              <tr className="border-b border-slate-200 dark:border-slate-800">
                <th className="th sticky left-0 bg-white dark:bg-slate-900">{t('common.metric')}</th>
                {computed.map(({ scenario: s }) => (
                  <th key={s.id} className="th text-right">
                    <div className="flex items-center justify-end gap-1">
                      <input
                        className={cx(
                          'w-32 bg-transparent text-right text-xs font-semibold uppercase outline-none',
                          s.id === activeId
                            ? 'text-brand-600 dark:text-brand-400'
                            : 'text-slate-500 dark:text-slate-400',
                        )}
                        value={s.name}
                        placeholder={scenarioLabel(s)}
                        onChange={(e) => rename(s.id, e.target.value)}
                      />
                      {s.kind === 'custom' && s.id !== 'sc_custom' && (
                        <DeleteButton
                          title={t('common.delete')}
                          onClick={() => removeScenario(s.id)}
                        />
                      )}
                    </div>
                    <button
                      className={cx(
                        'mt-1 inline-flex cursor-pointer items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium normal-case',
                        s.id === activeId
                          ? 'bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300'
                          : 'text-slate-400 hover:text-slate-700 dark:hover:text-slate-200',
                      )}
                      onClick={() => setActive(s.id)}
                    >
                      {s.id === activeId ? (
                        <>
                          <Check size={11} /> {t('scen.active')}
                        </>
                      ) : (
                        t('scen.makeActive')
                      )}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={r.label}
                  className={cx(
                    'border-b border-slate-100 last:border-0 dark:border-slate-800/70',
                    r.strong && 'bg-slate-50/70 dark:bg-slate-800/30',
                  )}
                >
                  <td
                    className={cx(
                      'td sticky left-0 bg-white dark:bg-slate-900',
                      r.strong && 'font-semibold',
                    )}
                  >
                    {r.label}
                  </td>
                  {computed.map((c) => (
                    <td
                      key={c.scenario.id}
                      className={cx(
                        'td tnum text-right whitespace-nowrap',
                        r.strong && 'font-semibold',
                        c.scenario.id === activeId && 'bg-brand-50/60 dark:bg-brand-900/10',
                      )}
                    >
                      {r.get(c)}
                    </td>
                  ))}
                </tr>
              ))}
              <tr className="border-t-2 border-slate-200 dark:border-slate-700">
                <td className="td sticky left-0 bg-white font-semibold dark:bg-slate-900">
                  {t('scen.deltaRow')}
                </td>
                {computed.map((c) => {
                  const d = c.totals.operatingProfit - baseProfit
                  return (
                    <td
                      key={c.scenario.id}
                      className={cx(
                        'td tnum text-right font-semibold whitespace-nowrap',
                        d > 0
                          ? 'text-emerald-600 dark:text-emerald-400'
                          : d < 0
                            ? 'text-rose-600 dark:text-rose-400'
                            : 'text-slate-400',
                      )}
                    >
                      {d === 0 ? '—' : `${d > 0 ? '+' : '−'}${money(Math.abs(d), currency)}`}
                    </td>
                  )
                })}
              </tr>
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <SectionTitle
            title={t('scen.chartTitle')}
            subtitle={t('common.forPeriod', { period: periodAcc })}
          />
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
                  formatter={tooltipMoney(currency, t('sim.row.profit'))}
                />
                <Bar dataKey="profit" radius={[4, 4, 0, 0]}>
                  {chartData.map((d) => (
                    <Cell
                      key={d.name}
                      fill={d.profit >= 0 ? CHART_COLORS.profit : CHART_COLORS.loss}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <SectionTitle title={t('scen.paramsTitle')} subtitle={t('scen.paramsSubtitle')} />
          <div className="space-y-3">
            {computed.map(({ scenario: s }) => {
              const active = (Object.entries(s.adj) as Array<[keyof Adjustments, number]>).filter(
                ([, v]) => v !== 0,
              )
              return (
                <div
                  key={s.id}
                  className={cx(
                    'rounded-lg border p-3',
                    s.id === activeId
                      ? 'border-brand-300 bg-brand-50/50 dark:border-brand-800 dark:bg-brand-900/20'
                      : 'border-slate-200 dark:border-slate-800',
                  )}
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-sm font-medium">{scenarioLabel(s)}</span>
                    <button
                      className="btn btn-ghost px-2 py-1 text-xs"
                      onClick={() => setActive(s.id)}
                    >
                      {t('common.open')}
                    </button>
                  </div>
                  {active.length === 0 ? (
                    <span className="text-xs text-slate-500">{t('scen.noChanges')}</span>
                  ) : (
                    <div className="flex flex-wrap gap-1.5">
                      {active.map(([k, v]) => (
                        <span
                          key={k}
                          className="chip bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                        >
                          {t(ADJ_LABEL_KEY[k])}: {v > 0 ? '+' : ''}
                          {num(v, 1)}
                          {ABSOLUTE_ADJ.includes(k) ? '' : '%'}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </Card>
      </div>
    </div>
  )
}
