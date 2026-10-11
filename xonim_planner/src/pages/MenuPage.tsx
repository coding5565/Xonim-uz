import { Fragment, useMemo, useState } from 'react'
import { ChefHat, ChevronDown, ChevronRight, Copy, FolderPlus, Plus, Tags } from 'lucide-react'
import {
  Card,
  DeleteButton,
  EmptyState,
  Field,
  NumberInput,
  SectionTitle,
  Segmented,
  Select,
  Switch,
  Table,
  TextInput,
  Thead,
  Tr,
} from '@/components/ui'
import { cx } from '@/components/cx'
import { money, num, pct } from '@/core/format'
import { recipeCost, type DishRow } from '@/core/engine'
import { PERIODS, convertPeriod } from '@/core/period'
import { unitsFor } from '@/core/units'
import type { Dish, MeasureUnit, Period } from '@/core/types'
import { PERIOD_ACC_KEY, PERIOD_LABEL_KEY, UNIT_KEY } from '@/i18n/keys'
import { useAppStore } from '@/store/useAppStore'
import { usePeriodView } from '@/store/useCalc'
import { useCurrency, useT } from '@/store/useT'

export default function MenuPage() {
  const t = useT()
  const model = useAppStore((s) => s.model)
  const addDish = useAppStore((s) => s.addDish)
  const updateDish = useAppStore((s) => s.updateDish)
  const removeDish = useAppStore((s) => s.removeDish)
  const duplicateDish = useAppStore((s) => s.duplicateDish)
  const addCategory = useAppStore((s) => s.addCategory)
  const updateCategory = useAppStore((s) => s.updateCategory)
  const removeCategory = useAppStore((s) => s.removeCategory)
  const { calc, period, ratio, currency } = usePeriodView()

  const [expanded, setExpanded] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>('all')
  const [showCats, setShowCats] = useState(false)
  const [newCat, setNewCat] = useState('')

  const periodOptions = PERIODS.map((p) => ({ value: p, label: t(PERIOD_LABEL_KEY[p]) }))
  const periodAcc = t(PERIOD_ACC_KEY[period])

  const rows = useMemo(() => new Map(calc.dishes.map((r) => [r.id, r])), [calc.dishes])
  const catName = (id: string) =>
    model.categories.find((c) => c.id === id)?.name ?? t('common.uncategorized')

  const visible = model.dishes.filter((d) => filter === 'all' || d.categoryId === filter)

  const catOptions = [
    { value: '', label: t('common.uncategorized') },
    ...model.categories.map((c) => ({ value: c.id, label: c.name })),
  ]

  const totalRevenue = visible.reduce((s, d) => s + (rows.get(d.id)?.revenueMonth ?? 0), 0) * ratio
  const totalGross = visible.reduce((s, d) => s + (rows.get(d.id)?.grossMonth ?? 0), 0) * ratio
  const totalCogs = totalRevenue - totalGross

  return (
    <div className="space-y-5">
      {model.salesMode !== 'menu' && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200">
          {t('menu.notActiveMode')}{' '}
          <a href="#sales" className="font-semibold underline">
            {t('menu.switchMode')}
          </a>
        </div>
      )}

      <Card>
        <SectionTitle
          icon={<ChefHat size={18} />}
          title={t('menu.title')}
          subtitle={t('menu.subtitle')}
          right={
            <>
              <button className="btn btn-ghost" onClick={() => setShowCats((v) => !v)}>
                <Tags size={16} /> {t('menu.categories')}
              </button>
              <button className="btn btn-primary" onClick={() => setExpanded(addDish())}>
                <Plus size={16} /> {t('menu.addDish')}
              </button>
            </>
          }
        />

        {showCats && (
          <div className="mb-4 rounded-xl border border-slate-200 p-4 dark:border-slate-800">
            <div className="mb-3 flex flex-wrap gap-2">
              {model.categories.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center gap-1 rounded-lg border border-slate-200 bg-slate-50 py-1 pr-1 pl-2 dark:border-slate-700 dark:bg-slate-800"
                >
                  <input
                    className="w-36 bg-transparent text-sm outline-none"
                    value={c.name}
                    onChange={(e) => updateCategory(c.id, { name: e.target.value })}
                  />
                  <button
                    className="btn btn-danger px-1.5 py-0.5 text-xs"
                    onClick={() => removeCategory(c.id)}
                    title={t('menu.deleteCategory')}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <TextInput
                className="max-w-xs"
                value={newCat}
                onChange={setNewCat}
                placeholder={t('menu.newCategory')}
              />
              <button
                className="btn btn-ghost"
                onClick={() => {
                  if (newCat.trim()) {
                    addCategory(newCat.trim())
                    setNewCat('')
                  }
                }}
              >
                <FolderPlus size={16} /> {t('common.add')}
              </button>
            </div>
          </div>
        )}

        <div className="mb-3 flex flex-wrap items-center gap-2">
          <div className="w-52">
            <Select
              value={filter}
              onChange={setFilter}
              options={[
                { value: 'all', label: t('menu.allCategories') },
                ...model.categories.map((c) => ({ value: c.id, label: c.name })),
              ]}
            />
          </div>
          <span className="text-xs text-slate-500 dark:text-slate-400">
            {t('menu.shown', { count: visible.length, period: periodAcc })}
          </span>
        </div>

        {model.dishes.length === 0 ? (
          <EmptyState
            title={t('menu.emptyTitle')}
            description={t('menu.emptyDesc')}
            action={
              <button className="btn btn-primary" onClick={() => setExpanded(addDish())}>
                <Plus size={16} /> {t('menu.emptyAction')}
              </button>
            }
          />
        ) : (
          <Table className="min-w-[1180px]">
            <Thead>
              <tr>
                <th className="th w-8" />
                <th className="th w-[16%]">{t('menu.col.dish')}</th>
                <th className="th">{t('common.category')}</th>
                <th className="th text-right">{t('menu.col.price')}</th>
                <th className="th text-right">{t('menu.col.cost')}</th>
                <th className="th text-right">{t('kpi.foodCost')}</th>
                <th className="th text-right">{t('kpi.grossMargin')}</th>
                <th className="th text-right">{t('menu.col.sales')}</th>
                <th className="th text-right">{t('menu.col.revenue')}</th>
                <th className="th text-right">{t('menu.col.gross')}</th>
                <th className="th w-28" />
              </tr>
            </Thead>
            <tbody>
              {visible.map((dish) => {
                const row = rows.get(dish.id)
                if (!row) return null
                const isOpen = expanded === dish.id
                return (
                  <Fragment key={dish.id}>
                    <Tr muted={!dish.active}>
                      <td className="td">
                        <button
                          className="cursor-pointer text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                          onClick={() => setExpanded(isOpen ? null : dish.id)}
                          title={t('menu.detailsToggle')}
                        >
                          {isOpen ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                        </button>
                      </td>
                      <td className="td">
                        <TextInput
                          value={dish.name}
                          placeholder={t('menu.dishPlaceholder')}
                          onChange={(v) => updateDish(dish.id, { name: v })}
                        />
                      </td>
                      <td className="td">
                        <Select
                          value={dish.categoryId}
                          options={catOptions}
                          onChange={(v) => updateDish(dish.id, { categoryId: v })}
                        />
                      </td>
                      <td className="td">
                        <NumberInput
                          className="w-28"
                          value={dish.price}
                          min={0}
                          onChange={(v) => updateDish(dish.id, { price: v })}
                        />
                      </td>
                      <td className="td">
                        {dish.costMode === 'manual' ? (
                          <NumberInput
                            className="w-28"
                            value={dish.manualCost}
                            min={0}
                            onChange={(v) => updateDish(dish.id, { manualCost: v })}
                          />
                        ) : (
                          <button
                            className="tnum w-28 cursor-pointer rounded-lg border border-dashed border-brand-400 px-3 py-2 text-right text-sm text-brand-700 dark:text-brand-300"
                            onClick={() => setExpanded(dish.id)}
                            title={t('menu.recipeHint')}
                          >
                            {num(row.cost)}
                          </button>
                        )}
                      </td>
                      <td className="td tnum text-right">
                        <FoodCostCell value={row.foodCostPct} />
                      </td>
                      <td className="td tnum text-right font-medium">{pct(row.marginPct)}</td>
                      <td className="td">
                        <div className="flex justify-end gap-1.5">
                          <NumberInput
                            className="w-24"
                            value={dish.salesQty}
                            min={0}
                            onChange={(v) => updateDish(dish.id, { salesQty: v })}
                          />
                          <Select<Period>
                            className="w-28"
                            value={dish.salesPeriod}
                            options={periodOptions}
                            onChange={(v) => updateDish(dish.id, { salesPeriod: v })}
                          />
                        </div>
                      </td>
                      <td className="td tnum text-right font-medium whitespace-nowrap">
                        {money(row.revenueMonth * ratio, currency)}
                      </td>
                      <td className="td tnum text-right whitespace-nowrap text-emerald-600 dark:text-emerald-400">
                        {money(row.grossMonth * ratio, currency)}
                      </td>
                      <td className="td">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            className="btn btn-ghost px-2 py-1"
                            title={t('menu.duplicate')}
                            onClick={() => duplicateDish(dish.id, t('menu.copyLabel'))}
                          >
                            <Copy size={14} />
                          </button>
                          <DeleteButton
                            title={t('common.delete')}
                            onClick={() => removeDish(dish.id)}
                          />
                        </div>
                      </td>
                    </Tr>
                    {isOpen && (
                      <tr className="bg-slate-50/70 dark:bg-slate-800/30">
                        <td colSpan={11} className="px-3 py-4">
                          <DishDetails dish={dish} row={row} />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-slate-200 dark:border-slate-700">
                <td className="td" colSpan={8}>
                  <span className="font-semibold">
                    {t('common.totalFor', { period: periodAcc })}
                  </span>
                  <span className="ml-2 text-xs text-slate-500">
                    ({filter === 'all' ? t('menu.wholeMenu') : catName(filter)})
                  </span>
                </td>
                <td className="td tnum text-right font-semibold whitespace-nowrap">
                  {money(totalRevenue, currency)}
                </td>
                <td className="td tnum text-right font-semibold whitespace-nowrap text-emerald-600 dark:text-emerald-400">
                  {money(totalGross, currency)}
                </td>
                <td className="td text-right text-xs text-slate-500">
                  {t('menu.foodCostShort', {
                    value: pct((totalCogs / (totalRevenue || 1)) * 100),
                  })}
                </td>
              </tr>
            </tfoot>
          </Table>
        )}
      </Card>
    </div>
  )
}

function FoodCostCell({ value }: { value: number | null }) {
  const tone =
    value === null
      ? 'text-slate-400'
      : value <= 30
        ? 'text-emerald-600 dark:text-emerald-400'
        : value <= 38
          ? 'text-slate-700 dark:text-slate-200'
          : value <= 45
            ? 'text-amber-600 dark:text-amber-400'
            : 'text-rose-600 dark:text-rose-400'
  return <span className={cx('font-medium', tone)}>{pct(value)}</span>
}

/* ─────────────────────── Раскрытая карточка блюда ─────────────────────── */

function DishDetails({ dish, row }: { dish: Dish; row: DishRow }) {
  const t = useT()
  const ingredients = useAppStore((s) => s.model.ingredients)
  const updateDish = useAppStore((s) => s.updateDish)
  const addLine = useAppStore((s) => s.addRecipeLine)
  const updateLine = useAppStore((s) => s.updateRecipeLine)
  const removeLine = useAppStore((s) => s.removeRecipeLine)
  const currency = useCurrency()
  const { calc } = usePeriodView()

  const ingMap = useMemo(() => new Map(ingredients.map((i) => [i.id, i])), [ingredients])
  const rc = useMemo(() => recipeCost(dish, ingMap), [dish, ingMap])
  const lineById = useMemo(() => new Map(rc.lines.map((l) => [l.lineId, l])), [rc.lines])

  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
      {/* Техкарта */}
      <div className="card card-pad">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="font-medium">
              {t('menu.costTitle', { name: dish.name || t('menu.dishPlaceholder') })}
            </div>
            <div className="text-xs text-slate-500 dark:text-slate-400">
              {t('menu.costSubtitle')}
            </div>
          </div>
          <Segmented<'manual' | 'recipe'>
            size="sm"
            value={dish.costMode}
            onChange={(v) => updateDish(dish.id, { costMode: v })}
            options={[
              { value: 'manual', label: t('menu.costManual') },
              { value: 'recipe', label: t('menu.costRecipe') },
            ]}
          />
        </div>

        {dish.costMode === 'manual' ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label={t('menu.portionCost')}>
              <NumberInput
                value={dish.manualCost}
                min={0}
                suffix={currency}
                onChange={(v) => updateDish(dish.id, { manualCost: v })}
              />
            </Field>
            <Field label={t('menu.sellPrice')}>
              <NumberInput
                value={dish.price}
                min={0}
                suffix={currency}
                onChange={(v) => updateDish(dish.id, { price: v })}
              />
            </Field>
            {rc.lines.length > 0 && (
              <div className="text-xs text-slate-500 sm:col-span-2">
                {t('menu.savedRecipe', {
                  count: rc.lines.length,
                  value: money(rc.total, currency),
                })}
              </div>
            )}
          </div>
        ) : ingredients.length === 0 ? (
          <EmptyState
            title={t('menu.noIngredientsTitle')}
            description={t('menu.noIngredientsDesc')}
            action={
              <a href="#ingredients" className="btn btn-primary">
                {t('menu.goIngredients')}
              </a>
            }
          />
        ) : (
          <>
            <Table className="min-w-[520px]">
              <Thead>
                <tr>
                  <th className="th">{t('menu.col.ingredient')}</th>
                  <th className="th text-right">{t('menu.col.qty')}</th>
                  <th className="th text-right">{t('menu.col.lineCost')}</th>
                  <th className="th w-10" />
                </tr>
              </Thead>
              <tbody>
                {dish.recipe.map((line) => {
                  const ing = ingMap.get(line.ingredientId)
                  const allowed = ing ? unitsFor(ing.baseUnit) : (['g'] as MeasureUnit[])
                  const cost = lineById.get(line.id)?.cost ?? 0
                  return (
                    <Tr key={line.id}>
                      <td className="td">
                        <Select
                          value={line.ingredientId}
                          options={ingredients.map((i) => ({
                            value: i.id,
                            label: i.name || t('ing.placeholder'),
                          }))}
                          onChange={(v) => {
                            const next = ingMap.get(v)
                            updateLine(dish.id, line.id, {
                              ingredientId: v,
                              unit: next ? (unitsFor(next.baseUnit)[0] as MeasureUnit) : line.unit,
                            })
                          }}
                        />
                      </td>
                      <td className="td">
                        <div className="flex justify-end gap-1.5">
                          <NumberInput
                            className="w-24"
                            value={line.qty}
                            min={0}
                            onChange={(v) => updateLine(dish.id, line.id, { qty: v })}
                          />
                          <Select<MeasureUnit>
                            className="w-20"
                            value={line.unit}
                            options={allowed.map((u) => ({ value: u, label: t(UNIT_KEY[u]) }))}
                            onChange={(v) => updateLine(dish.id, line.id, { unit: v })}
                          />
                        </div>
                      </td>
                      <td className="td tnum text-right whitespace-nowrap">
                        {money(cost, currency)}
                      </td>
                      <td className="td text-right">
                        <DeleteButton
                          title={t('common.delete')}
                          onClick={() => removeLine(dish.id, line.id)}
                        />
                      </td>
                    </Tr>
                  )
                })}
              </tbody>
              <tfoot>
                <tr className="border-t-2 border-slate-200 dark:border-slate-700">
                  <td className="td font-semibold" colSpan={2}>
                    {t('menu.totalCost')}
                  </td>
                  <td className="td tnum text-right font-semibold whitespace-nowrap">
                    {money(rc.total, currency)}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </Table>
            <button className="btn btn-ghost mt-3" onClick={() => addLine(dish.id)}>
              <Plus size={16} /> {t('menu.addIngredient')}
            </button>
          </>
        )}
      </div>

      {/* Экономика позиции */}
      <div className="card card-pad">
        <div className="mb-3 flex items-center justify-between">
          <div className="font-medium">{t('menu.economics')}</div>
          <Switch
            checked={dish.active}
            onChange={(v) => updateDish(dish.id, { active: v })}
            label={dish.active ? t('menu.inSale') : t('menu.removed')}
          />
        </div>
        <Row label={t('menu.sellPrice')} value={money(row.price, currency)} />
        <Row label={t('menu.col.cost')} value={money(row.cost, currency)} />
        <Row label={t('menu.cmPerUnit')} value={money(row.cmPerUnit, currency)} tone="good" />
        <Row label={t('kpi.foodCost')} value={pct(row.foodCostPct)} />
        <Row label={t('kpi.grossMargin')} value={pct(row.marginPct)} />

        <div className="mt-4 mb-2 text-xs font-semibold tracking-wide text-slate-500 uppercase">
          {t('menu.salesByPeriod')}
        </div>
        {PERIODS.map((p) => (
          <Row
            key={p}
            label={t(PERIOD_LABEL_KEY[p])}
            value={t('menu.portionsAndRevenue', {
              count: convertPeriod(row.qtyMonth, 'month', p, calc.factors),
              value: money(convertPeriod(row.revenueMonth, 'month', p, calc.factors), currency),
            })}
          />
        ))}

        {row.marginPct !== null && row.marginPct < 0 && (
          <div className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-xs text-rose-700 dark:bg-rose-950/40 dark:text-rose-300">
            {t('menu.lossWarning')}
          </div>
        )}
      </div>
    </div>
  )
}

function Row({ label, value, tone }: { label: string; value: string; tone?: 'good' }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-slate-100 py-1.5 text-sm last:border-0 dark:border-slate-800/70">
      <span className="text-slate-600 dark:text-slate-300">{label}</span>
      <span
        className={cx(
          'tnum font-medium whitespace-nowrap',
          tone === 'good' && 'text-emerald-600 dark:text-emerald-400',
        )}
      >
        {value}
      </span>
    </div>
  )
}
