import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { AlertTriangle, CheckCircle2, CreditCard, Lock, Scale, Wallet } from 'lucide-react'
import { api, dateLabel, money, today } from '../api'
import { useSession } from '../session'
import type { ShiftDay, ShiftHistory } from '../types'

export default function ShiftClosePanel() {
  const { user } = useSession()
  const manager = user?.role === 'owner' || user?.role === 'admin'
  const [day, setDay] = useState<ShiftDay>()
  const [history, setHistory] = useState<ShiftHistory>()
  const [counted, setCounted] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      setDay(await api<ShiftDay>('shift/'))
      if (manager) setHistory(await api<ShiftHistory>('shift/history/'))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [manager])

  useEffect(() => {
    load()
  }, [load])

  async function close(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      await api('shift/', { method: 'POST', body: JSON.stringify({ counted_cash: counted || '0', note }) })
      setCounted('')
      setNote('')
      await load()
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!day) return null

  // Kassada qoladigan pul bilan hisobga tushadigani ajratib ko'rsatiladi:
  // kassir faqat birinchisini sanaydi.
  const inDrawer = day.breakdown.filter(row => row.in_drawer)
  const toAccount = day.breakdown.filter(row => !row.in_drawer)

  // Kassir yozayotgan raqamdan farqni darhol ko'rsatamiz — xato shu yerda bilinadi.
  const gap = counted === '' ? null : Number(counted) - Number(day.expected_cash)
  const big = gap !== null && Math.abs(gap) > Number(day.alert_som)

  return (
    <>
      <section className={`panel spaced${day.closed && day.alert ? ' warn-panel' : ''}`}>
        <header className="panel-heading">
          <div>
            <h2>
              {day.closed ? <Lock size={17} /> : <Wallet size={17} />} Kun yakuni
            </h2>
            <p>
              {day.closed
                ? `${day.date} yopilgan · ${day.actor}${day.closed_at ? ` · ${dateLabel(day.closed_at)}` : ''}`
                : 'Kassadagi naqd pulni sanang va tizim hisobi bilan solishtiring'}
            </p>
          </div>
          <span className="pill subtle">{day.date === today() ? 'Bugun' : day.date}</span>
        </header>

        <div className="shift-grid">
          <div>
            <small>Kassada bo‘lishi kerak</small>
            <strong>{money(day.expected_cash)}</strong>
            <em>
              {day.closed
                ? 'yopilish paytida muzlatilgan'
                : `naqd savdo ${money(day.cash_in || 0)} − naqd xarajat ${money(day.cash_out || 0)}`}
            </em>
          </div>
          <div>
            <small>Kunlik savdo</small>
            <strong>{money(day.revenue)}</strong>
            <em>{day.orders} ta chek</em>
          </div>
          {day.closed ? (
            <div>
              <small>Sanaldi</small>
              <strong>{money(day.counted_cash || 0)}</strong>
              <em className={day.alert ? 'owed' : undefined}>
                farq {Number(day.difference) > 0 ? '+' : ''}{money(day.difference || 0)} so‘m
              </em>
            </div>
          ) : (
            <div>
              <small>Ochiq hisoblar</small>
              <strong>{day.open_orders ?? 0}</strong>
              <em>
                {day.open_orders
                  ? 'avval ularni yopish kerak — pul hali kassaga tushmagan'
                  : 'hammasi yopilgan'}
              </em>
            </div>
          )}
        </div>

        {!!day.breakdown.length && (
          <div className="drawer-split">
            <div className="drawer-side counted">
              <header><Wallet size={15} />Kassada — sanaladi</header>
              {inDrawer.map(row => (
                <p key={row.method}><span>{row.label}</span><b>{money(row.amount)}</b></p>
              ))}
              {!inDrawer.length && <p className="muted">Naqd savdo bo‘lmagan</p>}
              {Number(day.cash_out || 0) > 0 && (
                <p className="outflow"><span>Naqd xarajat</span><b>−{money(day.cash_out || 0)}</b></p>
              )}
            </div>
            <div className="drawer-side">
              <header><CreditCard size={15} />Hisobga tushgan — sanalmaydi</header>
              {toAccount.map(row => (
                <p key={row.method}><span>{row.label}</span><b>{money(row.amount)}</b></p>
              ))}
              {!toAccount.length && <p className="muted">Karta orqali savdo bo‘lmagan</p>}
              <small>Bu pul kassada yotmaydi — provayder hisobiga tushadi.</small>
            </div>
          </div>
        )}

        {day.closed ? (
          <>
            {day.note && <p className="data-note">Izoh: {day.note}</p>}
            <p className="alert success">
              <CheckCircle2 size={16} />
              Bu kun yopilgan. Raqamlar muzlatilgan — keyingi savdolar bu hisobga ta’sir qilmaydi.
            </p>
          </>
        ) : (
          <form onSubmit={close} className="shift-form">
            <label>
              Kassadagi naqd pul, so‘m
              <small className="field-hint">Faqat qutidagi naqd — karta puli hisobga kirmaydi</small>
              <input
                value={counted}
                onChange={event => setCounted(event.target.value)}
                type="number"
                min="0"
                step="1"
                required
                placeholder="Sanab chiqing"
              />
            </label>
            <label>
              Izoh (ixtiyoriy)
              <input
                value={note}
                onChange={event => setNote(event.target.value)}
                maxLength={250}
                placeholder="Masalan, kechqurun avans berildi"
              />
            </label>
            <div className="shift-gap">
              {gap === null
                ? <span className="muted">Raqamni yozing — farq shu yerda chiqadi</span>
                : (
                  <>
                    <span>Farq</span>
                    <strong className={big ? 'owed' : undefined}>
                      {gap > 0 ? '+' : ''}{money(gap)} so‘m
                    </strong>
                    {big && <small className="owed">Farq katta — qayta sanang</small>}
                  </>
                )}
            </div>
            <button className="button primary" disabled={busy}>
              <Lock size={16} />{busy ? 'Yopilmoqda…' : 'Kunni yopish'}
            </button>
          </form>
        )}
        {error && <p className="alert error">{error}</p>}
      </section>

      {manager && history && !!history.days.length && (
        <section className="panel spaced">
          <header className="panel-heading">
            <div>
              <h2><Scale size={17} /> Yopilgan kunlar</h2>
              <p>
                {history.summary.closed_days} kun · umumiy farq{' '}
                <strong>{money(history.summary.total_difference)} so‘m</strong>
                {history.summary.alerts > 0 && ` · ${history.summary.alerts} kunda katta farq`}
              </p>
            </div>
            {history.summary.alerts > 0 && <AlertTriangle size={18} />}
          </header>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>KUN</th><th>SAVDO</th><th>KUTILGAN NAQD</th><th>SANALDI</th><th>FARQ</th><th>YOPGAN</th></tr>
              </thead>
              <tbody>
                {history.days.map(row => (
                  <tr key={row.date}>
                    <td><strong>{row.date}</strong>{row.note && <small>{row.note}</small>}</td>
                    <td className="number">{money(row.revenue)}</td>
                    <td className="number">{money(row.expected_cash)}</td>
                    <td className="number">{money(row.counted_cash || 0)}</td>
                    <td className="number">
                      <span className={row.alert ? 'owed' : undefined}>
                        {Number(row.difference) > 0 ? '+' : ''}{money(row.difference || 0)}
                      </span>
                    </td>
                    <td>{row.actor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </>
  )
}
