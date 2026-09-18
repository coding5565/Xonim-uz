import { useCallback, useEffect, useState, type ChangeEvent, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Eye, ImagePlus, Layers3, Pencil, Plus, Search, Trash2 } from 'lucide-react'
import { api, list, money } from '../api'
import type { Category, Dish, Ingredient, Recipe, Station } from '../types'
import AppModal from '../components/AppModal'
import DishArt from '../components/DishArt'

interface DishForm {
  name: string
  category: number
  description: string
  price: string
  portion: string
  available: boolean
  archived: boolean
}

const emptyDish: DishForm = {
  name: '', category: 0, description: '', price: '', portion: '1 porsiya', available: true, archived: false,
}

export default function CatalogPage() {
  const [categories, setCategories] = useState<Category[]>([])
  const [dishes, setDishes] = useState<Dish[]>([])
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState(0)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [modal, setModal] = useState<'dish' | 'category' | ''>('')
  const [editId, setEditId] = useState<number>()
  const [imageFile, setImageFile] = useState<File>()
  const [form, setForm] = useState<DishForm>(emptyDish)
  const [ingredients, setIngredients] = useState<Ingredient[]>([])
  const [recipes, setRecipes] = useState<Recipe[]>([])
  // 1 porsiya uchun masalliqlar. Miqdor mayda o'lchovda (g/ml) kiritiladi.
  const [recipeLines, setRecipeLines] = useState<{ ingredient: number; quantity: string; small: boolean }[]>([])
  const [categoryName, setCategoryName] = useState('')
  const [categoryStation, setCategoryStation] = useState<Station>('kitchen')

  const update = (patch: Partial<DishForm>) => setForm(previous => ({ ...previous, ...patch }))

  const load = useCallback(async () => {
    try {
      const [loadedCategories, loadedDishes, loadedIngredients, loadedRecipes] = await Promise.all([
        list<Category>('categories/'),
        list<Dish>('dishes/'),
        list<Ingredient>('ingredients/'),
        list<Recipe>('recipes/'),
      ])
      setCategories(loadedCategories)
      setDishes(loadedDishes)
      setIngredients(loadedIngredients)
      setRecipes(loadedRecipes)
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const filtered = dishes.filter(dish =>
    !dish.archived &&
    (!category || dish.category === category) &&
    dish.name.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
  )

  function openDish(dish?: Dish) {
    setFormError('')
    setEditId(dish?.id)
    setImageFile(undefined)
    setForm(dish
      ? {
        name: dish.name, category: dish.category, description: dish.description,
        price: dish.price, portion: dish.portion, available: dish.available, archived: dish.archived,
      }
      : { ...emptyDish, category: category || categories[0]?.id || 0 })
    // Taomning retsepti bo'lsa formaga tortiladi, bo'lmasa bo'sh qator beriladi.
    const recipe = dish ? recipes.find(item => item.dish === dish.id) : undefined
    setRecipeLines(recipe
      ? recipe.lines.map(line => {
        const item = ingredients.find(row => row.id === line.ingredient)
        const small = item?.unit !== 'dona' && Number(line.quantity) < 1
        return {
          ingredient: line.ingredient,
          quantity: String(Number(line.quantity) * (small ? 1000 : 1)),
          small,
        }
      })
      : [])
    setModal('dish')
  }

  async function saveDish(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    try {
      const body = new FormData()
      // Porsiya bo'sh qoldirilsa server rad qiladi, shuning uchun standart qiymat qo'yiladi.
      const payload = { ...form, portion: form.portion.trim() || '1 porsiya' }
      Object.entries(payload).forEach(([field, value]) => body.append(field, String(value)))
      if (imageFile) body.append('image', imageFile)
      const dish = await api<Dish>(`dishes/${editId ? `${editId}/` : ''}`, { method: editId ? 'PATCH' : 'POST', body })
      await saveRecipeFor(dish)
      setModal('')
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function addRecipeLine() {
    if (!ingredients.length) return
    const first = ingredients[0]
    setRecipeLines([...recipeLines, { ingredient: first.id, quantity: '', small: first.unit !== 'dona' }])
  }

  function updateRecipeLine(index: number, patch: Partial<(typeof recipeLines)[number]>) {
    setRecipeLines(recipeLines.map((line, spot) => spot === index ? { ...line, ...patch } : line))
  }

  // 1 porsiya tannarxi: masalliq narxi × miqdor.
  const recipeCost = recipeLines.reduce((total, line) => {
    const item = ingredients.find(row => row.id === line.ingredient)
    const amount = Number(line.quantity || 0) / (line.small ? 1000 : 1)
    return total + Number(item?.unit_cost || 0) * amount
  }, 0)

  /** Taom saqlangandan keyin uning retseptini yozadi yoki yangilaydi. */
  async function saveRecipeFor(dish: Dish) {
    const filled = recipeLines.filter(line => line.ingredient && Number(line.quantity) > 0)
    const existing = recipes.find(item => item.dish === dish.id)
    if (!filled.length) {
      // Retsept bo'sh qoldirilsa mavjudiga tegilmaydi — tasodifan o'chib
      // ketmasligi uchun; olib tashlash «Retsept va foyda» bo'limida.
      return
    }
    const body = {
      dish: dish.id,
      name: dish.name,
      yield_quantity: 1,
      yield_unit: 'porsiya',
      selling_price: Number(dish.price),
      active: true,
      lines: filled.map(line => ({
        ingredient: line.ingredient,
        quantity: Number(line.quantity) / (line.small ? 1000 : 1),
      })),
    }
    await api(`recipes/${existing ? `${existing.id}/` : ''}`, {
      method: existing ? 'PATCH' : 'POST',
      body: JSON.stringify(body),
    })
  }

  async function saveCategory(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    try {
      await api('categories/', {
        method: 'POST',
        body: JSON.stringify({ name: categoryName, position: categories.length, station: categoryStation }),
      })
      setModal('')
      setCategoryName('')
      setCategoryStation('kitchen')
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    setImageFile(event.target.files?.[0])
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">TAOMLARINGIZ KOLLEKSIYASI</span>
          <h1>Menyu boshqaruvi<span className="heading-dot">.</span></h1>
          <p>Kategoriyalar, taomlar va narxlar — bir joyda.</p>
        </div>
        <div className="heading-actions">
          <button className="button secondary" onClick={() => { setModal('category'); setFormError('') }}>
            <Layers3 size={17} />Kategoriya
          </button>
          <button className="button primary" onClick={() => openDish()}><Plus size={18} />Taom qo‘shish</button>
        </div>
      </div>
      {error && <p className="alert error">{error}</p>}
      <div className="catalog-toolbar">
        <div className="tabs">
          <button className={category === 0 ? 'selected' : undefined} onClick={() => setCategory(0)}>
            Barchasi <span>{dishes.filter(dish => !dish.archived).length}</span>
          </button>
          {categories.map(item => (
            <button
              key={item.id}
              className={category === item.id ? 'selected' : undefined}
              onClick={() => setCategory(item.id)}
            >
              {item.name}
            </button>
          ))}
        </div>
        <div className="search-field">
          <Search size={18} />
          <input
            value={query}
            onChange={event => setQuery(event.target.value)}
            placeholder="Taomni qidirish…"
            aria-label="Taomni qidirish"
          />
        </div>
      </div>
      {loading ? (
        <div className="empty-state">Menyu yuklanmoqda…</div>
      ) : (
        <div className="dish-grid">
          {filtered.map(dish => (
            <article key={dish.id} className="dish-card">
              <div className="dish-image-wrap">
                <DishArt name={dish.name} category={dish.category_name} image={dish.image} />
                <span className={`dish-state${dish.available ? '' : ' unavailable'}`}>
                  <i />{dish.available ? 'Mavjud' : 'Tugagan'}
                </span>
                <button className="edit-dish" aria-label={`${dish.name} tahrirlash`} onClick={() => openDish(dish)}>
                  <Pencil size={16} />
                </button>
              </div>
              <div className="dish-details">
                <span className="eyebrow">{dish.category_name}</span>
                <h3>{dish.name}</h3>
                <p>{dish.description || 'Tavsif kiritilmagan'}</p>
                <footer>
                  <strong>{money(dish.price)} <small>so‘m</small></strong>
                  <span>{dish.portion}</span>
                </footer>
              </div>
            </article>
          ))}
        </div>
      )}
      {!loading && !filtered.length && (
        <div className="empty-state">
          <Search size={32} />
          <h3>Taom topilmadi</h3>
          <p>Qidiruvni o‘zgartiring yoki yangi taom qo‘shing.</p>
        </div>
      )}
      <div className="inline-tip">
        <Eye size={18} />
        <span>Faol taomlar kassir panelida va mijoz menyusida avtomatik ko‘rinadi.</span>
        <Link to="/menu" target="_blank">Menyuni ko‘rish →</Link>
      </div>

      <AppModal open={modal === 'category'} title="Yangi kategoriya" onClose={() => { if (!busy) setModal('') }}>
        <form onSubmit={saveCategory}>
          <label>
            Kategoriya nomi
            <input
              value={categoryName}
              onChange={event => setCategoryName(event.target.value)}
              required
              maxLength={100}
              placeholder="Masalan, Milliy taomlar"
            />
          </label>
          <label>
            Talon qaysi printerdan chiqsin?
            <select value={categoryStation} onChange={event => setCategoryStation(event.target.value as Station)}>
              <option value="kitchen">Oshxona — pishiriladi</option>
              <option value="counter">Kassa — tayyor (suv, ichimlik)</option>
            </select>
          </label>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? 'Saqlanmoqda…' : 'Kategoriyani saqlash'}
          </button>
        </form>
      </AppModal>

      <AppModal
        open={modal === 'dish'}
        title={editId ? 'Taomni tahrirlash' : 'Yangi taom'}
        onClose={() => { if (!busy) setModal('') }}
      >
        <form onSubmit={saveDish}>
          <div className="form-row">
            <label>
              Taom nomi
              <input
                value={form.name}
                onChange={event => update({ name: event.target.value })}
                required
                maxLength={120}
                placeholder="Masalan, To‘y oshi"
              />
            </label>
            <label>
              Kategoriya
              <select value={form.category} onChange={event => update({ category: Number(event.target.value) })} required>
                <option disabled value={0}>Kategoriyani tanlang</option>
                {categories.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            </label>
          </div>
          <div className="form-row">
            <label>
              Narx, so‘m
              <input
                value={form.price}
                onChange={event => update({ price: event.target.value })}
                type="number"
                min="1"
                max="9999999999"
                step="0.01"
                required
              />
            </label>
            <label>
              Porsiya
              <input
                value={form.portion}
                onChange={event => update({ portion: event.target.value })}
                required
                maxLength={50}
                placeholder="350 g"
              />
            </label>
          </div>
          <label>
            Tavsif
            <textarea
              value={form.description}
              onChange={event => update({ description: event.target.value })}
              maxLength={500}
              rows={3}
              placeholder="Tarkibi va taom haqida qisqacha…"
            />
          </label>
          <label className="upload-field">
            <ImagePlus size={24} />
            <span>{imageFile?.name || 'Taom rasmini tanlang'}<small>JPG, PNG, WebP · 5 MB gacha</small></span>
            <input type="file" accept="image/jpeg,image/png,image/webp" onChange={chooseFile} />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.available}
              onChange={event => update({ available: event.target.checked })}
            />
            Hozir sotuvda mavjud
          </label>
          {editId && (
            <label className="checkbox">
              <input
                type="checkbox"
                checked={form.archived}
                onChange={event => update({ archived: event.target.checked })}
              />
              Arxivlash (menyudan olib tashlash)
            </label>
          )}
          <div className="recipe-form-lines">
            <div className="recipe-line-head">
              <div>
                <strong>1 porsiya uchun masalliqlar</strong>
                <small>
                  {ingredients.length
                    ? 'Har bir taomdan bittasi sotilganda shu miqdor ombordan ayriladi'
                    : 'Avval «Ombor va sarf» bo‘limiga masalliq qo‘shing'}
                </small>
              </div>
              <button type="button" className="text-link" onClick={addRecipeLine} disabled={!ingredients.length}>
                <Plus size={15} />Masalliq
              </button>
            </div>
            {recipeLines.map((line, index) => (
              <div key={index} className="recipe-form-line">
                <select
                  value={line.ingredient}
                  onChange={event => {
                    const next = Number(event.target.value)
                    const item = ingredients.find(row => row.id === next)
                    updateRecipeLine(index, { ingredient: next, small: item?.unit !== 'dona' && line.small })
                  }}
                >
                  {ingredients.map(row => (
                    <option key={row.id} value={row.id}>{row.name} · {row.unit}</option>
                  ))}
                </select>
                <div className="amount-field">
                  <input
                    value={line.quantity}
                    onChange={event => updateRecipeLine(index, { quantity: event.target.value })}
                    type="number"
                    min={line.small ? '1' : '0.001'}
                    step={line.small ? '1' : '0.001'}
                    placeholder="Miqdor"
                  />
                  <select
                    value={line.small ? 'small' : 'base'}
                    onChange={event => updateRecipeLine(index, { small: event.target.value === 'small' })}
                    aria-label="O‘lchov birligi"
                  >
                    {(() => {
                      const item = ingredients.find(row => row.id === line.ingredient)
                      if (item?.unit === 'dona') return <option value="base">dona</option>
                      return <>
                        <option value="small">{item?.unit === 'l' ? 'ml' : 'g'}</option>
                        <option value="base">{item?.unit === 'l' ? 'l' : 'kg'}</option>
                      </>
                    })()}
                  </select>
                </div>
                <span className="line-cost">
                  {(() => {
                    const item = ingredients.find(row => row.id === line.ingredient)
                    const price = Number(item?.unit_cost || 0)
                    if (!price) return <em>narx yo‘q</em>
                    const amount = Number(line.quantity || 0) / (line.small ? 1000 : 1)
                    return <>{money(price * amount)} <small>so‘m</small></>
                  })()}
                </span>
                <button
                  type="button"
                  className="icon-button"
                  aria-label="Qatorni o‘chirish"
                  onClick={() => setRecipeLines(recipeLines.filter((_, spot) => spot !== index))}
                >
                  <Trash2 size={16} />
                </button>
              </div>
            ))}
            {!!recipeLines.length && (
              <div className="recipe-line-total">
                <span>1 ta uchun tannarx</span>
                <strong>{money(recipeCost)} so‘m</strong>
                {Number(form.price) > 0 && (
                  <small className={Number(form.price) - recipeCost < 0 ? 'owed' : undefined}>
                    Foyda: {money(Number(form.price) - recipeCost)} so‘m
                  </small>
                )}
              </div>
            )}
            {!recipeLines.length && !!ingredients.length && (
              <p className="empty-state compact">
                Retseptsiz taomning tannarxi nol hisoblanadi va foyda haqiqatdan yuqori ko‘rinadi.
              </p>
            )}
          </div>
          {formError && <p className="alert error" role="alert">{formError}</p>}
          <button className="button primary full" disabled={busy}>{busy ? 'Saqlanmoqda…' : 'Saqlash'}</button>
        </form>
      </AppModal>
    </>
  )
}
