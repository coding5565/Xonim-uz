import { useCallback, useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle, Banknote, CalendarDays, History, RefreshCw, Users, Wallet,
} from 'lucide-react'
import { api, money } from '../api'
import type { Payroll, PayrollEmployee } from '../types'

const STATUS_LABELS: Record<PayrollEmployee['status'], string> = {
  paid: 'To‘langan',
  partial: 'Qisman',
  unpaid: 'To‘lanmagan',
  // Oylik summasi kiritilmagan xodimni «to‘lanmagan» deb ko‘rsatish noto‘g‘ri.
  no_agreement: 'Oylik kiritilmagan',
}

/** Oy kalitini «2026-yil sentabr» ko‘rinishiga keltiradi. */
const MONTHS = [
  'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
  'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr',
]
const monthName = (key: string) => {
  const [year, month] = key.split('-')
  return `${year}-yil ${MONTHS[Number(month) - 1]}`
}

export default function PayrollPage() {
  // Oy manzil satrida turadi: «shu oyning oyliklari» havolasi ishlashi uchun.
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<Payroll>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const month = params.get('month') || ''

  const load = useCallback(async (wanted: string) => {
    setLoading(true)
    setError('')
    try {
      setData(await api<Payroll>(`payroll/${wanted ? `?month=${wanted}` : ''}`))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(month)
  }, [load, month])

  function pick(next: string) {
    setParams(next ? { month: next } : {}, { replace: true })
  }

  const rows = data?.employees || []
  const unpaid = rows.filter(row => row.active && row.status !== 'paid' && row.status !== 'no_agreement')
  const maxTrend = Math.max(1, ...(data?.trend.map(point => Number(point.total)) || [1]))

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">ISH HAQI NAZORATI</span>
          <h1>Oyliklar<span className="heading-dot">.</span></h1>
          <p>Kimga qancha kelishilgan, kimga qancha berilgan va oyiga qancha pul ketyapti.</p>
        </div>
        <div className="heading-actions">
          <select value={month} onChange={event => pick(event.target.value)} aria-label="Oyni tanlash">
            <option value="">Shu oy</option>
            {(data?.months || []).map(item => (
              <option key={item} value={item}>{monthName(item)}</option>
            ))}
          </select>
          <button className="button secondary" disabled={loading} onClick={() => load(month)}>
            <RefreshCw size={17} className={loading ? 'spin' : undefined} />Yangilash
          </button>
        </div>
      </div>

      {error && <p className="alert error">{error}</p>}

      {data && (
        <>
          <div className="report-metrics">
            <article>
              <span className="metric-icon blue"><Wallet /></span>
              <div>
                <small>Kelishilgan fond</small>
                <strong>{money(data.summary.agreed)} <em>so‘m</em></strong>
                <em>
                  {data.summary.staff_count} ta faol xodim
                  {data.summary.without_agreement > 0 && ` · ${data.summary.without_agreement} tasida oylik kiritilmagan`}
                </em>
              </div>
            </article>
            <article>
              <span className="metric-icon green"><Banknote /></span>
              <div>
                <small>To‘langan</small>
                <strong>{money(data.summary.paid)} <em>so‘m</em></strong>
                <em>{data.summary.covered} / {data.summary.expected} xodimga berilgan</em>
              </div>
            </article>
            <article>
              <span className={`metric-icon ${Number(data.summary.remaining) ? 'orange' : 'green'}`}>
                <AlertTriangle />
              </span>
              <div>
                <small>Qolgan qarz</small>
                <strong>{money(data.summary.remaining)} <em>so‘m</em></strong>
                <em>
                  {unpaid.length
                    ? `${unpaid.length} ta xodim kutmoqda`
                    : data.summary.expected ? 'Hamma bilan hisob-kitob qilingan' : 'Hali oylik kelishilmagan'}
                </em>
              </div>
            </article>
            <article>
              <span className="metric-icon violet"><History /></span>
              <div>
                <small>Boshidan beri to‘langan</small>
                <strong>{money(data.all_time.total)} <em>so‘m</em></strong>
                <em>{data.all_time.payments} ta to‘lov</em>
              </div>
            </article>
          </div>

          <section className="panel">
            <header className="panel-heading">
              <div>
                <h2>{data.month_label}</h2>
                <p>Kelishilgan summa xodim kartasidan, to‘langan summa haqiqiy to‘lovlardan olinadi</p>
              </div>
              <Link to="/staff" className="text-link">Xodimlar bo‘limi →</Link>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>XODIM</th><th>LAVOZIM</th><th>KELISHILGAN</th><th>TO‘LANGAN</th>
                    <th>FARQ</th><th>HOLAT</th><th>TO‘LOV</th><th>HARAKATLARI</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map(row => (
                    <tr key={row.id} className={row.active ? undefined : 'row-muted'}>
                      <td>
                        <strong>{row.name}</strong>
                        <small>{row.username}{row.active ? '' : ' · ishdan bo‘shagan'}</small>
                      </td>
                      <td><span className="pill subtle">{row.role_label}</span></td>
                      <td className="number">
                        {Number(row.agreed) ? `${money(row.agreed)} so‘m` : <span className="muted">kiritilmagan</span>}
                      </td>
                      <td className="number">{Number(row.paid) ? `${money(row.paid)} so‘m` : '—'}</td>
                      <td className="number">
                        {Number(row.difference) > 0
                          ? <span className="owed">{money(row.difference)} so‘m</span>
                          : '—'}
                      </td>
                      <td>
                        <span className={`status ${row.status === 'paid' ? 'paid' : row.status === 'no_agreement' ? 'neutral' : 'open'}`}>
                          {STATUS_LABELS[row.status]}
                        </span>
                      </td>
                      <td>
                        {row.paid_on
                          ? <>{row.paid_on}<small>{row.payment_label}</small></>
                          : <span className="muted">—</span>}
                      </td>
                      <td>
                        <Link to={`/activity?actor=${row.id}`} className="text-link">Jurnal →</Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!rows.length && <div className="empty-state">Bu filialda xodim yo‘q.</div>}
            </div>
          </section>

          <div className="payroll-grid">
            <section className="panel">
              <header className="panel-heading">
                <div><h2>Oylik fond tarixi</h2><p>Oxirgi 12 oyda ish haqiga qancha pul ketgan</p></div>
                <CalendarDays size={18} />
              </header>
              <div className="report-chart" role="img" aria-label="Oylik ish haqi grafigi">
                {data.trend.map(point => (
                  <button
                    key={point.period}
                    className="report-bar"
                    title={`${point.label}: ${money(point.total)} so‘m · ${point.count} ta to‘lov`}
                    onClick={() => pick(point.period)}
                  >
                    <div><span style={{ height: `${Number(point.total) / maxTrend * 100}%` }} /></div>
                    <small>{point.label}</small>
                  </button>
                ))}
                {!Number(data.all_time.total) && (
                  <p className="chart-empty">Hali oylik to‘lovi kiritilmagan</p>
                )}
              </div>
              <footer className="chart-footer">
                <span>Ustunni bosing — o‘sha oy ochiladi</span>
                <Link to="/expenses" className="text-link">Xarajatlarda ko‘rish →</Link>
              </footer>
            </section>

            <section className="panel">
              <header className="panel-heading">
                <div><h2>Kim jami qancha olgan</h2><p>Butun davr bo‘yicha</p></div>
                <Users size={18} />
              </header>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>XODIM</th><th>JAMI</th><th>OYLAR</th><th>DAVR</th></tr></thead>
                  <tbody>
                    {data.lifetime.map(row => (
                      <tr key={row.id}>
                        <td><strong>{row.name}</strong></td>
                        <td className="number">{money(row.total)} so‘m</td>
                        <td>{row.months} oy</td>
                        <td><small>{row.first} — {row.last}</small></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!data.lifetime.length && (
                  <div className="empty-state compact">Hali birorta oylik to‘lanmagan.</div>
                )}
              </div>
            </section>
          </div>

          {!!data.summary.by_method.length && (
            <p className="data-note">
              Bu oyda:&nbsp;
              {data.summary.by_method.map(row => `${row.label} ${money(row.amount)} so‘m (${row.count} ta)`).join(' · ')}.
              Har bir oylik to‘lovi «Ish haqi» kategoriyasida xarajat ham yaratadi, shuning uchun umumiy
              moliyada u xarajatlar ichida turadi — ustiga qo‘shilmaydi.
            </p>
          )}
        </>
      )}
    </>
  )
}
