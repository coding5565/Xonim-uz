import { ChefHat, TrendingUp, Users } from 'lucide-react'
import { Card, Field, NumberInput, SectionTitle, Segmented } from '@/components/ui'
import { cx } from '@/components/cx'
import { Kpi, StatRow } from '@/components/Kpi'
import { money, num, pct } from '@/core/format'
import { convertPeriod } from '@/core/period'
import type { SalesMode } from '@/core/types'
import { PERIOD_LOWER_KEY } from '@/i18n/keys'
import { useAppStore } from '@/store/useAppStore'
import { usePeriodView } from '@/store/useCalc'
import { useT } from '@/store/useT'

export default function SalesPage() {
  const t = useT()
  const mode = useAppStore((s) => s.model.salesMode)
  const setMode = useAppStore((s) => s.setSalesMode)
  const avg = useAppStore((s) => s.model.avgCheckModel)
  const updateAvg = useAppStore((s) => s.updateAvgCheck)
  const business = useAppStore((s) => s.model.business)
  const updateBusiness = useAppStore((s) => s.updateBusiness)
  const dishes = useAppStore((s) => s.model.dishes)
  const { calc, totals, period, currency } = usePeriodView()

  const periodLower = t(PERIOD_LOWER_KEY[period])
  const activeDishes = dishes.filter((d) => d.active).length
  const itemsPerDay = convertPeriod(calc.totals.items, 'month', 'day', calc.factors)

  return (
    <div className="space-y-5">
      <Card>
        <SectionTitle
          icon={<TrendingUp size={18} />}
          title={t('sales.modeTitle')}
          subtitle={t('sales.modeSubtitle')}
          right={
            <Segmented<SalesMode>
              value={mode}
              onChange={setMode}
              options={[
                { value: 'menu', label: t('sales.modeMenu'), icon: <ChefHat size={14} /> },
                { value: 'avgcheck', label: t('sales.modeAvg'), icon: <Users size={14} /> },
              ]}
            />
          }
        />

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi
            label={t('sales.revenue', { period: periodLower })}
            value={money(totals.revenue, currency)}
            tone="brand"
          />
          <Kpi
            label={t('sales.avgCheck')}
            value={money(calc.ratios.avgCheck, currency)}
            sub={t('sales.avgCheckHint')}
          />
          <Kpi label={t('sales.guests', { period: periodLower })} value={num(totals.guests)} />
          <Kpi
            label={t('sales.orders', { period: periodLower })}
            value={num(totals.orders)}
            sub={t('sales.guestsPerCheck', { count: business.guestsPerOrder })}
          />
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* Режим 1 */}
        <Card className={cx(mode !== 'menu' && 'opacity-60')}>
          <SectionTitle
            icon={<ChefHat size={18} />}
            title={t('sales.mode1Title')}
            subtitle={t('sales.mode1Subtitle')}
            right={
              mode === 'menu' ? (
                <span className="chip bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300">
                  {t('sales.activeBadge')}
                </span>
              ) : (
                <button className="btn btn-ghost" onClick={() => setMode('menu')}>
                  {t('sales.enable')}
                </button>
              )
            }
          />
          <StatRow
            label={t('sales.dishesActive')}
            value={t('sales.ofTotal', { active: activeDishes, total: dishes.length })}
          />
          <StatRow label={t('sales.itemsPerDay')} value={num(itemsPerDay)} />
          <StatRow label={t('sales.revenueMonth')} value={money(calc.totals.revenue, currency)} strong />
          <StatRow label={t('sales.foodCostMenu')} value={pct(calc.ratios.foodCostPct)} />
          <div className="mt-4">
            <Field label={t('sales.itemsPerGuest')} hint={t('sales.itemsPerGuestHint')}>
              <NumberInput
                value={business.itemsPerGuest}
                onChange={(v) => updateBusiness({ itemsPerGuest: v })}
                min={0.1}
                disabled={mode !== 'menu'}
              />
            </Field>
          </div>
          <a href="#menu" className="btn btn-ghost mt-4 w-full">
            {t('sales.goToMenu')}
          </a>
        </Card>

        {/* Режим 2 */}
        <Card className={cx(mode !== 'avgcheck' && 'opacity-60')}>
          <SectionTitle
            icon={<Users size={18} />}
            title={t('sales.mode2Title')}
            subtitle={t('sales.mode2Subtitle')}
            right={
              mode === 'avgcheck' ? (
                <span className="chip bg-brand-100 text-brand-700 dark:bg-brand-900/40 dark:text-brand-300">
                  {t('sales.activeBadge')}
                </span>
              ) : (
                <button className="btn btn-ghost" onClick={() => setMode('avgcheck')}>
                  {t('sales.enable')}
                </button>
              )
            }
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('sales.guestsPerDay')}>
              <NumberInput
                value={avg.guestsPerDay}
                onChange={(v) => updateAvg({ guestsPerDay: v })}
                min={0}
                disabled={mode !== 'avgcheck'}
              />
            </Field>
            <Field label={t('sales.avgCheck')}>
              <NumberInput
                value={avg.avgCheck}
                onChange={(v) => updateAvg({ avgCheck: v })}
                min={0}
                suffix={currency}
                disabled={mode !== 'avgcheck'}
              />
            </Field>
            <Field label={t('sales.foodCost')} hint={t('sales.foodCostHint')}>
              <NumberInput
                value={avg.foodCostPct}
                onChange={(v) => updateAvg({ foodCostPct: v })}
                min={0}
                max={100}
                suffix="%"
                disabled={mode !== 'avgcheck'}
              />
            </Field>
            <Field label={t('sales.workDays')} hint={t('sales.workDaysHint')}>
              <NumberInput
                value={business.workingDaysPerMonth}
                onChange={(v) => updateBusiness({ workingDaysPerMonth: v })}
                min={1}
                max={31}
              />
            </Field>
          </div>
          <div className="mt-4 rounded-lg bg-slate-50 px-3 py-2.5 text-sm dark:bg-slate-800/50">
            <div className="tnum text-slate-600 dark:text-slate-300">
              {num(avg.guestsPerDay)} × {money(avg.avgCheck, currency)} ×{' '}
              {t('sales.formulaDays', { count: business.workingDaysPerMonth })}
            </div>
            <div className="tnum mt-1 text-base font-semibold">
              {t('sales.perMonthResult', {
                value: money(
                  avg.guestsPerDay * avg.avgCheck * business.workingDaysPerMonth,
                  currency,
                ),
              })}
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}
