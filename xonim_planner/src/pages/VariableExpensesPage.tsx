import { useMemo } from 'react'
import { Percent, Plus } from 'lucide-react'
import {
  Badge,
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
import { varExpenseBehavior } from '@/core/engine'
import { PERIODS, convertPeriod } from '@/core/period'
import type { CostBehavior, Period, VarExpenseType } from '@/core/types'
import {
  BEHAVIOR_KEY,
  PERIOD_ACC_KEY,
  PERIOD_LABEL_KEY,
  PERIOD_LOWER_KEY,
  VAR_TYPE_KEY,
} from '@/i18n/keys'
import { useAppStore } from '@/store/useAppStore'
import { usePeriodView } from '@/store/useCalc'
import { useT } from '@/store/useT'

const TYPES: VarExpenseType[] = ['pct_revenue', 'per_order', 'per_guest', 'fixed_period']
type BehaviorChoice = CostBehavior | 'auto'

export default function VariableExpensesPage() {
  const t = useT()
  const items = useAppStore((s) => s.model.variableExpenses)
  const add = useAppStore((s) => s.addVariableExpense)
  const update = useAppStore((s) => s.updateVariableExpense)
  const remove = useAppStore((s) => s.removeVariableExpense)
  const { calc, totals, period, currency } = usePeriodView()

  const periodOptions = PERIODS.map((p) => ({ value: p, label: t(PERIOD_LABEL_KEY[p]) }))
  const periodAcc = t(PERIOD_ACC_KEY[period])
  const periodLower = t(PERIOD_LOWER_KEY[period])
  const typeOptions = TYPES.map((v) => ({ value: v, label: t(VAR_TYPE_KEY[v]) }))
  const behaviorOptions: Array<{ value: BehaviorChoice; label: string }> = [
    { value: 'auto', label: t('behavior.auto') },
    { value: 'variable', label: t(BEHAVIOR_KEY.variable) },
    { value: 'fixed', label: t(BEHAVIOR_KEY.fixed) },
  ]

  const monthlyById = useMemo(
    () => new Map(calc.variableItems.map((i) => [i.id, i.monthly])),
    [calc.variableItems],
  )

  return (
    <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-4">
        <Kpi
          label={t('var.kpi', { period: periodLower })}
          value={money(totals.variableExpenses, currency)}
          tone="brand"
        />
        <Kpi label={t('var.shareOfRevenue')} value={pct(calc.ratios.variablePct)} />
        <Kpi
          label={t('var.growsWithVolume')}
          value={money(totals.variableExpensesVariable, currency)}
          sub={t('var.growsSub')}
        />
        <Kpi
          label={t('var.behavesFixed')}
          value={money(totals.variableExpensesFixed, currency)}
          sub={t('var.behavesFixedSub')}
        />
      </div>

      <Card>
        <SectionTitle
          icon={<Percent size={18} />}
          title={t('var.title')}
          subtitle={t('var.subtitle')}
          right={
            <button className="btn btn-primary" onClick={() => add()}>
              <Plus size={16} /> {t('var.addExpense')}
            </button>
          }
        />

        {items.length === 0 ? (
          <EmptyState
            title={t('var.emptyTitle')}
            description={t('var.emptyDesc')}
            action={
              <button className="btn btn-primary" onClick={() => add()}>
                <Plus size={16} /> {t('var.emptyAction')}
              </button>
            }
          />
        ) : (
          <Table className="min-w-[1080px]">
            <Thead>
              <tr>
                <th className="th w-[20%]">{t('common.name')}</th>
                <th className="th">{t('var.col.method')}</th>
                <th className="th text-right">{t('var.col.value')}</th>
                <th className="th">{t('var.col.base')}</th>
                <th className="th">{t('common.behavior')}</th>
                <th className="th text-right">{t('common.forPeriod', { period: periodAcc })}</th>
                <th className="th text-right">{t('common.shareOfRevenue')}</th>
                <th className="th text-center">{t('common.active')}</th>
                <th className="th w-10" />
              </tr>
            </Thead>
            <tbody>
              {items.map((x) => {
                const monthly = monthlyById.get(x.id) ?? 0
                const behavior = varExpenseBehavior(x)
                return (
                  <Tr key={x.id} muted={!x.active}>
                    <td className="td">
                      <TextInput
                        value={x.name}
                        placeholder={t('var.namePlaceholder')}
                        onChange={(v) => update(x.id, { name: v })}
                      />
                    </td>
                    <td className="td">
                      <Select<VarExpenseType>
                        className="w-44"
                        value={x.type}
                        options={typeOptions}
                        onChange={(v) => update(x.id, { type: v })}
                      />
                    </td>
                    <td className="td">
                      <NumberInput
                        className="w-32"
                        value={x.value}
                        min={0}
                        suffix={x.type === 'pct_revenue' ? '%' : undefined}
                        onChange={(v) => update(x.id, { value: v })}
                      />
                    </td>
                    <td className="td">
                      {x.type === 'pct_revenue' ? (
                        <div className="flex items-center gap-1.5">
                          <NumberInput
                            className="w-20"
                            value={x.baseSharePct}
                            min={0}
                            max={100}
                            suffix="%"
                            onChange={(v) => update(x.id, { baseSharePct: v })}
                          />
                          <span className="text-xs whitespace-nowrap text-slate-500">
                            {t('var.baseRevenue')}
                          </span>
                        </div>
                      ) : x.type === 'fixed_period' ? (
                        <Select<Period>
                          className="w-28"
                          value={x.period}
                          options={periodOptions}
                          onChange={(v) => update(x.id, { period: v })}
                        />
                      ) : (
                        <span className="text-xs text-slate-500">
                          {x.type === 'per_order'
                            ? t('var.timesOrders', { count: calc.totals.orders })
                            : t('var.timesGuests', { count: calc.totals.guests })}
                        </span>
                      )}
                    </td>
                    <td className="td">
                      <Select<BehaviorChoice>
                        className="w-32"
                        value={x.behavior ?? 'auto'}
                        options={behaviorOptions}
                        onChange={(v) => update(x.id, { behavior: v === 'auto' ? null : v })}
                      />
                      {x.behavior === null && (
                        <div className="mt-1">
                          <Badge tone={behavior === 'variable' ? 'green' : 'slate'}>
                            {behavior === 'variable'
                              ? t('behavior.variableShort')
                              : t('behavior.fixedShort')}
                          </Badge>
                        </div>
                      )}
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
                <td className="td font-semibold" colSpan={5}>
                  {t('common.totalFor', { period: periodAcc })}
                </td>
                <td className="td tnum text-right font-semibold whitespace-nowrap">
                  {money(totals.variableExpenses, currency)}
                </td>
                <td className="td tnum text-right font-semibold">{pct(calc.ratios.variablePct)}</td>
                <td colSpan={2} />
              </tr>
            </tfoot>
          </Table>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <SectionTitle title={t('var.howTitle')} />
          <StatRow
            label={t('var.type.pctRevenue')}
            value={t('var.howPct')}
            hint={t('var.howPctHint')}
          />
          <StatRow
            label={t('var.type.perOrder')}
            value={t('var.howOrder', { count: calc.totals.orders })}
          />
          <StatRow
            label={t('var.type.perGuest')}
            value={t('var.howGuest', { count: calc.totals.guests })}
          />
          <StatRow label={t('var.type.fixedPeriod')} value={t('var.howFixed')} />
        </Card>

        <Card>
          <SectionTitle title={t('var.behaviorTitle')} />
          <p className="text-sm text-slate-600 dark:text-slate-300">{t('var.behaviorText')}</p>
          <div className="mt-3 space-y-2">
            <StatRow
              label={t('var.inVariable')}
              value={money(calc.totals.variableExpensesVariable, currency)}
            />
            <StatRow
              label={t('var.inFixed')}
              value={money(calc.totals.variableExpensesFixed, currency)}
            />
          </div>
        </Card>
      </div>
    </div>
  )
}
