import { Trophy } from 'lucide-react'
import { Card, Field, NumberInput, SectionTitle, Select } from '@/components/ui'
import { Kpi, StatRow } from '@/components/Kpi'
import { money, num, pct, safeDiv, safePct, signedPct } from '@/core/format'
import { PERIODS, convertPeriod } from '@/core/period'
import type { Period } from '@/core/types'
import { PERIOD_ACC_KEY, PERIOD_LABEL_KEY } from '@/i18n/keys'
import { useAppStore } from '@/store/useAppStore'
import { usePeriodView } from '@/store/useCalc'
import { useT } from '@/store/useT'

export default function TargetPage() {
  const t = useT()
  const b = useAppStore((s) => s.model.business)
  const update = useAppStore((s) => s.updateBusiness)
  const { calc, period, ratio, currency } = usePeriodView()
  const tg = calc.target
  const be = calc.breakEven

  const periodOptions = PERIODS.map((p) => ({ value: p, label: t(PERIOD_LABEL_KEY[p]) }))
  const periodAcc = t(PERIOD_ACC_KEY[period])

  const currentProfit = calc.totals.operatingProfit
  const progress = tg.targetMonthly > 0 ? Math.max(0, (currentProfit / tg.targetMonthly) * 100) : 0
  const achieved = currentProfit >= tg.targetMonthly && tg.targetMonthly > 0

  /* Четыре способа закрыть разрыв — каждый считается при прочих равных. */
  const gap = Math.max(0, tg.targetMonthly - currentProfit)
  const checkNeeded = tg.requiredAvgCheck
  const checkNeededPct =
    checkNeeded !== null && calc.ratios.avgCheck
      ? (checkNeeded / calc.ratios.avgCheck - 1) * 100
      : null
  const requiredCmrPct = safePct(be.fixedCosts + tg.targetMonthly, calc.totals.revenue)
  const cmrGapPp =
    requiredCmrPct !== null && be.cmRatioPct !== null ? requiredCmrPct - be.cmRatioPct : null
  const fixedCutPct = safePct(gap, be.fixedCosts)
  const guestsPerDayNow = convertPeriod(calc.totals.guests, 'month', 'day', calc.factors)

  return (
    <div className="space-y-5">
      <Card>
        <SectionTitle
          icon={<Trophy size={18} />}
          title={t('target.title')}
          subtitle={t('target.subtitle')}
        />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Field label={t('target.want')}>
            <NumberInput
              value={b.targetProfit}
              onChange={(v) => update({ targetProfit: v })}
              min={0}
              suffix={currency}
            />
          </Field>
          <Field label={t('target.forPeriod')}>
            <Select<Period>
              value={b.targetProfitPeriod}
              onChange={(v) => update({ targetProfitPeriod: v })}
              options={periodOptions}
            />
          </Field>
          <div className="sm:col-span-2">
            <span className="label">{t('target.progress')}</span>
            <div className="mt-2 h-3 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
              <div
                className={achieved ? 'h-full bg-emerald-500' : 'h-full bg-brand-500'}
                style={{ width: `${Math.min(100, progress)}%` }}
              />
            </div>
            <div className="mt-2 flex justify-between text-xs text-slate-500 dark:text-slate-400">
              <span className="tnum">
                {t('target.nowValue', { value: money(currentProfit, currency) })}
              </span>
              <span className="tnum">{pct(Math.min(999, progress))}</span>
            </div>
          </div>
        </div>
      </Card>

      {tg.targetMonthly <= 0 ? (
        <Card>
          <p className="text-sm text-slate-500 dark:text-slate-400">{t('target.needPositive')}</p>
        </Card>
      ) : (
        <>
          <div className="rounded-xl border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-900 dark:border-brand-900/50 dark:bg-brand-900/20 dark:text-brand-100">
            {achieved
              ? t('target.achieved', {
                  profit: money(currentProfit, currency),
                  target: money(tg.targetMonthly, currency),
                  surplus: money(currentProfit - tg.targetMonthly, currency),
                })
              : tg.requiredRevenue === null
                ? t('target.unreachable')
                : t('target.gapSentence', {
                    target: money(tg.targetMonthly, currency),
                    required: money(tg.requiredRevenue, currency),
                    delta: signedPct(tg.revenueGapPct),
                    guests: num(tg.guestsGap),
                    perDay: num(safeDiv(tg.guestsGap ?? 0, calc.factors.month)),
                  })}
          </div>

          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Kpi
              label={t('target.requiredRevenue')}
              value={money(
                tg.requiredRevenue === null ? null : tg.requiredRevenue * ratio,
                currency,
              )}
              sub={t('common.forPeriod', { period: periodAcc })}
              tone="brand"
            />
            <Kpi
              label={t('target.requiredGuestsMonth')}
              value={num(tg.requiredGuestsMonth)}
              sub={t('target.nowSub', { value: num(calc.totals.guests) })}
            />
            <Kpi
              label={t('target.requiredGuestsDay')}
              value={num(tg.requiredGuestsDay)}
              sub={t('target.nowSub', { value: num(guestsPerDayNow) })}
            />
            <Kpi
              label={t('target.requiredAvgCheck')}
              value={money(tg.requiredAvgCheck, currency)}
              sub={t('target.nowSub', { value: money(calc.ratios.avgCheck, currency) })}
            />
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <SectionTitle title={t('target.calcTitle')} subtitle={t('target.calcSubtitle')} />
              <StatRow
                label={t('target.targetMonth')}
                value={money(tg.targetMonthly, currency)}
                strong
              />
              <StatRow label={t('target.fixedLoad')} value={money(be.fixedCosts, currency)} />
              <StatRow label={t('target.cmRatio')} value={pct(be.cmRatioPct)} />
              <StatRow
                label={t('target.requiredRevenueRow')}
                value={money(tg.requiredRevenue, currency)}
                strong
                tone="brand"
                hint={t('target.requiredRevenueHint')}
              />
              <StatRow label={t('target.needGuestsMonth')} value={num(tg.requiredGuestsMonth)} />
              <StatRow label={t('target.needGuestsDay')} value={num(tg.requiredGuestsDay)} />
              <StatRow label={t('target.needOrdersMonth')} value={num(tg.requiredOrdersMonth)} />
              <StatRow label={t('target.needOrdersDay')} value={num(tg.requiredOrdersDay)} />
              <StatRow
                label={t('target.diffWithCurrent')}
                value={`${money(tg.revenueGap, currency)} · ${signedPct(tg.revenueGapPct)}`}
                strong
                tone={achieved ? 'good' : 'warn'}
              />
            </Card>

            <Card>
              <SectionTitle
                title={t('target.waysTitle')}
                subtitle={t('target.waysSubtitle', { gap: money(gap, currency) })}
              />
              <Way
                n={1}
                title={t('target.way1')}
                value={
                  achieved
                    ? t('target.alreadyAchieved')
                    : t('target.way1Value', { value: pct(tg.revenueGapPct) })
                }
                detail={t('target.way1Detail', {
                  required: num(tg.requiredGuestsDay),
                  current: num(guestsPerDayNow),
                })}
              />
              <Way
                n={2}
                title={t('target.way2')}
                value={
                  achieved
                    ? t('target.alreadyAchieved')
                    : t('target.way2Value', { value: pct(checkNeededPct) })
                }
                detail={t('target.way2Detail', {
                  required: money(checkNeeded, currency),
                  current: money(calc.ratios.avgCheck, currency),
                })}
              />
              <Way
                n={3}
                title={t('target.way3')}
                value={
                  cmrGapPp === null || cmrGapPp <= 0
                    ? t('target.alreadyAchieved')
                    : t('target.way3Value', {
                        required: pct(requiredCmrPct),
                        delta: num(cmrGapPp, 1),
                      })
                }
                detail={t('target.way3Detail', {
                  current: pct(be.cmRatioPct),
                  gap: money(gap, currency),
                })}
              />
              <Way
                n={4}
                title={t('target.way4')}
                value={
                  gap <= 0
                    ? t('target.alreadyAchieved')
                    : t('target.way4Value', { gap: money(gap, currency) })
                }
                detail={t('target.way4Detail', {
                  share: pct(fixedCutPct),
                  fixed: money(be.fixedCosts, currency),
                })}
              />
            </Card>
          </div>
        </>
      )}
    </div>
  )
}

function Way({
  n,
  title,
  value,
  detail,
}: {
  n: number
  title: string
  value: string
  detail: string
}) {
  return (
    <div className="flex gap-3 border-b border-slate-100 py-3 last:border-0 dark:border-slate-800/70">
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700 dark:bg-brand-900/40 dark:text-brand-300">
        {n}
      </span>
      <div className="min-w-0">
        <div className="flex flex-wrap items-baseline gap-x-2">
          <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{title}</span>
          <span className="tnum text-sm font-semibold text-brand-600 dark:text-brand-400">
            {value}
          </span>
        </div>
        <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{detail}</div>
      </div>
    </div>
  )
}
