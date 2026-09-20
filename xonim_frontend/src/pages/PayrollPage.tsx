import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle, Banknote, CalendarDays, Check, ChevronLeft, ChevronRight,
  Coffee, History, RefreshCw, Users, Wallet, X,
} from 'lucide-react'
import { api, money, today as todayKey } from '../api'
import AppModal from '../components/AppModal'
import { useI18n } from '../i18n'
import { useSession } from '../session'
import { CardsSkeleton, TableSkeleton } from '../components/Skeleton'
import type { Payroll, PayrollEmployee } from '../types'

interface PayForm {
  key: string
  amount: string
  payment_method: string
  paid_on: string
  note: string
}

/** Kun kalitidan oldingi/keyingi haftani hisoblaydi. */
function shiftWeek(start: string, days: number) {
  const date = new Date(`${start}T00:00:00`)
  date.setDate(date.getDate() + days)
  return date.toISOString().slice(0, 10)
}

export default function PayrollPage() {
  const { t, tn } = useI18n()
  // Xodimlar bo'limi faqat superadminniki: kassirga havola ko'rsatilsa,
  // bosgan zahoti uni Kassaga qaytarib yuborardi.
  const { user } = useSession()
  const owner = user?.role === 'owner'
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<Payroll>()
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(0)
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [selected, setSelected] = useState<PayrollEmployee>()
  const [payOpen, setPayOpen] = useState(false)
  const [payForm, setPayForm] = useState<PayForm>({
    key: '', amount: '', payment_method: 'cash', paid_on: todayKey(), note: '',
  })
  const week = params.get('week') || ''
  const month = params.get('month') || ''

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const query = new URLSearchParams()
      if (week) query.set('week', week)
      if (month) query.set('month', month)
      setData(await api<Payroll>(`payroll/${query.toString() ? `?${query}` : ''}`))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setLoading(false)
    }
  }, [week, month])

  useEffect(() => {
    load()
  }, [load])

  /** Davomatni belgilaydi. Server to'liq manzarani qaytaradi — qayta so'rov shart emas. */
  async function mark(rows: { employee: number; present: boolean }[], day: string) {
    setBusy(rows.length === 1 ? rows[0].employee : -1)
    setError('')
    try {
      setData(await api<Payroll>('attendance/', {
        method: 'POST',
        body: JSON.stringify({ date: day, rows }),
      }))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setBusy(0)
    }
  }

  function startPay(row: PayrollEmployee) {
    setSelected(row)
    setPayForm({
      // Kalit shu yerda tug'iladi: takroriy bosish ikki marta pul bermaydi.
      key: crypto.randomUUID(),
      amount: Number(row.balance) > 0 ? row.balance : '',
      payment_method: 'cash',
      paid_on: todayKey(),
      note: '',
    })
    setFormError('')
    setPayOpen(true)
  }

  async function pay(event: FormEvent) {
    event.preventDefault()
    if (!selected) return
    setBusy(selected.id)
    setFormError('')
    try {
      await api(`staff/${selected.id}/salary-payments/`, {
        method: 'POST',
        body: JSON.stringify(payForm),
      })
      setPayOpen(false)
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(0)
    }
  }

  const rows = (data?.employees || []).filter(row => row.active)
  const left = (data?.employees || []).filter(row => !row.active && Number(row.balance) !== 0)
  const maxTrend = Math.max(1, ...(data?.trend.map(point => Number(point.total)) || [1]))

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('DAVOMAT VA ISH HAQI')}</span>
          <h1>{t('Ish haqi')}<span className="heading-dot">.</span></h1>
          <p>{t('Kim keldi, kimga qancha yig‘ildi va kimga qancha berildi.')}</p>
        </div>
        <div className="heading-actions">
          {owner && <Link to="/staff" className="button secondary"><Users size={17} />{t('Xodimlar')}</Link>}
          <button className="button secondary" disabled={loading} onClick={() => load()}>
            <RefreshCw size={17} className={loading ? 'spin' : undefined} />{t('Yangilash')}
          </button>
        </div>
      </div>

      {error && <p className="alert error">{error}</p>}

      {!data && (
        <>
          <CardsSkeleton />
          <section className="panel"><TableSkeleton rows={4} columns={6} /></section>
        </>
      )}

      {data && (
        <>
          <div className="report-metrics">
            <article>
              <span className="metric-icon blue"><Users /></span>
              <div>
                <small>{t('Bugun ishda')}</small>
                <strong>{data.summary.present_today} / {data.summary.staff_count}</strong>
                <em>
                  {data.rest_day
                    ? t('Yakshanba — dam olish kuni')
                    : data.summary.unmarked_today
                      ? tn('{count} ta xodim hali belgilanmagan', data.summary.unmarked_today)
                      : t('Hammasi belgilangan')}
                </em>
              </div>
            </article>
            <article>
              <span className="metric-icon green"><CalendarDays /></span>
              <div>
                <small>{t('Shu haftada yig‘ildi')}</small>
                <strong>{money(data.summary.week_earned)} <em>{t('so‘m')}</em></strong>
                <em>{t('to‘liq hafta {amount}', { amount: money(data.summary.week_wage) })}</em>
              </div>
            </article>
            <article>
              <span className={`metric-icon ${Number(data.summary.balance) > 0 ? 'orange' : 'green'}`}>
                <AlertTriangle />
              </span>
              <div>
                <small>{t('Berilishi kerak')}</small>
                <strong>{money(data.summary.balance)} <em>{t('so‘m')}</em></strong>
                <em>{t('yig‘ilgan haq − berilgan pul')}</em>
              </div>
            </article>
            <article>
              <span className="metric-icon violet"><History /></span>
              <div>
                <small>{t('Boshidan beri berilgan')}</small>
                <strong>{money(data.all_time.total)} <em>{t('so‘m')}</em></strong>
                <em>{tn('{count} ta to‘lov', data.all_time.payments)}</em>
              </div>
            </article>
          </div>

          {/* ── Bugungi davomat: kunning eng ko'p ishlatiladigan qismi ── */}
          <section className="panel spaced">
            <header className="panel-heading">
              <div>
                <h2><Check size={17} /> {t('Bugungi davomat')}</h2>
                <p>{t('Har bir kelgan kun xodimning balansiga kunlik haqini qo‘shadi')}</p>
              </div>
              {!data.rest_day && !!rows.length && (
                <button
                  className="button secondary"
                  disabled={busy !== 0}
                  onClick={() => mark(rows.map(row => ({ employee: row.id, present: true })), data.today)}
                >
                  <Check size={17} />{t('Hammasi keldi')}
                </button>
              )}
            </header>
            {data.rest_day ? (
              <div className="rest-day">
                <Coffee size={34} strokeWidth={1.4} />
                <h3>{t('Yakshanba — dam olish kuni')}</h3>
                <p>{t('Bu kunga haq hisoblanmaydi. Davomat ertadan davom etadi.')}</p>
              </div>
            ) : (
              <div className="attendance-rows">
                {rows.map(row => (
                  <div key={row.id} className={`attendance-row ${row.today || 'pending'}`}>
                    <div className="attendance-name">
                      <strong>{row.name}</strong>
                      <small>{t(row.role_label)} · {money(row.daily_wage)} {t('so‘m / kun')}</small>
                    </div>
                    <div className="attendance-buttons">
                      <button
                        type="button"
                        className={`attend yes${row.today === 'present' ? ' on' : ''}`}
                        disabled={busy !== 0}
                        onClick={() => mark([{ employee: row.id, present: true }], data.today)}
                      >
                        <Check size={18} />{t('Keldi')}
                      </button>
                      <button
                        type="button"
                        className={`attend no${row.today === 'absent' ? ' on' : ''}`}
                        disabled={busy !== 0}
                        onClick={() => mark([{ employee: row.id, present: false }], data.today)}
                      >
                        <X size={18} />{t('Kelmadi')}
                      </button>
                    </div>
                  </div>
                ))}
                {!rows.length && <div className="empty-state compact">{t('Bu filialda faol xodim yo‘q.')}</div>}
              </div>
            )}
          </section>

          {/* ── Hafta kesimi va balans ── */}
          <section className="panel">
            <header className="panel-heading">
              <div>
                <h2>{t('Hafta')}: {data.week.label}</h2>
                <p>{t('Olti kun ish, yakshanba dam olish. Belgilanmagan kun — bo‘sh katak.')}</p>
              </div>
              <div className="week-nav">
                <button
                  className="button secondary"
                  onClick={() => setParams({ week: shiftWeek(data.week.start, -7) }, { replace: true })}
                >
                  <ChevronLeft size={17} />{t('Oldingi')}
                </button>
                <button
                  className="button secondary"
                  disabled={data.week.current}
                  onClick={() => setParams(
                    data.week.current ? {} : { week: shiftWeek(data.week.start, 7) }, { replace: true },
                  )}
                >
                  {t('Keyingi')}<ChevronRight size={17} />
                </button>
              </div>
            </header>
            <div className="table-wrap">
              <table className="week-table">
                <thead>
                  <tr>
                    <th>{t('XODIM')}</th>
                    {data.week.days.map(day => (
                      <th key={day.date} className={`day${day.rest ? ' rest' : ''}${day.today ? ' now' : ''}`}>
                        {t(day.weekday)}
                        <small>{day.date.slice(8)}</small>
                      </th>
                    ))}
                    <th>{t('HAFTA')}</th><th>{t('BALANS')}</th><th>{t('AMAL')}</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(row => (
                    <tr key={row.id}>
                      <td>
                        <strong>{row.name}</strong>
                        <small>{money(row.daily_wage)} {t('so‘m / kun')}</small>
                      </td>
                      {row.week.map(day => (
                        <td key={day.date} className={`day-cell${day.rest ? ' rest' : ''}`}>
                          {/* O'tgan kunni ham shu yerdan tuzatish mumkin: unutilgan
                              kun kelasi haftagacha kutib turmasin. */}
                          {day.rest || day.future ? (
                            <span className={`mark ${day.rest ? 'rest' : 'none'}`}>
                              {day.rest ? '—' : ''}
                            </span>
                          ) : (
                            <button
                              type="button"
                              className={`mark tap ${day.present === true ? 'yes' : day.present === false ? 'no' : 'none'}`}
                              disabled={busy !== 0}
                              title={`${day.date} · ${t('bosib o‘zgartiring')}`}
                              onClick={() => mark([{ employee: row.id, present: day.present !== true }], day.date)}
                            >
                              {day.present === true ? <Check size={15} />
                                : day.present === false ? <X size={15} /> : ''}
                            </button>
                          )}
                        </td>
                      ))}
                      <td className="number">
                        <strong>{money(row.week_earned)}</strong>
                        <small>{tn('{count} kun', row.week_days)}</small>
                      </td>
                      <td className="number">
                        <strong className={Number(row.balance) > 0 ? 'owed' : undefined}>
                          {money(row.balance)}
                        </strong>
                        <small>{row.advance ? t('avans') : tn('{count} ish kuni', row.days_worked)}</small>
                      </td>
                      <td>
                        <button className="button primary small" disabled={busy !== 0} onClick={() => startPay(row)}>
                          <Banknote size={15} />{t('Pul berish')}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {left.map(row => (
                    <tr key={row.id} className="row-muted">
                      <td colSpan={8}>
                        <strong>{row.name}</strong> <small>{t('ishdan bo‘shagan')}</small>
                      </td>
                      <td className="number"><strong className="owed">{money(row.balance)}</strong></td>
                      <td>
                        <button className="button secondary small" onClick={() => startPay(row)}>
                          {t('Hisob-kitob')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!rows.length && !left.length && <div className="empty-state">{t('Bu filialda xodim yo‘q.')}</div>}
            </div>
            <p className="data-note">
              {t('Kunlik haq o‘zgartirilsa faqat keyingi kunlarga ta’sir qiladi — belgilangan kunlar o‘sha kundagi summa bilan qoladi.')}
            </p>
          </section>

          <div className="payroll-grid">
            <section className="panel">
              <header className="panel-heading">
                <div>
                  <h2>{t('{month} to‘lovlari', { month: data.month_label })}</h2>
                  <p>{tn('{count} ta to‘lov', data.summary.month_count)} · {money(data.summary.month_paid)} {t('so‘m')}</p>
                </div>
                <Wallet size={18} />
              </header>
              <div className="salary-history">
                {data.payments.map(item => (
                  <div key={item.id}>
                    <span>
                      <strong>{item.employee_name}</strong>
                      <small>{item.paid_on} · {t(item.payment_label)} · {item.actor_name}</small>
                    </span>
                    <strong>{money(item.amount)} {t('so‘m')}</strong>
                    {item.note && <p>{item.note}</p>}
                  </div>
                ))}
                {!data.payments.length && (
                  <div className="empty-state compact">{t('Bu oyda hali pul berilmagan.')}</div>
                )}
              </div>
            </section>

            <section className="panel">
              <header className="panel-heading">
                <div>
                  <h2>{t('Ish haqi tarixi')}</h2>
                  <p>{t('Oxirgi 12 oyda xodimlarga qancha pul berilgan')}</p>
                </div>
                <CalendarDays size={18} />
              </header>
              <div className="report-chart" role="img" aria-label={t('Ish haqi grafigi')}>
                {data.trend.map(point => (
                  <button
                    key={point.period}
                    className="report-bar"
                    title={`${point.label}: ${money(point.total)} ${t('so‘m')}`}
                    onClick={() => setParams({ month: point.period }, { replace: true })}
                  >
                    <div><span style={{ height: `${Number(point.total) / maxTrend * 100}%` }} /></div>
                    <small>{point.label}</small>
                  </button>
                ))}
                {!Number(data.all_time.total) && (
                  <p className="chart-empty">{t('Hali pul berilmagan')}</p>
                )}
              </div>
              <footer className="chart-footer">
                <span>{t('Ustunni bosing — o‘sha oy ochiladi')}</span>
                <Link to="/expenses" className="text-link">{t('Xarajatlarda ko‘rish')} →</Link>
              </footer>
            </section>
          </div>

          {!!data.summary.without_wage && (
            <p className="alert">
              {tn('{count} ta xodimning kunlik haqi kiritilmagan — ularga haq yig‘ilmaydi.', data.summary.without_wage)}
              {owner && <> <Link to="/staff" className="text-link">{t('Xodimlar bo‘limi')} →</Link></>}
            </p>
          )}
        </>
      )}

      <AppModal
        open={payOpen}
        title={t('{name} · pul berish', { name: selected?.name || '' })}
        onClose={() => { if (!busy) setPayOpen(false) }}
      >
        <form onSubmit={pay}>
          <div className="salary-amount">{money(payForm.amount || 0)} <small>{t('so‘m')}</small></div>
          {!!selected && (
            <p className="alert">
              {selected.advance
                ? t('Bu xodimga {amount} so‘m avans berilgan — yangi to‘lov uning ustiga qo‘shiladi', {
                  amount: money(Math.abs(Number(selected.balance))),
                })
                : t('Hozirgi qarz: {amount} so‘m · {days} ish kuni yig‘ilgan', {
                  amount: money(selected.balance), days: selected.days_worked,
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
                step="1000"
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
                max={todayKey()}
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
            {t('To‘lov balansdan ayriladi va “Ish haqi” kategoriyasida xarajat yaratadi.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy !== 0}>
            {busy !== 0 ? t('Saqlanmoqda…') : t('Pulni berildi deb yozish')}
          </button>
        </form>
      </AppModal>
    </>
  )
}
