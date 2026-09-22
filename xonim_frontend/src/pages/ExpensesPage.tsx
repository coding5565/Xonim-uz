import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Filter, Pencil, Plus, Search, Trash2, Wallet, X } from 'lucide-react'
import { api, list, money, today } from '../api'
import { useI18n } from '../i18n'
import { useSession } from '../session'
import type { Expense } from '../types'
import AppModal from '../components/AppModal'

interface ExpenseForm {
  category: string
  purpose: string
  recipient: string
  amount: string
  payment_method: string
  date: string
}

// Masalliq birinchi turadi: restoran xarajatining katta qismi shu.
const categories = ['Masalliq', 'Kommunal', 'Ijara', 'Transport', 'Ta’mirlash', 'Tozalash', 'Boshqa']

const emptyForm = (): ExpenseForm => ({
  category: 'Masalliq', purpose: '', recipient: '', amount: '', payment_method: 'cash', date: today(),
})

export default function ExpensesPage() {
  // Davr va kategoriya manzil satridan olinadi: «Umumiy moliya» sahifasidagi
  // xarajat qatorini bosganda aynan o'sha kesim ochilishi kerak.
  const { t, tn } = useI18n()
  const { user } = useSession()
  // Tuzatish va o'chirish — nazorat amali, shuning uchun faqat superadminda.
  const owner = user?.role === 'owner'
  const [params, setParams] = useSearchParams()
  const range = {
    start: params.get('start') || '',
    end: params.get('end') || '',
    category: params.get('category') || '',
  }

  function applyRange(patch: Partial<typeof range>) {
    const next = { ...range, ...patch }
    const query = new URLSearchParams()
    for (const [name, value] of Object.entries(next)) if (value) query.set(name, value)
    setParams(query, { replace: true })
  }

  const [rows, setRows] = useState<Expense[]>([])
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [query, setQuery] = useState('')
  const [key, setKey] = useState(() => crypto.randomUUID())
  // Body of a request whose outcome is unknown; a retry reuses it unchanged.
  const [submitted, setSubmitted] = useState<string>()
  const [form, setForm] = useState<ExpenseForm>(emptyForm)
  // Tuzatish va o'chirish: noto'g'ri kiritilgan summa foyda hisobiga
  // to'g'ridan-to'g'ri kiradi, shuning uchun uni qaytarib olish kerak.
  const [editing, setEditing] = useState<Expense>()
  const [removing, setRemoving] = useState<Expense>()

  const update = (patch: Partial<ExpenseForm>) => setForm(previous => ({ ...previous, ...patch }))

  const load = useCallback(async () => {
    try {
      setRows(await list<Expense>('expenses/'))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  // Xarajatlar soni kam, shuning uchun saralash brauzerda bajariladi.
  const inRange = rows.filter(row =>
    (!range.start || row.date >= range.start)
    && (!range.end || row.date <= range.end)
    && (!range.category || row.category === range.category))
  const filtered = inRange.filter(row =>
    `${row.purpose} ${row.category} ${row.recipient}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
  )
  const sum = inRange.reduce((total, row) => total + Number(row.amount), 0)
  const known = [...new Set(rows.map(row => row.category))].sort()
  const narrowed = !!(range.start || range.end || range.category)

  function start() {
    setOpen(true)
    setEditing(undefined)
    setFormError('')
    if (!submitted) {
      setKey(crypto.randomUUID())
      setForm(emptyForm())
    }
  }

  /** Noto'g'ri kiritilgan xarajatni tuzatish. Faqat superadmin ko'radi. */
  function edit(row: Expense) {
    setEditing(row)
    setFormError('')
    setForm({
      category: row.category, purpose: row.purpose, recipient: row.recipient,
      amount: row.amount, payment_method: row.payment_method, date: row.date,
    })
    setOpen(true)
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    try {
      if (editing) {
        // Tahrirda takroriy yuborish xavfi yo'q: manzil aniq bir yozuvga
        // ishora qiladi, shuning uchun amal kaliti ham kerak emas.
        await api(`expenses/${editing.id}/`, { method: 'PATCH', body: JSON.stringify(form) })
        setOpen(false)
        setEditing(undefined)
        await load()
        return
      }
      const body = submitted ?? JSON.stringify({ ...form, key })
      if (!submitted) setSubmitted(body)
      await api('expenses/', { method: 'POST', body })
      setSubmitted(undefined)
      setOpen(false)
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
      if ((exception as { status?: number }).status === 400) setSubmitted(undefined)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    if (!removing) return
    setBusy(true)
    setFormError('')
    try {
      await api(`expenses/${removing.id}/`, { method: 'DELETE' })
      setRemoving(undefined)
      await load()
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
          <span className="eyebrow">{t('MOLIYAVIY TARTIB')}</span>
          <h1>{t('Xarajatlar')}<span className="heading-dot">.</span></h1>
          <p>{t('Nimaga, kimga va qancha — har bir chiqim ochiq.')}</p>
        </div>
        <button className="button primary" onClick={start}><Plus size={18} />{t('Xarajat kiritish')}</button>
      </div>
      <div className="expense-summary">
        <span className="metric-icon orange"><Wallet size={22} /></span>
        <div>
          <span className="muted">{t(narrowed ? 'Tanlangan kesim bo‘yicha' : 'Barcha kiritilgan xarajatlar')}</span>
          <h2>{money(sum)} <small>{t('so‘m')}</small></h2>
        </div>
        <span className="pill">{tn('{count} ta yozuv', inRange.length)}</span>
      </div>
      {error && <p className="alert error">{error}</p>}

      <section className="panel report-filters">
        <header>
          <Filter size={19} />
          <div><h2>{t('Davr va kategoriya')}</h2><p>{t('Qaysi kundan qaysi kungacha, qaysi turdagi chiqim')}</p></div>
          {narrowed && (
            <button className="button secondary" onClick={() => setParams({}, { replace: true })}>
              <X size={15} />{t('Filtrni tozalash')}
            </button>
          )}
        </header>
        <div className="report-filter-grid">
          <label>
            {t('Boshlanish')}
            <input value={range.start} onChange={event => applyRange({ start: event.target.value })} type="date" max={range.end || today()} />
          </label>
          <label>
            {t('Tugash')}
            <input value={range.end} onChange={event => applyRange({ end: event.target.value })} type="date" min={range.start || undefined} max={today()} />
          </label>
          <label>
            {t('Kategoriya')}
            <select value={range.category} onChange={event => applyRange({ category: event.target.value })}>
              <option value="">{t('Barcha kategoriyalar')}</option>
              {known.map(item => <option key={item} value={item}>{item}</option>)}
            </select>
          </label>
        </div>
      </section>
      <section className="panel">
        <header className="panel-heading">
          <div><h2>{t('Xarajatlar ro‘yxati')}</h2><p>{t('Admin saqlashi bilan hisobga olinadi')}</p></div>
          <div className="search-field">
            <Search size={17} />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              placeholder={t('Maqsad, oluvchi, kategoriya…')}
              aria-label={t('Xarajat qidirish')}
            />
          </div>
        </header>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('MAQSAD / OLUVCHI')}</th><th>{t('KATEGORIYA')}</th><th>{t('SANA')}</th>
                <th>{t('SUMMA')}</th><th>{t('TO‘LOV')}</th><th>{t('KIRITGAN')}</th>
                {owner && <th aria-label={t('Amallar')} />}
              </tr>
            </thead>
            <tbody>
              {filtered.map(row => (
                <tr key={row.id}>
                  <td><strong>{row.purpose}</strong><small>{row.recipient || t('Oluvchi ko‘rsatilmagan')}</small></td>
                  <td><span className="pill subtle">{t(row.category)}</span></td>
                  <td>{row.date}</td>
                  <td className="number">{money(row.amount)}</td>
                  <td>
                    <span className={`status ${row.payment_method === 'unpaid' ? 'open' : 'paid'}`}>
                      {t(row.payment_method === 'cash' ? 'Naqd' : row.payment_method === 'card' ? 'Karta' : 'To‘lanmagan')}
                    </span>
                  </td>
                  <td>{row.actor_name}</td>
                  {owner && (
                    <td className="row-actions">
                      <button
                        className="icon-button"
                        aria-label={t('Tuzatish')}
                        title={t('Tuzatish')}
                        onClick={() => edit(row)}
                      >
                        <Pencil size={15} />
                      </button>
                      <button
                        className="icon-button"
                        aria-label={t('O‘chirish')}
                        title={t('O‘chirish')}
                        onClick={() => { setFormError(''); setRemoving(row) }}
                      >
                        <Trash2 size={15} />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
          {!filtered.length && (
            <div className="empty-state">
              <Wallet size={38} strokeWidth={1.3} />
              <h3>{t('Xarajatlar hali yo‘q')}</h3>
              <p>{t('Ijara, kommunal va boshqa kundalik xarajatlarni kiriting.')}</p>
            </div>
          )}
        </div>
      </section>
      <p className="data-note">
        {t('Bu bo‘lim kundalik xarajatlar uchun. Ombor xaridi qiymati va ikkiyoqlama buxgalteriya registri hali ulanmagan.')}
      </p>

      <AppModal
        open={open}
        title={t(editing ? 'Xarajatni tuzatish' : 'Yangi xarajat')}
        onClose={() => { if (!busy) { setOpen(false); setEditing(undefined) } }}
      >
        <form onSubmit={save}>
          <fieldset disabled={(!editing && !!submitted) || busy}>
            <div className="form-row">
              <label>
                {t('Kategoriya')}
                <select value={form.category} onChange={event => update({ category: event.target.value })}>
                  {/* Qiymat o'zbekcha saqlanadi, ko'rinishi tarjima qilinadi. */}
                  {categories.map(item => <option key={item} value={item}>{t(item)}</option>)}
                </select>
              </label>
              <label>
                {t('Sana')}
                <input
                  value={form.date}
                  onChange={event => update({ date: event.target.value })}
                  type="date"
                  max={today()}
                  required
                />
              </label>
            </div>
            {/* Omborga kirim qilingan masalliq allaqachon pul oqimida turadi.
                Shu xaridni yana xarajat qilib yozish — pulni ikki marta
                sanash degani, shuning uchun ogohlantirish shu yerda turadi. */}
            {form.category === 'Masalliq' && (
              <p className="alert">
                {t('Bu masalliqni omborga kirim qilgan bo‘lsangiz, uni yana bu yerda yozmang — pul ikki marta hisoblanadi. Ombordagi kirim allaqachon pul oqimiga tushgan.')}
              </p>
            )}
            <label>
              {t('Nimaga ishlatildi?')}
              <textarea
                value={form.purpose}
                onChange={event => update({ purpose: event.target.value })}
                required
                maxLength={250}
                rows={2}
                placeholder={t('Masalan, sentabr oyi elektr to‘lovi')}
              />
            </label>
            <label>
              {t('Kimga to‘landi?')}
              <input
                value={form.recipient}
                onChange={event => update({ recipient: event.target.value })}
                maxLength={120}
                placeholder={t('Tashkilot yoki shaxs')}
              />
            </label>
            <div className="form-row">
              <label>
                {t('Summa, so‘m')}
                <input
                  value={form.amount}
                  onChange={event => update({ amount: event.target.value })}
                  type="number"
                  min="1"
                  step="0.01"
                  required
                />
              </label>
              <label>
                {t('To‘lov')}
                <select value={form.payment_method} onChange={event => update({ payment_method: event.target.value })}>
                  <option value="cash">{t('Naqd to‘landi')}</option>
                  <option value="card">{t('Karta to‘landi')}</option>
                  <option value="unpaid">{t('Hali to‘lanmagan')}</option>
                </select>
              </label>
            </div>
          </fieldset>
          <p className="alert">
            {t(editing
              ? 'Tuzatish jurnalga yoziladi: eski va yangi qiymat ko‘rinib turadi.'
              : 'Saqlangach darhol hisobga olinadi. Superadmin tasdig‘i talab qilinmaydi.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {t(busy ? 'Saqlanmoqda…'
              : editing ? 'Tuzatishni saqlash'
              : submitted ? 'Oldingi amalni qayta tekshirish'
              : 'Xarajatni saqlash')}
          </button>
        </form>
      </AppModal>

      <AppModal
        open={!!removing}
        title={t('Xarajatni o‘chirish')}
        onClose={() => { if (!busy) setRemoving(undefined) }}
      >
        {removing && (
          <>
            <p className="data-note">
              {t('«{purpose}» · {sum} so‘m · {date} — o‘chirilsinmi?', {
                purpose: removing.purpose, sum: money(removing.amount), date: removing.date,
              })}
            </p>
            <p className="alert">{t('Yozuv butunlay o‘chadi, lekin o‘chirilgani jurnalda qoladi.')}</p>
            {formError && <p className="alert error">{formError}</p>}
            <button className="button danger full" disabled={busy} onClick={remove}>
              <Trash2 size={17} />{t(busy ? 'Saqlanmoqda…' : 'O‘chirish')}
            </button>
            <button className="button secondary full" disabled={busy} onClick={() => setRemoving(undefined)}>
              {t('Bekor qilish')}
            </button>
          </>
        )}
      </AppModal>
    </>
  )
}
