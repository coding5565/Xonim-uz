import { useMemo } from 'react'
import { Plus, ShoppingBasket } from 'lucide-react'
import {
  Card,
  DeleteButton,
  EmptyState,
  NumberInput,
  SectionTitle,
  Select,
  Table,
  Thead,
  TextInput,
  Tr,
} from '@/components/ui'
import { money, num, pct } from '@/core/format'
import { ingredientCost } from '@/core/engine'
import { unitsFor } from '@/core/units'
import type { BaseUnit, MeasureUnit } from '@/core/types'
import { BASE_UNIT_KEY, BASE_UNIT_OPTION_KEY, UNIT_KEY } from '@/i18n/keys'
import { useAppStore } from '@/store/useAppStore'
import { useCurrency, useT } from '@/store/useT'

const BASE_UNITS: BaseUnit[] = ['g', 'ml', 'pc']

export default function IngredientsPage() {
  const t = useT()
  const ingredients = useAppStore((s) => s.model.ingredients)
  const dishes = useAppStore((s) => s.model.dishes)
  const add = useAppStore((s) => s.addIngredient)
  const update = useAppStore((s) => s.updateIngredient)
  const remove = useAppStore((s) => s.removeIngredient)
  const currency = useCurrency()

  const usage = useMemo(() => {
    const map = new Map<string, number>()
    for (const d of dishes) {
      for (const l of d.recipe) map.set(l.ingredientId, (map.get(l.ingredientId) ?? 0) + 1)
    }
    return map
  }, [dishes])

  const baseOptions = BASE_UNITS.map((u) => ({ value: u, label: t(BASE_UNIT_OPTION_KEY[u]) }))

  return (
    <div className="space-y-5">
      <Card>
        <SectionTitle
          icon={<ShoppingBasket size={18} />}
          title={t('ing.title')}
          subtitle={t('ing.subtitle')}
          right={
            <button className="btn btn-primary" onClick={() => add()}>
              <Plus size={16} /> {t('common.add')}
            </button>
          }
        />

        {ingredients.length === 0 ? (
          <EmptyState
            title={t('ing.emptyTitle')}
            description={t('ing.emptyDesc')}
            action={
              <button className="btn btn-primary" onClick={() => add()}>
                <Plus size={16} /> {t('ing.emptyAction')}
              </button>
            }
          />
        ) : (
          <Table className="min-w-[1000px]">
            <Thead>
              <tr>
                <th className="th w-[18%]">{t('ing.col.name')}</th>
                <th className="th">{t('ing.col.baseUnit')}</th>
                <th className="th">{t('ing.col.pack')}</th>
                <th className="th text-right">{t('ing.col.price')}</th>
                <th className="th text-right">{t('ing.col.perBase')}</th>
                <th className="th text-right">{t('ing.col.waste')}</th>
                <th className="th text-right">{t('ing.col.effective')}</th>
                <th className="th text-right">{t('ing.col.dishes')}</th>
                <th className="th" />
              </tr>
            </Thead>
            <tbody>
              {ingredients.map((ing) => {
                const c = ingredientCost(ing)
                const unitLabel = t(BASE_UNIT_KEY[ing.baseUnit])
                const allowed = unitsFor(ing.baseUnit)
                return (
                  <Tr key={ing.id}>
                    <td className="td">
                      <TextInput
                        value={ing.name}
                        placeholder={t('ing.placeholder')}
                        onChange={(v) => update(ing.id, { name: v })}
                      />
                    </td>
                    <td className="td">
                      <Select<BaseUnit>
                        value={ing.baseUnit}
                        options={baseOptions}
                        onChange={(v) =>
                          update(ing.id, {
                            baseUnit: v,
                            purchaseUnit: unitsFor(v)[0] as MeasureUnit,
                          })
                        }
                      />
                    </td>
                    <td className="td">
                      <div className="flex gap-1.5">
                        <NumberInput
                          className="w-24"
                          value={ing.purchaseQty}
                          min={0}
                          onChange={(v) => update(ing.id, { purchaseQty: v })}
                        />
                        <Select<MeasureUnit>
                          className="w-24"
                          value={ing.purchaseUnit}
                          options={allowed.map((u) => ({ value: u, label: t(UNIT_KEY[u]) }))}
                          onChange={(v) => update(ing.id, { purchaseUnit: v })}
                        />
                      </div>
                    </td>
                    <td className="td">
                      <NumberInput
                        value={ing.purchasePrice}
                        min={0}
                        onChange={(v) => update(ing.id, { purchasePrice: v })}
                      />
                    </td>
                    <td className="td tnum text-right whitespace-nowrap text-slate-500 dark:text-slate-400">
                      {money(c.perBase, currency)} / {unitLabel}
                    </td>
                    <td className="td">
                      <NumberInput
                        className="w-20"
                        value={ing.wastePct}
                        min={0}
                        max={99}
                        suffix="%"
                        onChange={(v) => update(ing.id, { wastePct: v })}
                      />
                    </td>
                    <td className="td tnum text-right font-medium whitespace-nowrap">
                      {money(c.effectivePerBase, currency)} / {unitLabel}
                      {ing.wastePct > 0 && c.perBase > 0 && (
                        <div className="text-[11px] font-normal text-amber-600 dark:text-amber-400">
                          {t('ing.wasteNote', {
                            value: pct((c.effectivePerBase / c.perBase - 1) * 100),
                          })}
                        </div>
                      )}
                    </td>
                    <td className="td tnum text-right text-slate-500">
                      {num(usage.get(ing.id) ?? 0)}
                    </td>
                    <td className="td text-right">
                      <DeleteButton
                        title={t('common.delete')}
                        onClick={() => {
                          const used = usage.get(ing.id) ?? 0
                          if (used === 0 || confirm(t('ing.deleteUsed', { count: used }))) {
                            remove(ing.id)
                          }
                        }}
                      />
                    </td>
                  </Tr>
                )
              })}
            </tbody>
          </Table>
        )}
      </Card>

      <Card>
        <SectionTitle title={t('ing.howTitle')} />
        <div className="grid gap-4 text-sm text-slate-600 sm:grid-cols-2 dark:text-slate-300">
          <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800/50">
            <div className="mb-1 font-medium text-slate-800 dark:text-slate-100">
              {t('ing.baseCostTitle')}
            </div>
            <div className="tnum">{t('ing.baseCostFormula')}</div>
            <div className="tnum mt-2 text-xs text-slate-500">
              {t('ing.baseCostExample', { currency })}
            </div>
          </div>
          <div className="rounded-lg bg-slate-50 p-4 dark:bg-slate-800/50">
            <div className="mb-1 font-medium text-slate-800 dark:text-slate-100">
              {t('ing.wasteTitle')}
            </div>
            <div className="tnum">{t('ing.wasteFormula')}</div>
            <div className="tnum mt-2 text-xs text-slate-500">
              {t('ing.wasteExample', { currency })}
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}
