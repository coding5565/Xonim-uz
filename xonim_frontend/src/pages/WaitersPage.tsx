import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Banknote, ConciergeBell, Coins, Pencil, Plus, Trash2, Users } from 'lucide-react'
import { api, list, money, today } from '../api'
import { useI18n } from '../i18n'
import type { Waiter, WaiterBook, WaiterEarnings } from '../types'
import { CardsSkeleton, TableSkeleton } from '../components/Skeleton'
import AppModal from '../components/AppModal'

interface WaiterForm {
  name: string
  phone: string
  commission: string
  active: boolean
}

interface PayForm {
  key: string
  amount: string
  payment_method: string
  paid_on: string
  note: string
}

const emptyForm = (): WaiterForm => ({ name: '', phone: '', commission: '5', active: true })

/** Ofitsiantlar va ularning ulushi.
 *
 * Foizni faqat superadmin belgilaydi; kassir buyurtmaga ofitsiantni bog'laydi.
 * Foiz sotuv paytida hisobga muzlatiladi, shuning uchun bugun foizni
 * o'zgartirish o'tgan hisobotlarni buzmaydi.
 */
export default function WaitersPage() {
  const { t, tn } = useI18n()
  const [rows, setRows] = useState<Waiter[]>()
  const [earnings, setEarnings] = useState<WaiterEarnings>()
  const [range, setRange] = useState({ start: today(), end: today() })
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState<Waiter>()
  const [form, setForm] = useState<WaiterForm>(emptyForm)
  const [paying, setPaying] = useState<WaiterBook>()
  const [payForm, setPayForm] = useState<PayForm>({
    key: '', amount: '', payment_method: 'cash', paid_on: today(), note: '',
  })

  const update = (patch: Partial<WaiterForm>) => setForm(previous => ({ ...previous, ...patch }))

  const loadWaiters = useCallback(async () => {
    try {
      setRows(await list<Waiter>('waiters/'))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [])

  const loadEarnings = useCallback(async (start: string, end: string) => {
    try {
      setEarnings(await api<WaiterEarnings>(`reports/waiters/?start=${start}&end=${end}`))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [])

  useEffect(() => {
    loadWaiters()
  }, [loadWaiters])

  useEffect(() => {
    loadEarnings(range.start, range.end)
  }, [loadEarnings, range.start, range.end])

  function startNew() {
    setEditing(undefined)
    setForm(emptyForm())
    setFormError('')
    setOpen(true)
  }

  function startEdit(waiter: Waiter) {
    setEditing(waiter)
    setForm({ name: waiter.name, phone: waiter.phone, commission: waiter.commission, active: waiter.active })
    setFormError('')
    setOpen(true)
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setFormError('')
    try {
      await api(editing ? `waiters/${editing.id}/` : 'waiters/', {
        method: editing ? 'PATCH' : 'POST',
        body: JSON.stringify(form),
      })
      setOpen(false)
      await Promise.all([loadWaiters(), loadEarnings(range.start, range.end)])
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function startPay(row: WaiterBook) {
    setPaying(row)
    setPayForm({
      // Kalit shu yerda tug'iladi: takroriy bosish ikki marta pul bermaydi.
      key: crypto.randomUUID(),
      amount: Number(row.balance) > 0 ? row.balance : '',
      payment_method: 'cash',
      paid_on: today(),
      note: '',
    })
    setFormError('')
  }

  async function payWaiter(event: FormEvent) {
    event.preventDefault()
    if (!paying) return
    setBusy(true)
    setFormError('')
    try {
      await api(`waiters/${paying.id}/payments/`, { method: 'POST', body: JSON.stringify(payForm) })
      setPaying(undefined)
      await loadEarnings(range.start, range.end)
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function remove(waiter: Waiter) {
    // O'chirilmaydi — faolsizlantiriladi, aks holda o'tgan hisoblar egasiz qolardi.
    if (!confirm(t('«{name}» ro‘yxatdan olinsinmi? Eski hisoblari saqlanib qoladi.', { name: waiter.name }))) return
    try {
      await api(`waiters/${waiter.id}/`, { method: 'DELETE' })
      await loadWaiters()
    } catch (exception) {
      setError((exception as Error).message)
    }
  }

  const summary = earnings?.summary

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('XIZMAT KO‘RSATISH')}</span>
          <h1>{t('Ofitsiantlar')}<span className="heading-dot">.</span></h1>
          <p>{t('Kim qancha sotdi va xizmati uchun qancha oladi.')}</p>
        </div>
        <button className="button primary" onClick={startNew}><Plus size={18} />{t('Ofitsiant qo‘shish')}</button>
      </div>

      {error && <p className="alert error">{error}</p>}

      {!earnings ? <CardsSkeleton count={4} /> : (
        <div className="metric-grid">
          <article className="metric-card tone-out">
            <div className="metric-top">
              <span>{t('Xizmat haqi')}</span>
              <span className="metric-icon orange"><ConciergeBell size={19} /></span>
            </div>
            <div className="metric-value">{money(summary!.fees)}<small>{t('so‘m')}</small></div>
            <p>{t('Har hisobning o‘z foizi bo‘yicha')}</p>
          </article>
          <article className="metric-card tone-flat">
            <div className="metric-top">
              <span>{t('Bugun yig‘ildi')}</span>
              <span className="metric-icon blue"><ConciergeBell size={19} /></span>
            </div>
            <div className="metric-value">{money(summary!.today_fee)}<small>{t('so‘m')}</small></div>
            <p>{t('bugungi stol savdosi {amount} so‘m', { amount: money(summary!.today_sales) })}</p>
          </article>
          <article className="metric-card tone-out">
            <div className="metric-top">
              <span>{t('Berilishi kerak')}</span>
              <span className="metric-icon orange"><Banknote size={19} /></span>
            </div>
            <div className="metric-value">{money(summary!.owed)}<small>{t('so‘m')}</small></div>
            <p>{t('yig‘ilgan haq − berilgan pul')}</p>
          </article>
          <article className="metric-card tone-flat">
            <div className="metric-top">
              <span>{t('Ofitsiantsiz')}</span>
              <span className="metric-icon violet"><Users size={19} /></span>
            </div>
            <div className="metric-value">{money(summary!.unassigned_revenue)}<small>{t('so‘m')}</small></div>
            <p>{tn('{count} ta hisob bog‘lanmagan', summary!.unassigned_orders)}</p>
          </article>
        </div>
      )}

      <section className="panel report-filters">
        <header>
          <Coins size={19} />
          <div><h2>{t('Hisobot davri')}</h2><p>{t('Ulush faqat to‘langan hisoblardan hisoblanadi')}</p></div>
        </header>
        <div className="report-filter-grid">
          <label>
            {t('Boshlanish')}
            <input
              value={range.start}
              onChange={event => setRange(previous => ({ ...previous, start: event.target.value }))}
              type="date"
              max={range.end}
            />
          </label>
          <label>
            {t('Tugash')}
            <input
              value={range.end}
              onChange={event => setRange(previous => ({ ...previous, end: event.target.value }))}
              type="date"
              min={range.start}
              max={today()}
            />
          </label>
        </div>
      </section>

      <section className="panel">
        <header className="panel-heading">
          <div>
            <h2>{t('Davr bo‘yicha ulush')}</h2>
            <p>{t('Xizmat haqi hisob ustiga qo‘shiladi va to‘liq ofitsiantga o‘tadi')}</p>
          </div>
        </header>
        {!earnings ? <TableSkeleton rows={4} columns={5} /> : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t('OFITSIANT')}</th><th>{t('HISOBLAR')}</th><th>{t('SAVDO')}</th>
                  <th>{t('ULUSHI')}</th><th>{t('BUGUN')}</th><th>{t('BALANS')}</th><th>{t('AMAL')}</th>
                </tr>
              </thead>
              <tbody>
                {earnings.waiters.map(row => (
                  <tr key={row.id}>
                    <td><strong>{row.name}</strong></td>
                    <td className="number">{row.orders}</td>
                    <td className="number">{money(row.revenue)}</td>
                    <td className="number"><strong>{money(row.fee)}</strong></td>
                    <td className="number">
                      {money(row.today_fee)}
                      <small>{tn('{count} ta hisob', row.today_orders)}</small>
                    </td>
                    <td className="number">
                      <strong className={Number(row.balance) > 0 ? 'owed' : undefined}>
                        {money(row.balance)}
                      </strong>
                      <small>{t('berilgan {amount}', { amount: money(row.paid) })}</small>
                    </td>
                    <td>
                      <button className="button primary small" disabled={busy} onClick={() => startPay(row)}>
                        <Banknote size={15} />{t('Pul berish')}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!earnings.waiters.length && (
              <div className="empty-state">
                <ConciergeBell size={38} strokeWidth={1.3} />
                <h3>{t('Bu davrda ofitsiantga bog‘langan hisob yo‘q')}</h3>
                <p>{t('Kassir hisobni ochayotganda ofitsiantni tanlaydi.')}</p>
              </div>
            )}
          </div>
        )}
      </section>

      <section className="panel">
        <header className="panel-heading">
          <div><h2>{t('Ro‘yxat')}</h2><p>{t('Foizni faqat superadmin o‘zgartiradi')}</p></div>
          <span className="pill subtle">{tn('{count} ta ofitsiant', rows?.length || 0)}</span>
        </header>
        {!rows ? <TableSkeleton rows={3} columns={4} /> : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t('ISM')}</th><th>{t('TELEFON')}</th><th>{t('ULUSHI')}</th>
                  <th>{t('HOLAT')}</th><th>{t('AMALLAR')}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(row => (
                  <tr key={row.id}>
                    <td><strong>{row.name}</strong></td>
                    <td>{row.phone || <span className="muted">—</span>}</td>
                    <td className="number">{row.commission}%</td>
                    <td>
                      <span className={`status ${row.active ? 'paid' : 'neutral'}`}>
                        {t(row.active ? 'Ishda' : 'Ro‘yxatdan olingan')}
                      </span>
                    </td>
                    <td>
                      <div className="staff-actions">
                        <button className="table-action" title={t('Tahrirlash')} onClick={() => startEdit(row)}>
                          <Pencil size={15} />
                        </button>
                        {row.active && (
                          <button className="table-action" title={t('Ro‘yxatdan olish')} onClick={() => remove(row)}>
                            <Trash2 size={15} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!rows.length && (
              <div className="empty-state">
                <ConciergeBell size={38} strokeWidth={1.3} />
                <h3>{t('Ofitsiantlar hali qo‘shilmagan')}</h3>
                <p>{t('Qo‘shilgach kassir ularni hisobga bog‘lay oladi.')}</p>
              </div>
            )}
          </div>
        )}
      </section>

      <AppModal
        open={!!paying}
        title={t('{name} · pul berish', { name: paying?.name || '' })}
        onClose={() => { if (!busy) setPaying(undefined) }}
      >
        <form onSubmit={payWaiter}>
          <div className="salary-amount">{money(payForm.amount || 0)} <small>{t('so‘m')}</small></div>
          {!!paying && (
            <p className="alert">
              {t('Yig‘ilgan xizmat haqi {earned} so‘m, berilgani {paid} so‘m. Qoldiq: {balance} so‘m.', {
                earned: money(paying.earned), paid: money(paying.paid), balance: money(paying.balance),
              })}
            </p>
          )}
          <div className="form-row">
            <label>
              {t('Summa')}
              <input
                value={payForm.amount}
                onChange={event => setPayForm({ ...payForm, amount: event.target.value })}
                type="number"
                min="1"
                step="any"
                required
                autoFocus
              />
            </label>
            <label>
              {t('To‘lov sanasi')}
              <input
                value={payForm.paid_on}
                onChange={event => setPayForm({ ...payForm, paid_on: event.target.value })}
                type="date"
                max={today()}
                required
              />
            </label>
          </div>
          <label>
            {t('To‘lov usuli')}
            <select
              value={payForm.payment_method}
              onChange={event => setPayForm({ ...payForm, payment_method: event.target.value })}
            >
              <option value="cash">{t('Naqd')}</option>
              <option value="card">{t('Karta')}</option>
            </select>
          </label>
          <label>
            {t('Izoh')}
            <textarea
              value={payForm.note}
              onChange={event => setPayForm({ ...payForm, note: event.target.value })}
              maxLength={250}
              rows={2}
              placeholder={t('Masalan, haftalik hisob-kitob')}
            />
          </label>
          <p className="data-note">
            {t('Bu pul mijozdan ofitsiant nomiga yig‘ilgan — restoran xarajati emas, shuning uchun foydaga ta’sir qilmaydi. Naqd berilsa kassadan chiqadi.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('Pulni berildi deb yozish')}
          </button>
        </form>
      </AppModal>

      <AppModal
        open={open}
        title={editing ? t('Ofitsiantni tahrirlash') : t('Yangi ofitsiant')}
        onClose={() => { if (!busy) setOpen(false) }}
      >
        <form onSubmit={save}>
          <label>
            {t('Ism')}
            <input
              value={form.name}
              onChange={event => update({ name: event.target.value })}
              required
              maxLength={80}
              placeholder={t('Masalan, Fazliddin')}
            />
          </label>
          <div className="form-row">
            <label>
              {t('Telefon')}
              <input
                value={form.phone}
                onChange={event => update({ phone: event.target.value })}
                maxLength={20}
                placeholder="+998"
              />
            </label>
            <label>
              {t('Ulushi, %')}
              <input
                value={form.commission}
                onChange={event => update({ commission: event.target.value })}
                type="number"
                min="0"
                max="100"
                step="0.01"
                required
              />
            </label>
          </div>
          {editing && (
            <label className="checkbox">
              <input
                checked={form.active}
                onChange={event => update({ active: event.target.checked })}
                type="checkbox"
              />
              {t('Ishda')}
            </label>
          )}
          <p className="alert">
            {t('Foiz hisob ochilganda o‘sha paytdagi qiymatda muzlatiladi — keyin o‘zgartirsangiz eski hisobotlar o‘zgarmaydi.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : editing ? t('O‘zgarishni saqlash') : t('Ofitsiantni qo‘shish')}
          </button>
        </form>
      </AppModal>
    </>
  )
}
