import { useMemo } from 'react'
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import {
  Banknote,
  ChefHat,
  Coins,
  PiggyBank,
  Receipt,
  Target,
  TrendingUp,
  Users,
} from 'lucide-react'
import { Card, SectionTitle } from '@/components/ui'
import { cx } from '@/components/cx'
import { Kpi, StatRow } from '@/components/Kpi'
import { CHART_COLORS, PIE_COLORS, tooltipMoney, useChartTheme } from '@/components/chartTheme'
import { money, moneyShort, num, pct, signedPct } from '@/core/format'
import { convertPeriod } from '@/core/period'
import { PERIOD_ACC_KEY, PERIOD_LABEL_KEY, PERIOD_LOWER_KEY } from '@/i18n/keys'
import { useAppStore } from '@/store/useAppStore'
import { usePeriodView } from '@/store/useCalc'
import { useT } from '@/store/useT'

export default function DashboardPage() {
  const t = useT()
  const { calc, totals, baseTotals, period, ratio, currency, simulated } = usePeriodView()
  const salesMode = useAppStore((s) => s.model.salesMode)
  const businessName = useAppStore((s) => s.model.business.name)
  const ct = useChartTheme()
  const r = calc.ratios
  const be = calc.breakEven
  const tg = calc.target

  const periodAcc = t(PERIOD_ACC_KEY[period])
  const periodLower = t(PERIOD_LOWER_KEY[period])

  const rel = (a: number, b: number) => (b === 0 ? null : ((a - b) / Math.abs(b)) * 100)
  const d = (a: number, b: number) => (simulated ? rel(a, b) : undefined)

  const structure = useMemo(
    () =>
      [
        { name: t('pnl.st.cogs'), value: totals.cogs, color: CHART_COLORS.cogs },
        { name: t('pnl.st.payroll'), value: totals.payroll, color: CHART_COLORS.payroll },
        {
          name: t('pnl.st.variable'),
          value: totals.variableExpenses,
          color: CHART_COLORS.variable,
        },
        { name: t('pnl.st.fixed'), value: totals.fixedExpenses, color: CHART_COLORS.fixed },
        {
          name: t('pnl.st.profit'),
          value: Math.max(0, totals.operatingProfit),
          color: CHART_COLORS.profit,
        },
      ].filter((x) => x.value > 0),
    [totals, t],
  )

  const topDishes = useMemo(
    () =>
      [...calc.dishes]
        .filter((x) => x.active && x.grossMonth !== 0)
        .sort((a, b) => b.grossMonth - a.grossMonth)
        .slice(0, 8)
        .map((x) => ({
          name: x.name || '—',
          gross: x.grossMonth * ratio,
        })),
    [calc.dishes, ratio],
  )

  const profitTone = totals.operatingProfit >= 0 ? 'good' : 'bad'

  return (
    <div className="space-y-5">
      {/* Главное */}
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi
          label={t('dash.revenue', { period: periodLower })}
          value={money(totals.revenue, currency)}
          icon={<TrendingUp size={16} />}
          tone="brand"
          delta={d(totals.revenue, baseTotals.revenue)}
          sub={salesMode === 'menu' ? t('dash.modeMenu') : t('dash.modeAvg')}
        />
        <Kpi
          label={t('dash.operatingProfit')}
          value={money(totals.operatingProfit, currency)}
          icon={<PiggyBank size={16} />}
          tone={profitTone}
          delta={d(totals.operatingProfit, baseTotals.operatingProfit)}
          sub={t('dash.marginIs', { value: pct(r.operatingMarginPct) })}
        />
        <Kpi
          label={t('dash.breakeven')}
          value={money(be.revenue === null ? null : be.revenue * ratio, currency)}
          icon={<Target size={16} />}
          tone="warn"
          sub={
            be.guestsDay === null
              ? undefined
              : t('be.guestsPerDayShort', { count: Math.round(be.guestsDay) })
          }
        />
        <Kpi
          label={t('dash.safety')}
          value={pct(be.marginOfSafetyPct)}
          icon={<Coins size={16} />}
          tone={
            (be.marginOfSafetyPct ?? 0) >= 25
              ? 'good'
              : (be.marginOfSafetyPct ?? 0) >= 10
                ? 'warn'
                : 'bad'
          }
          sub={money(be.marginOfSafety === null ? null : be.marginOfSafety * ratio, currency)}
        />
      </div>

      {/* Полный набор KPI */}
      <Card>
        <SectionTitle
          title={t('dash.kpiTitle', { name: businessName || t('app.cafe') })}
          subtitle={t('dash.kpiSubtitle', { period: t(PERIOD_LABEL_KEY[period]) })}
        />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Mini label={t('kpi.revenue')} value={money(totals.revenue, currency)} caption={t('kpi.cap.revenue')} />
          <Mini label={t('kpi.cogs')} value={money(totals.cogs, currency)} caption={t('kpi.cap.cogs')} />
          <Mini label={t('kpi.grossProfit')} value={money(totals.grossProfit, currency)} caption={t('kpi.cap.grossProfit')} />
          <Mini label={t('kpi.grossMargin')} value={pct(r.grossMarginPct)} caption={t('kpi.cap.grossMargin')} />
          <Mini label={t('kpi.foodCost')} value={pct(r.foodCostPct)} caption={t('kpi.cap.foodCost')} tone={foodTone(r.foodCostPct)} />
          <Mini label={t('kpi.payroll')} value={money(totals.payroll, currency)} caption={t('kpi.cap.payroll')} />
          <Mini label={t('kpi.laborCost')} value={pct(r.laborCostPct)} caption={t('kpi.cap.laborCost')} tone={laborTone(r.laborCostPct)} />
          <Mini label={t('kpi.primeCost')} value={money(totals.primeCost, currency)} caption={t('kpi.cap.primeCost')} />
          <Mini label={t('kpi.primeCostPct')} value={pct(r.primeCostPct)} caption={t('kpi.cap.primeCostPct')} tone={primeTone(r.primeCostPct)} />
          <Mini label={t('kpi.variableExpenses')} value={money(totals.variableExpenses, currency)} caption={t('kpi.cap.variableExpenses')} />
          <Mini label={t('kpi.fixedExpenses')} value={money(totals.fixedExpenses, currency)} caption={t('kpi.cap.fixedExpenses')} />
          <Mini label={t('kpi.operatingProfit')} value={money(totals.operatingProfit, currency)} caption={t('kpi.cap.operatingProfit')} tone={profitTone} />
          <Mini label={t('kpi.operatingMargin')} value={pct(r.operatingMarginPct)} caption={t('kpi.cap.operatingMargin')} />
          <Mini label={t('kpi.averageCheck')} value={money(r.avgCheck, currency)} caption={t('kpi.cap.averageCheck')} />
          <Mini label={t('kpi.guests')} value={num(totals.guests)} caption={t('dash.guestsFor', { period: periodAcc })} />
          <Mini label={t('kpi.profitPerGuest')} value={money(r.profitPerGuest, currency)} caption={t('kpi.cap.profitPerGuest')} tone={profitTone} />
          <Mini label={t('kpi.revenuePerGuest')} value={money(r.revenuePerGuest, currency)} caption={t('kpi.cap.revenuePerGuest')} />
          <Mini label={t('kpi.orders')} value={num(totals.orders)} caption={t('dash.ordersFor', { period: periodAcc })} />
          <Mini label={t('kpi.averageOrder')} value={money(r.avgOrder, currency)} caption={t('kpi.cap.averageOrder')} />
          <Mini
            label={t('kpi.contributionMargin')}
            value={money(be.contributionMargin * ratio, currency)}
            caption={t('kpi.cap.cmRatio', { value: pct(be.cmRatioPct) })}
          />
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <SectionTitle
            icon={<Receipt size={18} />}
            title={t('dash.structureTitle')}
            subtitle={t('dash.structureSubtitle', { period: periodAcc })}
          />
          {totals.revenue <= 0 ? (
            <p className="text-sm text-slate-500">{t('dash.noRevenue')}</p>
          ) : (
            <div className="flex flex-col items-center gap-4 sm:flex-row">
              <div className="h-56 w-full sm:w-1/2">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={structure}
                      dataKey="value"
                      nameKey="name"
                      innerRadius="58%"
                      outerRadius="86%"
                      paddingAngle={2}
                      stroke="none"
                    >
                      {structure.map((s, i) => (
                        <Cell key={s.name} fill={s.color ?? PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={ct.tooltip} formatter={tooltipMoney(currency)} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="w-full sm:w-1/2">
                {structure.map((s) => (
                  <div
                    key={s.name}
                    className="flex items-center gap-2 border-b border-slate-100 py-2 text-sm last:border-0 dark:border-slate-800/70"
                  >
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-sm"
                      style={{ background: s.color }}
                    />
                    <span className="mr-auto text-slate-600 dark:text-slate-300">{s.name}</span>
                    <span className="tnum text-xs text-slate-500">
                      {pct((s.value / totals.revenue) * 100)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>

        <Card>
          <SectionTitle
            icon={<ChefHat size={18} />}
            title={t('dash.topTitle')}
            subtitle={
              salesMode === 'menu'
                ? t('dash.topSubtitleMenu', { period: periodAcc })
                : t('dash.topSubtitleAvg')
            }
          />
          {topDishes.length === 0 ? (
            <p className="text-sm text-slate-500">
              {salesMode === 'menu' ? t('dash.topEmptyMenu') : t('dash.topEmptyAvg')}
            </p>
          ) : (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={topDishes}
                  layout="vertical"
                  margin={{ top: 4, right: 16, left: 8, bottom: 4 }}
                >
                  <XAxis
                    type="number"
                    tick={{ fill: ct.axis, fontSize: 11 }}
                    tickFormatter={(v: number) => moneyShort(v)}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="name"
                    tick={{ fill: ct.axis, fontSize: 11 }}
                    axisLine={false}
                    tickLine={false}
                    width={110}
                  />
                  <Tooltip
                    contentStyle={ct.tooltip}
                    formatter={tooltipMoney(currency, t('menu.col.gross'))}
                    cursor={{ fill: ct.dark ? '#ffffff10' : '#0f172a08' }}
                  />
                  <Bar dataKey="gross" fill={CHART_COLORS.revenue} radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card>
          <SectionTitle icon={<Target size={18} />} title={t('dash.beTitle')} />
          <StatRow label={t('dash.fixedLoad')} value={money(be.fixedCosts * ratio, currency)} />
          <StatRow label={t('be.cmRatio')} value={pct(be.cmRatioPct)} />
          <StatRow
            label={t('dash.revenueForZero')}
            value={money(be.revenue === null ? null : be.revenue * ratio, currency)}
            strong
          />
          <StatRow label={t('be.guestsMonth')} value={num(be.guestsMonth)} />
          <StatRow label={t('be.guestsDay')} value={num(be.guestsDay)} tone="brand" />
          <StatRow label={t('be.ordersDay')} value={num(be.ordersDay)} />
          <a href="#breakeven" className="btn btn-ghost mt-3 w-full">
            {t('dash.beDetails')}
          </a>
        </Card>

        <Card>
          <SectionTitle icon={<Banknote size={18} />} title={t('dash.targetTitle')} />
          {tg.targetMonthly <= 0 ? (
            <p className="text-sm text-slate-500">{t('dash.targetEmpty')}</p>
          ) : (
            <>
              <StatRow
                label={t('dash.targetMonth')}
                value={money(tg.targetMonthly, currency)}
                strong
              />
              <StatRow
                label={t('dash.requiredRevenue')}
                value={money(tg.requiredRevenue, currency)}
                tone="brand"
              />
              <StatRow label={t('dash.requiredGuestsDay')} value={num(tg.requiredGuestsDay)} />
              <StatRow
                label={t('dash.requiredAvgCheck')}
                value={money(tg.requiredAvgCheck, currency)}
              />
              <StatRow
                label={t('dash.revenueGrowth')}
                value={signedPct(tg.revenueGapPct)}
                strong
                tone={(tg.revenueGapPct ?? 0) <= 0 ? 'good' : 'warn'}
              />
            </>
          )}
          <a href="#target" className="btn btn-ghost mt-3 w-full">
            {t('dash.targetOpen')}
          </a>
        </Card>

        <Card>
          <SectionTitle icon={<Users size={18} />} title={t('dash.trafficTitle')} />
          <StatRow label={t('dash.guestsFor', { period: periodAcc })} value={num(totals.guests)} />
          <StatRow
            label={t('dash.guestsPerDay')}
            value={num(convertPeriod(calc.totals.guests, 'month', 'day', calc.factors))}
          />
          <StatRow label={t('kpi.cap.averageCheck')} value={money(r.avgCheck, currency)} />
          <StatRow label={t('kpi.cap.averageOrder')} value={money(r.avgOrder, currency)} />
          <StatRow
            label={t('kpi.cap.profitPerGuest')}
            value={money(r.profitPerGuest, currency)}
            tone={profitTone}
          />
          <StatRow label={t('dash.itemsFor', { period: periodAcc })} value={num(totals.items)} />
          <a href="#sales" className="btn btn-ghost mt-3 w-full">
            {t('dash.salesSettings')}
          </a>
        </Card>
      </div>
    </div>
  )
}

function Mini({
  label,
  value,
  caption,
  tone = 'neutral',
}: {
  label: string
  value: string
  caption: string
  tone?: 'neutral' | 'good' | 'warn' | 'bad'
}) {
  return (
    <div className="rounded-xl border border-slate-200 p-3 dark:border-slate-800">
      <div className="text-[11px] font-semibold tracking-wide text-slate-400 uppercase">{label}</div>
      <div
        className={cx(
          'tnum mt-1 text-base font-semibold break-words',
          tone === 'good'
            ? 'text-emerald-600 dark:text-emerald-400'
            : tone === 'warn'
              ? 'text-amber-600 dark:text-amber-400'
              : tone === 'bad'
                ? 'text-rose-600 dark:text-rose-400'
                : 'text-slate-900 dark:text-slate-50',
        )}
      >
        {value}
      </div>
      <div className="mt-0.5 text-[11px] text-slate-500 dark:text-slate-400">{caption}</div>
    </div>
  )
}

const foodTone = (v: number | null) =>
  v === null ? 'neutral' : v <= 32 ? 'good' : v <= 40 ? 'warn' : 'bad'
const laborTone = (v: number | null) =>
  v === null ? 'neutral' : v <= 25 ? 'good' : v <= 35 ? 'warn' : 'bad'
const primeTone = (v: number | null) =>
  v === null ? 'neutral' : v <= 60 ? 'good' : v <= 70 ? 'warn' : 'bad'
