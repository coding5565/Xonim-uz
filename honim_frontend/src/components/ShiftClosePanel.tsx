import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { AlertTriangle, CheckCircle2, CreditCard, Lock, Scale, Wallet } from 'lucide-react'
import { api, dateLabel, money, today } from '../api'
import { useSession } from '../session'
import { useI18n } from '../i18n'
import type { ShiftDay, ShiftHistory } from '../types'

export default function ShiftClosePanel() {
  const { user } = useSession()
  const { t, tn } = useI18n()
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
              {day.closed ? <Lock size={17} /> : <Wallet size={17} />} {t('Kun yakuni')}
            </h2>
            <p>
              {day.closed
                ? `${t('{date} yopilgan', { date: day.date })} · ${day.actor}${day.closed_at ? ` · ${dateLabel(day.closed_at)}` : ''}`
                : t('Kassadagi naqd pulni sanang va tizim hisobi bilan solishtiring')}
            </p>
          </div>
          <span className="pill subtle">{day.date === today() ? t('Bugun') : day.date}</span>
        </header>

        <div className="shift-grid">
          <div>
            <small>{t('Kassada bo‘lishi kerak')}</small>
            <strong>{money(day.expected_cash)}</strong>
            <em>
              {day.closed
                ? t('yopilish paytida muzlatilgan')
                : t('naqd savdo {income} − naqd xarajat {outcome}', {
                  income: money(day.cash_in || 0),
                  outcome: money(day.cash_out || 0),
                })}
            </em>
          </div>
          <div>
            <small>{t('Kunlik savdo')}</small>
            <strong>{money(day.revenue)}</strong>
            <em>{tn('{count} ta chek', day.orders)}</em>
          </div>
          {day.closed ? (
            <div>
              <small>{t('Sanaldi')}</small>
              <strong>{money(day.counted_cash || 0)}</strong>
              <em className={day.alert ? 'owed' : undefined}>
                {t('farq {amount} so‘m', {
                  amount: `${Number(day.difference) > 0 ? '+' : ''}${money(day.difference || 0)}`,
                })}
              </em>
            </div>
          ) : (
            <div>
              <small>{t('Ochiq hisoblar')}</small>
              <strong>{day.open_orders ?? 0}</strong>
              <em>
                {day.open_orders
                  ? t('avval ularni yopish kerak — pul hali kassaga tushmagan')
                  : t('hammasi yopilgan')}
              </em>
            </div>
          )}
        </div>

        {!!day.breakdown.length && (
          <div className="drawer-split">
            <div className="drawer-side counted">
              <header><Wallet size={15} />{t('Kassada — sanaladi')}</header>
              {inDrawer.map(row => (
                <p key={row.method}><span>{row.label}</span><b>{money(row.amount)}</b></p>
              ))}
              {!inDrawer.length && <p className="muted">{t('Naqd savdo bo‘lmagan')}</p>}
              {Number(day.cash_out || 0) > 0 && (
                <p className="outflow"><span>{t('Naqd xarajat')}</span><b>−{money(day.cash_out || 0)}</b></p>
              )}
            </div>
            <div className="drawer-side">
              <header><CreditCard size={15} />{t('Hisobga tushgan — sanalmaydi')}</header>
              {toAccount.map(row => (
                <p key={row.method}><span>{row.label}</span><b>{money(row.amount)}</b></p>
              ))}
              {!toAccount.length && <p className="muted">{t('Karta orqali savdo bo‘lmagan')}</p>}
              <small>{t('Bu pul kassada yotmaydi — provayder hisobiga tushadi.')}</small>
            </div>
          </div>
        )}

        {day.closed ? (
          <>
            {day.note && <p className="data-note">{t('Izoh')}: {day.note}</p>}
            <p className="alert success">
              <CheckCircle2 size={16} />
              {t('Bu kun yopilgan. Raqamlar muzlatilgan — keyingi savdolar bu hisobga ta’sir qilmaydi.')}
            </p>
          </>
        ) : (
          <form onSubmit={close} className="shift-form">
            <label>
              {t('Kassadagi naqd pul, so‘m')}
              <small className="field-hint">{t('Faqat qutidagi naqd — karta puli hisobga kirmaydi')}</small>
              <input
                value={counted}
                onChange={event => setCounted(event.target.value)}
                type="number"
                min="0"
                step="1"
                required
                placeholder={t('Sanab chiqing')}
              />
            </label>
            <label>
              {t('Izoh (ixtiyoriy)')}
              <input
                value={note}
                onChange={event => setNote(event.target.value)}
                maxLength={250}
                placeholder={t('Masalan, kechqurun avans berildi')}
              />
            </label>
            <div className="shift-gap">
              {gap === null
                ? <span className="muted">{t('Raqamni yozing — farq shu yerda chiqadi')}</span>
                : (
                  <>
                    <span>{t('Farq')}</span>
                    <strong className={big ? 'owed' : undefined}>
                      {gap > 0 ? '+' : ''}{money(gap)} {t('so‘m')}
                    </strong>
                    {big && <small className="owed">{t('Farq katta — qayta sanang')}</small>}
                  </>
                )}
            </div>
            <button className="button primary" disabled={busy}>
              <Lock size={16} />{busy ? t('Yopilmoqda…') : t('Kunni yopish')}
            </button>
          </form>
        )}
        {error && <p className="alert error">{error}</p>}
      </section>

      {manager && history && !!history.days.length && (
        <section className="panel spaced">
          <header className="panel-heading">
            <div>
              <h2><Scale size={17} /> {t('Yopilgan kunlar')}</h2>
              <p>
                {tn('{count} kun', history.summary.closed_days)} · {t('umumiy farq')}{' '}
                <strong>{money(history.summary.total_difference)} {t('so‘m')}</strong>
                {history.summary.alerts > 0 && ` · ${tn('{count} kunda katta farq', history.summary.alerts)}`}
              </p>
            </div>
            {history.summary.alerts > 0 && <AlertTriangle size={18} />}
          </header>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{t('KUN')}</th><th>{t('SAVDO')}</th><th>{t('KUTILGAN NAQD')}</th>
                  <th>{t('SANALDI')}</th><th>{t('FARQ')}</th><th>{t('YOPGAN')}</th>
                </tr>
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
