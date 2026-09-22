import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ArrowDownToLine, ClipboardList, Coins, Minus, Package, Pencil, Plus, Trash2 } from 'lucide-react'
import { api, list, money, today } from '../api'
import { useI18n } from '../i18n'
import { useSession } from '../session'
import type { Ingredient, Movement } from '../types'
import AppModal from '../components/AppModal'
import StockUsagePanel from '../components/StockUsagePanel'
import DailyUsagePanel from '../components/DailyUsagePanel'

type Modal = '' | 'item' | 'receipt' | 'consumption' | 'edit' | 'remove'

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
  modal === 'item' ? 'Yangi mahsulot'
    : modal === 'edit' ? 'Mahsulotni tahrirlash'
      : modal === 'remove' ? 'Mahsulotni ro‘yxatdan chiqarish'
        : modal === 'receipt' ? 'Omborga kirim' : 'Kunlik haqiqiy sarf'

export default function InventoryPage() {
  const { t, tn } = useI18n()
  const owner = useSession().user?.role == 'owner'
  // Ko'rinish ham, sarf filtrlari ham manzil satrida turadi, shunda boshqa
  // sahifadan «shu mahsulotning sarfi» havolasi to'g'ridan-to'g'ri ochiladi.
  const [params, setParams] = useSearchParams()
  const wanted = params.get('view')
  // Sarf tahlili faqat egasiga ochiq; kassir manzil satri orqali kelsa
  // qoldiq ko'rinishiga tushadi, 403 xatosiga emas.
  const view = wanted === 'usage' && owner ? 'usage' : wanted === 'daily' ? 'daily' : 'stock'
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
  // Tahrir va o'chirish uchun tanlangan mahsulot.
  const [chosen, setChosen] = useState<Ingredient>()

  const updateForm = (patch: Partial<MovementForm>) => setForm(previous => ({ ...previous, ...patch }))
  const updateItem = (patch: Partial<ItemForm>) => setItem(previous => ({ ...previous, ...patch }))

  const load = useCallback(async () => {
    try {
      setIngredients(await list<Ingredient>('ingredients/'))
      // Harakatlar tarixi egasining nazorat vositasi: kassirga ko'rinmaydi
      // va so'ralmaydi ham — server uni baribir rad etadi.
      if (owner) setMovements(await api<Movement[]>('stock/'))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [owner])

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

  function start(kind: Modal, ingredient?: number) {
    setFormError('')
    setModal(kind)
    if (pending) return
    setKey(crypto.randomUUID())
    setForm({
      // Qatordan bosilgan bo'lsa o'sha mahsulot tanlangan holda ochiladi.
      ingredient: ingredient || ingredients[0]?.id || 0,
      quantity: '',
      cost_total: '',
      note: kind === 'consumption' ? t('Kunlik haqiqiy sarf') : '',
      kind,
      date: today(),
    })
    setItem({ name: '', unit: 'kg', minimum: '0', unit_cost: '' })
  }

  /** Tahrir oynasini mahsulotning hozirgi qiymatlari bilan ochadi. */
  function edit(row: Ingredient) {
    setChosen(row)
    setItem({
      name: row.name, unit: row.unit,
      minimum: row.minimum, unit_cost: row.unit_cost,
    })
    setFormError('')
    setModal('edit')
  }

  /** O'chirish tasdig'i. Nima bo'lishini oldindan aytib turadi. */
  function confirmRemove(row: Ingredient) {
    setChosen(row)
    setFormError('')
    setModal('remove')
  }

  async function saveEdit(event: FormEvent) {
    event.preventDefault()
    if (!chosen || busy) return
    setBusy(true)
    setFormError('')
    try {
      await api(`ingredients/${chosen.id}/`, {
        method: 'PATCH',
        body: JSON.stringify({ ...item, unit_cost: item.unit_cost || '0' }),
      })
      setModal('')
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!chosen || busy) return
    setBusy(true)
    setFormError('')
    try {
      await api(`ingredients/${chosen.id}/`, { method: 'DELETE' })
      setModal('')
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
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
          <span className="eyebrow">{t('MAHSULOTLAR NAZORATI')}</span>
          <h1>{t('Ombor va sarf')}<span className="heading-dot">.</span></h1>
          <p>{t('Retseptli taom sotilganda xomashyo avtomatik ayriladi.')}</p>
        </div>
        <div className="heading-actions">
          <button className="button secondary" disabled={!!pending} onClick={() => start('item')}>
            <Plus size={17} />{t('Mahsulot')}
          </button>
          <button className="button secondary" disabled={!!pending || !ingredients.length} onClick={() => start('receipt')}>
            <ArrowDownToLine size={17} />{t('Kirim')}
          </button>
          <button className="button primary" disabled={!ingredients.length} onClick={() => start('consumption')}>
            <ClipboardList size={17} />{pending ? t('Amalni tekshirish') : t('Sarf kiritish')}
          </button>
        </div>
      </div>
      {error && <p className="alert error">{error}</p>}

      <div className="tabs view-tabs">
        <button
          className={view === 'stock' ? 'selected' : undefined}
          onClick={() => setParams({}, { replace: true })}
        >
          {t('Qoldiq va harakatlar')}
        </button>
        {/* Sarf tahlili — egasining nazorat vositasi, backendda ham OwnerOnly. */}
        {owner && (
          <button
            className={view === 'usage' ? 'selected' : undefined}
            onClick={() => applyUsage({})}
          >
            {t('Sarf tahlili')}
          </button>
        )}
        <button
          className={view === 'daily' ? 'selected' : undefined}
          onClick={() => setParams({ view: 'daily' }, { replace: true })}
        >
          {t('Kunlik hisobot')}
        </button>
      </div>

      {view === 'daily' ? (
        <DailyUsagePanel ingredients={ingredients} />
      ) : view === 'usage' ? (
        <StockUsagePanel ingredients={ingredients} filters={usageFilters} onChange={applyUsage} />
      ) : (
      <>
      <div className="inventory-summary">
        <div><Package size={21} /><span><strong>{ingredients.length}</strong> {tn('xil mahsulot', ingredients.length)}</span></div>
        <div><span className="warning-dot" /><span><strong>{low}</strong> {t('ta kam qolgan')}</span></div>
        <div><Coins size={21} /><span><strong>{money(stockValue)}</strong> {t('so‘mlik qoldiq')}</span></div>
        <p>
          {t('Kirimda narx yozilsa, ombor tannarxi o‘rtacha tortilgan usulda hisoblanadi va sotuvdagi sarf ham so‘mda ko‘rinadi.')}
        </p>
      </div>
      <section className="panel">
        <header className="panel-heading">
          <div><h2>{t('Xomashyo qoldig‘i')}</h2><p>{t('Registrdagi miqdor · sotuv va sarf harakatlari bilan yangilanadi')}</p></div>
          <span className="pill subtle">{t('Asosiy ombor')}</span>
        </header>
        <div className="table-wrap">
          <table>
            <thead><tr><th>{t('MAHSULOT')}</th><th>{t('QOLDIQ')}</th><th>{t('TANNARX')}</th><th>{t('QOLDIQ QIYMATI')}</th><th>{t('MINIMAL ME’YOR')}</th><th>{t('HOLAT')}</th><th>{t('AMALLAR')}</th></tr></thead>
            <tbody>
              {ingredients.map(row => {
                const isLow = Number(row.quantity) <= Number(row.minimum)
                // Manfiy qoldiq — retsept bo'yicha borig'idan ko'p ayrilgan
                // degani. Buni yashirmaslik kerak: kirim yozilmagan yoki
                // haqiqiy sarf retseptdan farq qilyapti.
                const owing = Number(row.quantity) < 0
                return (
                  <tr key={row.id}>
                    <td><strong>{row.name}</strong></td>
                    <td className={`number${owing ? ' owed' : ''}`}>{money(row.quantity)} {t(row.unit)}</td>
                    <td className="number">
                      {Number(row.unit_cost)
                        ? <>{money(row.unit_cost)} <small>{t('so‘m')}/{row.unit}</small></>
                        : <span className="muted">{t('narx yo‘q')}</span>}
                    </td>
                    <td className="number">{Number(row.stock_value) ? `${money(row.stock_value)} ${t('so‘m')}` : '—'}</td>
                    <td>{money(row.minimum)} {t(row.unit)}</td>
                    <td>
                      <span className={`status ${owing ? 'alert' : isLow ? 'open' : 'paid'}`}>
                        {owing ? t('Hisobdan oshgan') : isLow ? t('Kam qolgan') : t('Yetarli')}
                      </span>
                    </td>
                    <td>
                      {/* Qatorning o'zidan kiritish: mahsulot allaqachon
                          tanlangan bo'ladi, ro'yxatdan qidirish shart emas. */}
                      <div className="row-buttons">
                        <button
                          className="table-action receipt"
                          title={t('{name} uchun kirim', { name: row.name })}
                          onClick={() => start('receipt', row.id)}
                        >
                          <ArrowDownToLine size={14} />{t('Kirim')}
                        </button>
                        <button
                          className="table-action"
                          title={t('{name} uchun sarf', { name: row.name })}
                          onClick={() => start('consumption', row.id)}
                        >
                          <Minus size={14} />{t('Sarf')}
                        </button>
                        {/* Nomini tuzatish va ro'yxatdan chiqarish — faqat
                            egasiga: qoldiqqa tegmaydi, lekin ro'yxatni
                            o'zgartiradi. */}
                        {owner && (
                          <>
                            <button
                              className="table-action"
                              title={t('{name} ni tahrirlash', { name: row.name })}
                              onClick={() => edit(row)}
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              className="table-action"
                              title={t('{name} ni ro‘yxatdan chiqarish', { name: row.name })}
                              onClick={() => confirmRemove(row)}
                            >
                              <Trash2 size={14} />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {!ingredients.length && <div className="empty-state">{t('Xomashyo ro‘yxatiga mahsulot qo‘shing.')}</div>}
        </div>
      </section>
      {owner && (
      <section className="panel spaced">
        <header className="panel-heading">
          <div><h2>{t('Ombor harakatlari')}</h2><p>{t('So‘nggi 100 ta kirim, sarf va sotuv bo‘yicha yozuv')}</p></div>
        </header>
        <div className="table-wrap">
          <table>
            <thead><tr><th>{t('MAHSULOT')}</th><th>{t('AMAL')}</th><th>{t('MIQDOR')}</th><th>{t('SUMMA')}</th><th>{t('SANA')}</th><th>{t('IZOH')}</th></tr></thead>
            <tbody>
              {movements.map(row => (
                <tr key={row.id}>
                  <td>{row.ingredient_name}</td>
                  <td>
                    <span className={`status ${row.kind === 'receipt' ? 'paid' : 'open'}`}>
                      {row.kind === 'receipt' ? t('Kirim') : row.kind === 'sale_consumption' ? t('Sotuv sarfi') : t('Sarf')}
                    </span>
                  </td>
                  <td className="number">{row.kind === 'receipt' ? '+' : '−'}{money(row.quantity)} {t(row.unit)}</td>
                  <td className="number">{Number(row.cost_total) ? `${money(row.cost_total)} ${t('so‘m')}` : '—'}</td>
                  <td>{row.date}</td>
                  <td>{row.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!movements.length && (
            <div className="empty-state compact">{t('Boshlang‘ich qoldiqni «Kirim» orqali kiriting.')}</div>
          )}
        </div>
      </section>
      )}
      <p className="data-note">
        {t('Retsept, batch tannarxi va foyda «Retsept va foyda» bo‘limida. Sotuvdan oldin xomashyo qoldig‘ini Kirim orqali kiriting.')}
      </p>
      </>
      )}

      <AppModal
        open={modal === 'item' || modal === 'receipt' || modal === 'consumption'}
        title={t(modalTitle(modal))}
        onClose={() => { if (!busy) setModal('') }}
      >
        <form onSubmit={save}>
          <fieldset disabled={busy || !!pending}>
            {modal === 'item' ? (
              <>
                <label>
                  {t('Mahsulot nomi')}
                  <input value={item.name} onChange={event => updateItem({ name: event.target.value })} required maxLength={100} />
                </label>
                <div className="form-row">
                  <label>
                    {t('Birlik')}
                    <select value={item.unit} onChange={event => updateItem({ unit: event.target.value })}>
                      <option value="kg">{t('kg')}</option>
                      <option value="l">{t('l')}</option>
                      <option value="dona">{t('dona')}</option>
                    </select>
                  </label>
                  <label>
                    {t('Minimal qoldiq')}
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
                  {t('1 {unit} narxi, so‘m', { unit: item.unit })}
                  <input
                    value={item.unit_cost}
                    onChange={event => updateItem({ unit_cost: event.target.value })}
                    type="number"
                    min="0"
                    step="1"
                    placeholder={t('Masalan, 5000')}
                  />
                  <small className="field-hint">
                    {t('Retsept tannarxi shu narxdan hisoblanadi. Kirimda summa yozilsa, narx o‘rtacha bo‘yicha o‘zi yangilanadi.')}
                  </small>
                </label>
              </>
            ) : (
              <>
                <label>
                  {t('Mahsulot')}
                  <select
                    value={form.ingredient}
                    onChange={event => updateForm({ ingredient: Number(event.target.value) })}
                    required
                  >
                    {ingredients.map(row => (
                      <option key={row.id} value={row.id}>{row.name} · {money(row.quantity)} {t(row.unit)}</option>
                    ))}
                  </select>
                </label>
                <div className="form-row">
                  <label>
                    {t('Miqdor')}
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
                    {t('Sana')}
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
                    {t('Qancha so‘mga olindi')}
                    <input
                      value={form.cost_total}
                      onChange={event => updateForm({ cost_total: event.target.value })}
                      type="number"
                      min="0"
                      step="1"
                      placeholder={t('Masalan, 300000')}
                    />
                    <small className="field-hint">
                      {unitPrice
                        ? t('Birlik narxi: {price} so‘m / {unit}', { price: money(unitPrice), unit: selected?.unit || '' })
                        : t('Bo‘sh qoldirilsa, avvalgi tannarx saqlanadi')}
                    </small>
                  </label>
                )}
                <label>
                  {t('Izoh / sabab')}
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
            <p className="alert">{t('Kiritilgan miqdor ombor qoldig‘idan ayriladi. Bir sarfni qayta kiritmang.')}</p>
          )}
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : pending ? t('Oldingi amalni tekshirish') : t('Hisobga olish')}
          </button>
        </form>
      </AppModal>

      {/* ── Tahrirlash ── */}
      <AppModal
        open={modal === 'edit'}
        title={t('{name} · tahrirlash', { name: chosen?.name || '' })}
        onClose={() => { if (!busy) setModal('') }}
      >
        <form onSubmit={saveEdit}>
          <label>
            {t('Mahsulot nomi')}
            <input
              value={item.name}
              onChange={event => updateItem({ name: event.target.value })}
              required
              maxLength={100}
              autoFocus
            />
            <small className="field-hint">
              {t('Nom o‘zgarsa retseptlar ham yangi nom bilan ko‘rinadi — bog‘lanish uzilmaydi.')}
            </small>
          </label>
          <div className="form-row">
            <label>
              {t('Birlik')}
              <select
                value={item.unit}
                onChange={event => updateItem({ unit: event.target.value })}
                disabled={chosen?.has_history}
              >
                <option value="kg">{t('kg')}</option>
                <option value="l">{t('l')}</option>
                <option value="dona">{t('dona')}</option>
              </select>
              {chosen?.has_history && (
                <small className="field-hint">
                  {t('Kirim-chiqim tarixi bor — birlikni o‘zgartirib bo‘lmaydi.')}
                </small>
              )}
            </label>
            <label>
              {t('Minimal qoldiq')}
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
            {t('1 {unit} narxi, so‘m', { unit: item.unit })}
            <input
              value={item.unit_cost}
              onChange={event => updateItem({ unit_cost: event.target.value })}
              type="number"
              min="0"
              step="1"
            />
            <small className="field-hint">
              {t('Narx o‘zgarsa shu mahsulot ishlatilgan retseptlar tannarxi darhol qayta hisoblanadi.')}
            </small>
          </label>
          <p className="data-note">
            {t('Qoldiq bu yerdan o‘zgarmaydi — u faqat kirim va sarf orqali harakatlanadi.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('Saqlash')}
          </button>
        </form>
      </AppModal>

      {/* ── Ro'yxatdan chiqarish ── */}
      <AppModal
        open={modal === 'remove'}
        title={t('{name} · ro‘yxatdan chiqarish', { name: chosen?.name || '' })}
        onClose={() => { if (!busy) setModal('') }}
      >
        {/* Tugmani bosishdan oldin nima bo'lishi aytiladi: retseptdagi
            mahsulot umuman chiqmaydi, tarixlisi esa arxivlanadi. */}
        {chosen?.in_use ? (
          <p className="alert error">
            {t('Bu mahsulot retseptda ishlatilyapti — avval retseptdan olib tashlang, so‘ng ro‘yxatdan chiqaring.')}
          </p>
        ) : chosen?.has_history ? (
          <p className="alert">
            {t('Bu mahsulotda kirim-chiqim tarixi bor, shuning uchun u o‘chirilmaydi — ro‘yxatdan olinadi. Eski hisobotlarda nomi va harakatlari joyida qoladi.')}
          </p>
        ) : (
          <p className="alert">
            {t('Bu mahsulot hech qachon ishlatilmagan — butunlay o‘chiriladi.')}
          </p>
        )}
        {!!chosen && Number(chosen.quantity) !== 0 && (
          <p className="data-note">
            {t('Hozirgi qoldiq: {amount} {unit}. U yo‘qolmaydi va ombor qiymatida turaveradi.', {
              amount: money(chosen.quantity), unit: t(chosen.unit),
            })}
          </p>
        )}
        {formError && <p className="alert error">{formError}</p>}
        <button className="button danger full" disabled={busy || chosen?.in_use} onClick={remove}>
          {busy ? t('Saqlanmoqda…')
            : chosen?.has_history ? t('Ro‘yxatdan chiqarish') : t('O‘chirish')}
        </button>
      </AppModal>
    </>
  )
}
