import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ArrowDownToLine, ClipboardList, Coins, Package, Plus } from 'lucide-react'
import { api, list, money, today } from '../api'
import type { Ingredient, Movement } from '../types'
import AppModal from '../components/AppModal'
import StockUsagePanel from '../components/StockUsagePanel'
import DailyUsagePanel from '../components/DailyUsagePanel'

type Modal = '' | 'item' | 'receipt' | 'consumption'

interface MovementForm {
  ingredient: number
  quantity: string
  /** Kirimda to'langan umumiy summa; ombor tannarxi shundan chiqadi. */
  cost_total: string
  note: string
  kind: string
  date: string
}

interface ItemForm {
  name: string
  unit: string
  minimum: string
  /** 1 kg / 1 litr / 1 dona narxi. Kirim bo‘lganda o‘rtacha bo‘yicha yangilanadi. */
  unit_cost: string
}

const modalTitle = (modal: Modal) =>
  modal === 'item' ? 'Yangi mahsulot' : modal === 'receipt' ? 'Omborga kirim' : 'Kunlik haqiqiy sarf'

export default function InventoryPage() {
  // Ko'rinish ham, sarf filtrlari ham manzil satrida turadi, shunda boshqa
  // sahifadan «shu mahsulotning sarfi» havolasi to'g'ridan-to'g'ri ochiladi.
  const [params, setParams] = useSearchParams()
  const wanted = params.get('view')
  const view = wanted === 'usage' ? 'usage' : wanted === 'daily' ? 'daily' : 'stock'
  const usageFilters = {
    start: params.get('start') || `${today().slice(0, 8)}01`,
    end: params.get('end') || today(),
    ingredient: params.get('ingredient') || '',
  }

  function applyUsage(patch: Partial<typeof usageFilters>) {
    const next = { ...usageFilters, ...patch }
    const query = new URLSearchParams({ view: 'usage', start: next.start, end: next.end })
    if (next.ingredient) query.set('ingredient', next.ingredient)
    setParams(query, { replace: true })
  }

  const [ingredients, setIngredients] = useState<Ingredient[]>([])
  const [movements, setMovements] = useState<Movement[]>([])
  const [modal, setModal] = useState<Modal>('')
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const [key, setKey] = useState(() => crypto.randomUUID())
  // Request whose outcome is unknown; a retry replays it byte for byte.
  const [pending, setPending] = useState<{ path: string; body: string }>()
  const [form, setForm] = useState<MovementForm>({
    ingredient: 0, quantity: '', cost_total: '', note: '', kind: 'consumption', date: today(),
  })
  const [item, setItem] = useState<ItemForm>({ name: '', unit: 'kg', minimum: '0', unit_cost: '' })

  const updateForm = (patch: Partial<MovementForm>) => setForm(previous => ({ ...previous, ...patch }))
  const updateItem = (patch: Partial<ItemForm>) => setItem(previous => ({ ...previous, ...patch }))

  const load = useCallback(async () => {
    try {
      const [loadedIngredients, loadedMovements] = await Promise.all([
        list<Ingredient>('ingredients/'),
        api<Movement[]>('stock/'),
      ])
      setIngredients(loadedIngredients)
      setMovements(loadedMovements)
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const low = ingredients.filter(row => Number(row.quantity) <= Number(row.minimum)).length
  const stockValue = ingredients.reduce((sum, row) => sum + Number(row.stock_value), 0)
  const selected = ingredients.find(row => row.id === form.ingredient)
  // Kassir yozayotgan summadan birlik narxini darhol ko'rsatamiz: xato raqam shu yerda bilinadi.
  const unitPrice = Number(form.cost_total) && Number(form.quantity)
    ? Number(form.cost_total) / Number(form.quantity)
    : 0

  function start(kind: Modal) {
    setFormError('')
    setModal(kind)
    if (pending) return
    setKey(crypto.randomUUID())
    setForm({
      ingredient: ingredients[0]?.id || 0,
      quantity: '',
      cost_total: '',
      note: kind === 'consumption' ? 'Kunlik haqiqiy sarf' : '',
      kind,
      date: today(),
    })
    setItem({ name: '', unit: 'kg', minimum: '0', unit_cost: '' })
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    const request = pending ?? {
      path: modal === 'item' ? 'ingredients/' : 'stock/',
      body: JSON.stringify(modal === 'item'
        ? { ...item, unit_cost: item.unit_cost || '0' }
        : { ...form, key, cost_total: form.kind === 'receipt' ? form.cost_total || '0' : undefined }),
    }
    if (!pending) setPending(request)
    try {
      await api(request.path, { method: 'POST', body: request.body })
      setPending(undefined)
      setModal('')
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
      if ((exception as { status?: number }).status === 400) setPending(undefined)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">MAHSULOTLAR NAZORATI</span>
          <h1>Ombor va sarf<span className="heading-dot">.</span></h1>
          <p>Retseptli taom sotilganda xomashyo avtomatik ayriladi.</p>
        </div>
        <div className="heading-actions">
          <button className="button secondary" disabled={!!pending} onClick={() => start('item')}>
            <Plus size={17} />Mahsulot
          </button>
          <button className="button secondary" disabled={!!pending || !ingredients.length} onClick={() => start('receipt')}>
            <ArrowDownToLine size={17} />Kirim
          </button>
          <button className="button primary" disabled={!ingredients.length} onClick={() => start('consumption')}>
            <ClipboardList size={17} />{pending ? 'Amalni tekshirish' : 'Sarf kiritish'}
          </button>
        </div>
      </div>
      {error && <p className="alert error">{error}</p>}

      <div className="tabs view-tabs">
        <button
          className={view === 'stock' ? 'selected' : undefined}
          onClick={() => setParams({}, { replace: true })}
        >
          Qoldiq va harakatlar
        </button>
        <button
          className={view === 'usage' ? 'selected' : undefined}
          onClick={() => applyUsage({})}
        >
          Sarf tahlili
        </button>
        <button
          className={view === 'daily' ? 'selected' : undefined}
          onClick={() => setParams({ view: 'daily' }, { replace: true })}
        >
          Kunlik hisobot
        </button>
      </div>

      {view === 'daily' ? (
        <DailyUsagePanel ingredients={ingredients} />
      ) : view === 'usage' ? (
        <StockUsagePanel ingredients={ingredients} filters={usageFilters} onChange={applyUsage} />
      ) : (
      <>
      <div className="inventory-summary">
        <div><Package size={21} /><span><strong>{ingredients.length}</strong> xil mahsulot</span></div>
        <div><span className="warning-dot" /><span><strong>{low}</strong> ta kam qolgan</span></div>
        <div><Coins size={21} /><span><strong>{money(stockValue)}</strong> so‘mlik qoldiq</span></div>
        <p>
          Kirimda narx yozilsa, ombor tannarxi o‘rtacha tortilgan usulda hisoblanadi va sotuvdagi sarf ham
          so‘mda ko‘rinadi.
        </p>
      </div>
      <section className="panel">
        <header className="panel-heading">
          <div><h2>Xomashyo qoldig‘i</h2><p>Registrdagi miqdor · sotuv va sarf harakatlari bilan yangilanadi</p></div>
          <span className="pill subtle">Asosiy ombor</span>
        </header>
        <div className="table-wrap">
          <table>
            <thead><tr><th>MAHSULOT</th><th>QOLDIQ</th><th>TANNARX</th><th>QOLDIQ QIYMATI</th><th>MINIMAL ME’YOR</th><th>HOLAT</th></tr></thead>
            <tbody>
              {ingredients.map(row => {
                const isLow = Number(row.quantity) <= Number(row.minimum)
                return (
                  <tr key={row.id}>
                    <td><strong>{row.name}</strong></td>
                    <td className="number">{money(row.quantity)} {row.unit}</td>
                    <td className="number">
                      {Number(row.unit_cost)
                        ? <>{money(row.unit_cost)} <small>so‘m/{row.unit}</small></>
                        : <span className="muted">narx yo‘q</span>}
                    </td>
                    <td className="number">{Number(row.stock_value) ? `${money(row.stock_value)} so‘m` : '—'}</td>
                    <td>{money(row.minimum)} {row.unit}</td>
                    <td><span className={`status ${isLow ? 'open' : 'paid'}`}>{isLow ? 'Kam qolgan' : 'Yetarli'}</span></td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {!ingredients.length && <div className="empty-state">Xomashyo ro‘yxatiga mahsulot qo‘shing.</div>}
        </div>
      </section>
      <section className="panel spaced">
        <header className="panel-heading">
          <div><h2>Ombor harakatlari</h2><p>So‘nggi 100 ta kirim, sarf va sotuv bo‘yicha yozuv</p></div>
        </header>
        <div className="table-wrap">
          <table>
            <thead><tr><th>MAHSULOT</th><th>AMAL</th><th>MIQDOR</th><th>SUMMA</th><th>SANA</th><th>IZOH</th></tr></thead>
            <tbody>
              {movements.map(row => (
                <tr key={row.id}>
                  <td>{row.ingredient_name}</td>
                  <td>
                    <span className={`status ${row.kind === 'receipt' ? 'paid' : 'open'}`}>
                      {row.kind === 'receipt' ? 'Kirim' : row.kind === 'sale_consumption' ? 'Sotuv sarfi' : 'Sarf'}
                    </span>
                  </td>
                  <td className="number">{row.kind === 'receipt' ? '+' : '−'}{money(row.quantity)} {row.unit}</td>
                  <td className="number">{Number(row.cost_total) ? `${money(row.cost_total)} so‘m` : '—'}</td>
                  <td>{row.date}</td>
                  <td>{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!movements.length && (
            <div className="empty-state compact">Boshlang‘ich qoldiqni «Kirim» orqali kiriting.</div>
          )}
        </div>
      </section>
      <p className="data-note">
        Retsept, batch tannarxi va foyda «Retsept va foyda» bo‘limida. Sotuvdan oldin xomashyo qoldig‘ini Kirim orqali kiriting.
      </p>
      </>
      )}

      <AppModal open={!!modal} title={modalTitle(modal)} onClose={() => { if (!busy) setModal('') }}>
        <form onSubmit={save}>
          <fieldset disabled={busy || !!pending}>
            {modal === 'item' ? (
              <>
                <label>
                  Mahsulot nomi
                  <input value={item.name} onChange={event => updateItem({ name: event.target.value })} required maxLength={100} />
                </label>
                <div className="form-row">
                  <label>
                    Birlik
                    <select value={item.unit} onChange={event => updateItem({ unit: event.target.value })}>
                      <option>kg</option><option>l</option><option>dona</option>
                    </select>
                  </label>
                  <label>
                    Minimal qoldiq
                    <input
                      value={item.minimum}
                      onChange={event => updateItem({ minimum: event.target.value })}
                      type="number"
                      min="0"
                      step="0.001"
                      required
                    />
                  </label>
                </div>
                <label>
                  1 {item.unit} narxi, so‘m
                  <input
                    value={item.unit_cost}
                    onChange={event => updateItem({ unit_cost: event.target.value })}
                    type="number"
                    min="0"
                    step="1"
                    placeholder="Masalan, 5000"
                  />
                  <small className="field-hint">
                    Retsept tannarxi shu narxdan hisoblanadi. Kirimda summa yozilsa,
                    narx o‘rtacha bo‘yicha o‘zi yangilanadi.
                  </small>
                </label>
              </>
            ) : (
              <>
                <label>
                  Mahsulot
                  <select
                    value={form.ingredient}
                    onChange={event => updateForm({ ingredient: Number(event.target.value) })}
                    required
                  >
                    {ingredients.map(row => (
                      <option key={row.id} value={row.id}>{row.name} · {money(row.quantity)} {row.unit}</option>
                    ))}
                  </select>
                </label>
                <div className="form-row">
                  <label>
                    Miqdor
                    <input
                      value={form.quantity}
                      onChange={event => updateForm({ quantity: event.target.value })}
                      type="number"
                      min="0.001"
                      step="0.001"
                      required
                    />
                  </label>
                  <label>
                    Sana
                    <input
                      value={form.date}
                      onChange={event => updateForm({ date: event.target.value })}
                      type="date"
                      min={today()}
                      max={today()}
                      required
                    />
                  </label>
                </div>
                {modal === 'receipt' && (
                  <label>
                    Qancha so‘mga olindi
                    <input
                      value={form.cost_total}
                      onChange={event => updateForm({ cost_total: event.target.value })}
                      type="number"
                      min="0"
                      step="1"
                      placeholder="Masalan, 300000"
                    />
                    <small className="field-hint">
                      {unitPrice
                        ? `Birlik narxi: ${money(unitPrice)} so‘m / ${selected?.unit || ''}`
                        : 'Bo‘sh qoldirilsa, avvalgi tannarx saqlanadi'}
                    </small>
                  </label>
                )}
                <label>
                  Izoh / sabab
                  <textarea
                    value={form.note}
                    onChange={event => updateForm({ note: event.target.value })}
                    required
                    maxLength={250}
                    rows={2}
                  />
                </label>
              </>
            )}
          </fieldset>
          {modal === 'consumption' && (
            <p className="alert">Kiritilgan miqdor ombor qoldig‘idan ayriladi. Bir sarfni qayta kiritmang.</p>
          )}
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? 'Saqlanmoqda…' : pending ? 'Oldingi amalni tekshirish' : 'Hisobga olish'}
          </button>
        </form>
      </AppModal>
    </>
  )
}
