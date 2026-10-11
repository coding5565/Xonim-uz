import { Plus, Users } from 'lucide-react'
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
import { money, num, pct } from '@/core/format'
import { employeeMonthlyPay } from '@/core/engine'
import { PERIODS, convertPeriod } from '@/core/period'
import type { CostBehavior, PayFrequency } from '@/core/types'
import { BEHAVIOR_KEY, PAY_FREQUENCY_KEY, PERIOD_LABEL_KEY } from '@/i18n/keys'
import { useAppStore } from '@/store/useAppStore'
import { usePeriodView } from '@/store/useCalc'
import { useT } from '@/store/useT'

const FREQS: PayFrequency[] = ['day', 'week', 'month']
const BEHAVIORS: CostBehavior[] = ['fixed', 'variable']

export default function StaffPage() {
  const t = useT()
  const employees = useAppStore((s) => s.model.employees)
  const add = useAppStore((s) => s.addEmployee)
  const update = useAppStore((s) => s.updateEmployee)
  const remove = useAppStore((s) => s.removeEmployee)
  const { calc, totals, currency } = usePeriodView()

  const f = calc.factors
  const payrollMonth = calc.totals.payroll
  const freqOptions = FREQS.map((v) => ({ value: v, label: t(PAY_FREQUENCY_KEY[v]) }))
  const behaviorOptions = BEHAVIORS.map((v) => ({ value: v, label: t(BEHAVIOR_KEY[v]) }))

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Kpi
          label={t('staff.payrollDay')}
          value={money(convertPeriod(payrollMonth, 'month', 'day', f), currency)}
        />
        <Kpi
          label={t('staff.payrollWeek')}
          value={money(convertPeriod(payrollMonth, 'month', 'week', f), currency)}
        />
        <Kpi label={t('staff.payrollMonth')} value={money(payrollMonth, currency)} tone="brand" />
        <Kpi
          label={t('staff.payrollYear')}
          value={money(convertPeriod(payrollMonth, 'month', 'year', f), currency)}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-[1fr_320px]">
        <Card>
          <SectionTitle
            icon={<Users size={18} />}
            title={t('staff.title')}
            subtitle={t('staff.subtitle')}
            right={
              <button className="btn btn-primary" onClick={() => add()}>
                <Plus size={16} /> {t('staff.addEmployee')}
              </button>
            }
          />

          {employees.length === 0 ? (
            <EmptyState
              title={t('staff.emptyTitle')}
              description={t('staff.emptyDesc')}
              action={
                <button className="btn btn-primary" onClick={() => add()}>
                  <Plus size={16} /> {t('staff.emptyAction')}
                </button>
              }
            />
          ) : (
            <Table className="min-w-[980px]">
              <Thead>
                <tr>
                  <th className="th w-[18%]">{t('staff.col.name')}</th>
                  <th className="th">{t('staff.col.role')}</th>
                  <th className="th text-right">{t('staff.col.pay')}</th>
                  <th className="th">{t('common.frequency')}</th>
                  <th className="th text-right">{t('staff.col.workDays')}</th>
                  <th className="th">{t('common.behavior')}</th>
                  <th className="th text-right">{t('staff.col.monthly')}</th>
                  <th className="th text-center">{t('common.active')}</th>
                  <th className="th w-10" />
                </tr>
              </Thead>
              <tbody>
                {employees.map((e) => {
                  const monthly = employeeMonthlyPay(e, f)
                  return (
                    <Tr key={e.id} muted={!e.active}>
                      <td className="td">
                        <TextInput
                          value={e.name}
                          placeholder={t('staff.namePlaceholder')}
                          onChange={(v) => update(e.id, { name: v })}
                        />
                      </td>
                      <td className="td">
                        <TextInput
                          value={e.role}
                          placeholder={t('staff.rolePlaceholder')}
                          onChange={(v) => update(e.id, { role: v })}
                        />
                      </td>
                      <td className="td">
                        <NumberInput
                          className="w-32"
                          value={e.pay}
                          min={0}
                          onChange={(v) => update(e.id, { pay: v })}
                        />
                      </td>
                      <td className="td">
                        <Select<PayFrequency>
                          className="w-32"
                          value={e.payFrequency}
                          options={freqOptions}
                          onChange={(v) => update(e.id, { payFrequency: v })}
                        />
                      </td>
                      <td className="td">
                        <NumberInput
                          className="w-20"
                          value={e.workDaysPerMonth}
                          min={0}
                          max={31}
                          disabled={e.payFrequency === 'month'}
                          onChange={(v) => update(e.id, { workDaysPerMonth: v })}
                        />
                      </td>
                      <td className="td">
                        <Select<CostBehavior>
                          className="w-36"
                          value={e.behavior}
                          options={behaviorOptions}
                          onChange={(v) => update(e.id, { behavior: v })}
                        />
                      </td>
                      <td className="td tnum text-right font-medium whitespace-nowrap">
                        {money(monthly, currency)}
                      </td>
                      <td className="td text-center">
                        <Switch checked={e.active} onChange={(v) => update(e.id, { active: v })} />
                      </td>
                      <td className="td text-right">
                        <DeleteButton title={t('common.delete')} onClick={() => remove(e.id)} />
                      </td>
                    </Tr>
                  )
                })}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-200 dark:border-slate-700">
                  <td className="td font-semibold" colSpan={6}>
                    {t('staff.totalPayroll')}
                  </td>
                  <td className="td tnum text-right font-semibold whitespace-nowrap">
                    {money(payrollMonth, currency)}
                  </td>
                  <td colSpan={2} />
                </tr>
              </tfoot>
            </Table>
          )}
        </Card>

        <div className="space-y-5">
          <Card>
            <SectionTitle title={t('staff.laborTitle')} subtitle={t('staff.laborSubtitle')} />
            <div className="tnum mb-3 text-3xl font-semibold text-brand-600 dark:text-brand-400">
              {pct(calc.ratios.laborCostPct)}
            </div>
            <StatRow label={t('staff.payrollMonthRow')} value={money(payrollMonth, currency)} />
            <StatRow
              label={t('staff.revenueMonthRow')}
              value={money(calc.totals.revenue, currency)}
            />
            <StatRow
              label={t('staff.primeRow')}
              value={`${money(calc.totals.primeCost, currency)} · ${pct(calc.ratios.primeCostPct)}`}
              strong
            />
            <div className="mt-3 text-xs text-slate-500 dark:text-slate-400">
              {t('staff.benchmark')}
            </div>
          </Card>

          <Card>
            <SectionTitle title={t('staff.splitTitle')} subtitle={t('staff.splitSubtitle')} />
            <StatRow
              label={t('staff.fixedPayroll')}
              value={money(calc.totals.payrollFixed, currency)}
            />
            <StatRow
              label={t('staff.variablePayroll')}
              value={money(calc.totals.payrollVariable, currency)}
            />
            <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600 dark:bg-slate-800/50 dark:text-slate-300">
              {t('staff.splitNote')}
            </div>
          </Card>

          <Card>
            <SectionTitle title={t('staff.byPeriod')} />
            {PERIODS.map((p) => (
              <StatRow
                key={p}
                label={t(PERIOD_LABEL_KEY[p])}
                value={money(convertPeriod(payrollMonth, 'month', p, f), currency)}
                strong={p === 'month'}
              />
            ))}
            <StatRow
              label={t('staff.activeCount')}
              value={num(employees.filter((e) => e.active).length)}
            />
            <StatRow
              label={t('staff.revenuePerEmployee')}
              value={money(
                totals.revenue / Math.max(1, employees.filter((e) => e.active).length),
                currency,
              )}
            />
          </Card>
        </div>
      </div>
    </div>
  )
}
