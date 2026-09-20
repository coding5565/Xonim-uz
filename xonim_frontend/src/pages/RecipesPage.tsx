import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  ChefHat, CircleAlert, Coins, PackageCheck, Pencil, Plus, RefreshCw, Trash2,
} from 'lucide-react'
import { api, list, money } from '../api'
import type { Dish, Ingredient, Recipe } from '../types'
import { useI18n } from '../i18n'
import AppModal from '../components/AppModal'

interface FormLine {
  ingredient: number
  quantity: string
  /** Kiritish o'lchovi: mayda (g/ml) yoki asosiy (kg/l). Bazaga doim asosiyda boradi. */
  small: boolean
}

interface RecipeForm {
  dish: number | null
  name: string
  yield_quantity: string
  yield_unit: string
  active: boolean
  lines: FormLine[]
}

interface ItemForm {
  name: string
  unit: string
  minimum: string
}

const emptyItem: ItemForm = { name: '', unit: 'kg', minimum: '0' }
const wholeMoney = (value: string | number) => money(Math.round(Number(value)))
const yieldLabel = (value: string) => Number(value).toLocaleString('uz-UZ', { maximumFractionDigits: 3 })

export default function RecipesPage() {
  const { t, tn } = useI18n()
  const [recipes, setRecipes] = useState<Recipe[]>([])
  const [dishes, setDishes] = useState<Dish[]>([])
  const [ingredients, setIngredients] = useState<Ingredient[]>([])
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [loading, setLoading] = useState(false)
  const [busy, setBusy] = useState(false)
  const [recipeModal, setRecipeModal] = useState(false)
  const [itemModal, setItemModal] = useState(false)
  const [editId, setEditId] = useState<number>()
  const [form, setForm] = useState<RecipeForm>({
    dish: null, name: '', yield_quantity: '1', yield_unit: 'porsiya', active: true, lines: [],
  })
  const [item, setItem] = useState<ItemForm>(emptyItem)

  const updateForm = (patch: Partial<RecipeForm>) => setForm(previous => ({ ...previous, ...patch }))
  const updateItem = (patch: Partial<ItemForm>) => setItem(previous => ({ ...previous, ...patch }))

  /** Returns the reloaded ingredients so callers can act on them without waiting for a render. */
  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const [loadedRecipes, loadedDishes, loadedIngredients] = await Promise.all([
        list<Recipe>('recipes/'),
        list<Dish>('dishes/'),
        list<Ingredient>('ingredients/'),
      ])
      setRecipes(loadedRecipes)
      setDishes(loadedDishes)
      setIngredients(loadedIngredients)
      return loadedIngredients
    } catch (exception) {
      setError((exception as Error).message)
      return []
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const linked = recipes.filter(recipe => recipe.dish).length
  const batchProfit = recipes.reduce(
    (total, recipe) => total + Number(recipe.gross_profit) * Number(recipe.yield_quantity),
    0,
  )

  function openRecipe(recipe?: Recipe) {
    setFormError('')
    setEditId(recipe?.id)
    setForm(recipe
      ? {
        dish: recipe.dish,
        name: recipe.name,
        yield_quantity: String(Number(recipe.yield_quantity)),
        yield_unit: recipe.yield_unit,
        active: recipe.active,
        // Kichik miqdorlar grammda ko'rsatiladi: 0.020 kg o'rniga 20 g.
        lines: recipe.lines.map(line => {
          const item = ingredients.find(row => row.id === line.ingredient)
          const small = item?.unit !== 'dona' && Number(line.quantity) < 1
          return {
            ingredient: line.ingredient,
            quantity: String(Number(line.quantity) * (small ? 1000 : 1)),
            small,
          }
        }),
      }
      : {
        dish: null,
        name: '',
        yield_quantity: '1',
        yield_unit: 'porsiya',
        active: true,
        lines: ingredients.length ? [{ ingredient: ingredients[0].id, quantity: '', small: ingredients[0].unit !== 'dona' }] : [],
      })
    setRecipeModal(true)
  }

  function addLine() {
    if (!ingredients.length) return
    updateForm({ lines: [...form.lines, { ingredient: ingredients[0].id, quantity: '', small: ingredients[0].unit !== 'dona' }] })
  }

  function removeLine(index: number) {
    updateForm({ lines: form.lines.filter((_, position) => position !== index) })
  }

  function updateLine(index: number, patch: Partial<FormLine>) {
    updateForm({ lines: form.lines.map((line, position) => position === index ? { ...line, ...patch } : line) })
  }

  // Forma ichidagi jonli tannarx: masalliq narxi × miqdor.
  const formCost = form.lines.reduce((total, line) => {
    const chosen = ingredients.find(row => row.id === line.ingredient)
    const amount = Number(line.quantity || 0) / (line.small ? 1000 : 1)
    return total + Number(chosen?.unit_cost || 0) * amount
  }, 0)
  const perUnit = Number(form.yield_quantity) ? formCost / Number(form.yield_quantity) : 0
  // Sotuv narxi kiritilmaydi: u menyudagi taomniki. Taom tanlanmagan bo'lsa
  // (masalan, bulyon) foyda ham ko'rsatilmaydi — u sotilmaydi.
  const formPrice = Number(dishes.find(dish => dish.id === form.dish)?.price || 0)
  const formProfit = formPrice - perUnit

  async function saveRecipe(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    try {
      const body = {
        ...form,
        dish: form.dish || null,
        // Narx yuborilmaydi: server uni masalliq narxidan hisoblaydi.
        // Gramm/millilitr bazaga kg/litrga aylantirib boradi.
        lines: form.lines.map(line => ({
          ingredient: line.ingredient,
          quantity: Number(line.quantity) / (line.small ? 1000 : 1),
        })),
      }
      await api(`recipes/${editId ? `${editId}/` : ''}`, {
        method: editId ? 'PATCH' : 'POST',
        body: JSON.stringify(body),
      })
      setRecipeModal(false)
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function saveItem(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    try {
      await api('ingredients/', { method: 'POST', body: JSON.stringify(item) })
      setItemModal(false)
      const loaded = await load()
      // The first ingredient unlocks the recipe form, so give it a line to fill in.
      if (loaded.length && !form.lines.length) {
        setForm(previous => ({
          ...previous,
          lines: [{ ingredient: loaded[0].id, quantity: '', small: loaded[0].unit !== 'dona' }],
        }))
      }
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('TANNARX VA MARJA')}</span>
          <h1>{t('Retseptlar va foyda')}<span className="heading-dot">.</span></h1>
          <p>{t('Har taomning batch tannarxi, porsiya tannarxi va yalpi foydasi.')}</p>
        </div>
        <div className="heading-actions">
          <button
            className="button secondary"
            onClick={() => { setItemModal(true); setFormError(''); setItem(emptyItem) }}
          >
            <Plus size={17} />{t('Mahsulot')}
          </button>
          <button className="button primary" disabled={!ingredients.length} onClick={() => openRecipe()}>
            <Plus size={17} />{t('Retsept')}
          </button>
          <button
            className="button secondary icon-button"
            disabled={loading}
            aria-label={t('Yangilash')}
            onClick={load}
          >
            <RefreshCw size={17} className={loading ? 'spin' : undefined} />
          </button>
        </div>
      </div>
      {error && <p className="alert error">{error}</p>}
      <div className="recipe-summary">
        <article>
          <ChefHat size={21} />
          <div><small>{t('Retseptlar')}</small><strong>{tn('{count} ta', recipes.length)}</strong></div>
        </article>
        <article>
          <PackageCheck size={21} />
          <div><small>{t('Menyuga bog‘langan')}</small><strong>{tn('{count} ta', linked)}</strong></div>
        </article>
        <article>
          <Coins size={21} />
          <div>
            <small>{t('Batchlardagi yalpi foyda')}</small>
            <strong>{wholeMoney(batchProfit)} {t('so‘m')}</strong>
          </div>
        </article>
      </div>
      {loading && !recipes.length && <div className="empty-state">{t('Retseptlar yuklanmoqda…')}</div>}
      {recipes.map(recipe => (
        <section key={recipe.id} className="panel recipe-card">
          <header>
            <div>
              <span className="eyebrow">{recipe.dish_name || t('MENYUGA HALI BOG‘LANMAGAN')}</span>
              <h2>{recipe.name}</h2>
              <p>
                {yieldLabel(recipe.yield_quantity)} {recipe.yield_unit}
                {/* Narx menyudagi taomniki — retseptda alohida narx yo'q. */}
                {recipe.dish
                  ? ` · ${t('menyu narxi')} ${wholeMoney(recipe.selling_price)} ${t('so‘m')}`
                  : ` · ${t('sotilmaydi')}`}
              </p>
            </div>
            <div className="recipe-card-actions">
              <span className={`status ${recipe.dish ? 'paid' : 'open'}`}>
                {recipe.dish ? t('Faol') : t('Draft')}
              </span>
              <button
                className="icon-button"
                aria-label={t('{name} tahrirlash', { name: recipe.name })}
                onClick={() => openRecipe(recipe)}
              >
                <Pencil size={17} />
              </button>
            </div>
          </header>
          <div className="recipe-metrics">
            <div>
              <small>{t('Batch tannarxi')}</small>
              <strong>{wholeMoney(recipe.batch_cost)} {t('so‘m')}</strong>
            </div>
            <div>
              <small>{t('1 {unit} tannarxi', { unit: recipe.yield_unit })}</small>
              <strong>{wholeMoney(recipe.unit_cost)} {t('so‘m')}</strong>
            </div>
            <div>
              <small>{t('1 birlik yalpi foyda')}</small>
              <strong className="profit">{wholeMoney(recipe.gross_profit)} {t('so‘m')}</strong>
            </div>
          </div>
          <div className="table-wrap">
            <table>
              <thead><tr><th>{t('MASALLIQ')}</th><th>{t('MIQDOR')}</th><th>{t('BATCH XARAJATI')}</th></tr></thead>
              <tbody>
                {recipe.lines.map(line => (
                  <tr key={line.id}>
                    <td><strong>{line.ingredient_name}</strong></td>
                    <td>{yieldLabel(line.quantity)} {t(line.unit)}</td>
                    <td className="number">{wholeMoney(line.batch_cost)} {t('so‘m')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
      {recipes.some(recipe => !recipe.dish) && (
        <p className="data-note">
          <CircleAlert size={15} />
          {t('Bulyon kalkulyatsiyasi saqlandi, ammo menyuda Bulyon taomi yo‘q. Uni menyuga qo‘shgach retseptga bog‘lanadi.')}
        </p>
      )}
      <p className="data-note">
        {t('Yalpi foyda sotuv narxidan retsept tannarxi ayirilgan qiymat. Ijara, oylik va umumiy xarajatlar sof foydada alohida hisoblanadi.')}
      </p>

      <AppModal
        open={recipeModal}
        title={editId ? t('Retseptni tahrirlash') : t('Yangi retsept')}
        onClose={() => { if (!busy) setRecipeModal(false) }}
      >
        <form onSubmit={saveRecipe}>
          <fieldset disabled={busy}>
            <div className="form-row">
              <label>
                {t('Retsept nomi')}
                <input
                  value={form.name}
                  onChange={event => updateForm({ name: event.target.value })}
                  required
                  maxLength={120}
                  placeholder={t('Masalan, Mastava')}
                />
              </label>
              <label>
                {t('Menyu taomi')}
                <select
                  value={form.dish ?? ''}
                  onChange={event => updateForm({ dish: event.target.value ? Number(event.target.value) : null })}
                >
                  <option value="">{t('Hali bog‘lanmagan')}</option>
                  {dishes.map(dish => <option key={dish.id} value={dish.id}>{dish.name}</option>)}
                </select>
              </label>
            </div>
            <div className="form-row">
              <label>
                {t('Batch chiqimi')}
                <input
                  value={form.yield_quantity}
                  onChange={event => updateForm({ yield_quantity: event.target.value })}
                  required
                  type="number"
                  min="0.001"
                  step="0.001"
                />
              </label>
              <label>
                {t('Birlik')}
                <select value={form.yield_unit} onChange={event => updateForm({ yield_unit: event.target.value })}>
                  <option value="dona">{t('dona')}</option>
                  <option value="porsiya">{tn('porsiya', 1)}</option>
                </select>
              </label>
            </div>
            <div className="recipe-form-lines">
              <div className="recipe-line-head">
                <div>
                  <strong>
                    {t('{count} {unit} uchun masalliqlar', {
                      count: Number(form.yield_quantity), unit: form.yield_unit,
                    })}
                  </strong>
                  <small>{t('Narx masalliq kartasidan olinadi — bu yerda faqat miqdor yoziladi')}</small>
                </div>
                <button type="button" className="text-link" onClick={addLine}><Plus size={15} />{t('Qator')}</button>
              </div>
              {form.lines.map((line, index) => (
                <div key={index} className="recipe-form-line">
                  <select
                    value={line.ingredient}
                    onChange={event => {
                      const next = Number(event.target.value)
                      const item = ingredients.find(row => row.id === next)
                      updateLine(index, { ingredient: next, small: item?.unit !== 'dona' && line.small })
                    }}
                    required
                  >
                    {ingredients.map(row => (
                      <option key={row.id} value={row.id}>{row.name} · {t(row.unit)}</option>
                    ))}
                  </select>
                  <div className="amount-field">
                    <input
                      value={line.quantity}
                      onChange={event => updateLine(index, { quantity: event.target.value })}
                      required
                      type="number"
                      min={line.small ? '1' : '0.001'}
                      step={line.small ? '1' : '0.001'}
                      placeholder={t('Miqdor')}
                    />
                    <select
                      value={line.small ? 'small' : 'base'}
                      onChange={event => updateLine(index, { small: event.target.value === 'small' })}
                      aria-label={t('O‘lchov birligi')}
                    >
                      {(() => {
                        const item = ingredients.find(row => row.id === line.ingredient)
                        if (item?.unit === 'dona') return <option value="base">dona</option>
                        const base = item?.unit === 'l' ? 'l' : 'kg'
                        const small = item?.unit === 'l' ? 'ml' : 'g'
                        return <>
                          <option value="small">{small}</option>
                          <option value="base">{base}</option>
                        </>
                      })()}
                    </select>
                  </div>
                  <span className="line-cost">
                    {(() => {
                      const chosen = ingredients.find(row => row.id === line.ingredient)
                      const price = Number(chosen?.unit_cost || 0)
                      if (!price) return <em>{t('narx kiritilmagan')}</em>
                      const amount = Number(line.quantity || 0) / (line.small ? 1000 : 1)
                      return <>{wholeMoney(price * amount)} <small>{t('so‘m')}</small></>
                    })()}
                  </span>
                  <button
                    type="button"
                    className="icon-button"
                    disabled={form.lines.length === 1}
                    aria-label={t('Qatorni o‘chirish')}
                    onClick={() => removeLine(index)}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
              <div className="recipe-line-total">
                <span>
                  {Number(form.yield_quantity) === 1 ? t('1 ta uchun tannarx') : t('Jami tannarx')}
                </span>
                <strong>{wholeMoney(formCost)} {t('so‘m')}</strong>
                {Number(form.yield_quantity) > 1 && (
                  <small>
                    1 {form.yield_unit} = {wholeMoney(formCost / Number(form.yield_quantity))} {t('so‘m')}
                  </small>
                )}
                {formPrice > 0 && (
                  <small className={formProfit < 0 ? 'owed' : undefined}>
                    {t('Foyda')}: {wholeMoney(formProfit)} {t('so‘m')}{' '}
                    ({t('narxi {price} so‘m', { price: wholeMoney(formPrice) })})
                  </small>
                )}
              </div>
            </div>
            <label className="checkbox">
              <input type="checkbox" checked={form.active} onChange={event => updateForm({ active: event.target.checked })} />
              {t('Retsept faol')}
            </label>
          </fieldset>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy || !form.lines.length}>
            {busy ? t('Saqlanmoqda…') : t('Retseptni saqlash')}
          </button>
        </form>
      </AppModal>

      <AppModal open={itemModal} title={t('Yangi mahsulot')} onClose={() => { if (!busy) setItemModal(false) }}>
        <form onSubmit={saveItem}>
          <fieldset disabled={busy}>
            <label>
              {t('Mahsulot nomi')}
              <input
                value={item.name}
                onChange={event => updateItem({ name: event.target.value })}
                required
                maxLength={100}
                placeholder={t('Masalan, Pomidor')}
              />
            </label>
            <div className="form-row">
              <label>
                {t('Birlik')}
                <select value={item.unit} onChange={event => updateItem({ unit: event.target.value })}>
                  <option>kg</option><option>l</option><option>dona</option>
                </select>
              </label>
              <label>
                {t('Minimal qoldiq')}
                <input
                  value={item.minimum}
                  onChange={event => updateItem({ minimum: event.target.value })}
                  required
                  type="number"
                  min="0"
                  step="0.001"
                />
              </label>
            </div>
          </fieldset>
          <p className="alert">
            {t('Mahsulot qo‘shilgach uning boshlang‘ich qoldig‘ini «Ombor va sarf» bo‘limidagi Kirim orqali kiriting.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('Mahsulotni saqlash')}
          </button>
        </form>
      </AppModal>
    </>
  )
}
