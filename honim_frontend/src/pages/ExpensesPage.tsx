import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Filter, Plus, Search, Wallet, X } from 'lucide-react'
import { api, list, money, today } from '../api'
import { useI18n } from '../i18n'
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

const categories = ['Kommunal', 'Ijara', 'Transport', 'Ta’mirlash', 'Tozalash', 'Boshqa']

const emptyForm = (): ExpenseForm => ({
  category: 'Kommunal', purpose: '', recipient: '', amount: '', payment_method: 'cash', date: today(),
})

export default function ExpensesPage() {
  // Davr va kategoriya manzil satridan olinadi: «Umumiy moliya» sahifasidagi
  // xarajat qatorini bosganda aynan o'sha kesim ochilishi kerak.
  const { t, tn } = useI18n()
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
    setFormError('')
    if (!submitted) {
      setKey(crypto.randomUUID())
      setForm(emptyForm())
    }
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    const body = submitted ?? JSON.stringify({ ...form, key })
    if (!submitted) setSubmitted(body)
    try {
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
              <X size={15} />{t('Tozalash')}
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
              </tr>
            </thead>
            <tbody>
              {filtered.map(row => (
                <tr key={row.id}>
                  <td><strong>{row.purpose}</strong><small>{row.recipient || t('Oluvchi ko‘rsatilmagan')}</small></td>
                  <td><span className="pill subtle">{row.category}</span></td>
                  <td>{row.date}</td>
                  <td className="number">{money(row.amount)}</td>
                  <td>
                    <span className={`status ${row.payment_method === 'unpaid' ? 'open' : 'paid'}`}>
                      {t(row.payment_method === 'cash' ? 'Naqd' : row.payment_method === 'card' ? 'Karta' : 'To‘lanmagan')}
                    </span>
                  </td>
                  <td>{row.actor_name}</td>
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

      <AppModal open={open} title={t('Yangi xarajat')} onClose={() => { if (!busy) setOpen(false) }}>
        <form onSubmit={save}>
          <fieldset disabled={!!submitted || busy}>
            <div className="form-row">
              <label>
                {t('Kategoriya')}
                <select value={form.category} onChange={event => update({ category: event.target.value })}>
                  {categories.map(item => <option key={item}>{item}</option>)}
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
          <p className="alert">{t('Saqlangach darhol hisobga olinadi. Superadmin tasdig‘i talab qilinmaydi.')}</p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {t(busy ? 'Saqlanmoqda…' : submitted ? 'Oldingi amalni qayta tekshirish' : 'Xarajatni saqlash')}
          </button>
        </form>
      </AppModal>
    </>
  )
}
