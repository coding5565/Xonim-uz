import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ArrowDownLeft, ArrowRight, ArrowUpRight, Info, Package, Plus, ReceiptText, RefreshCw, TrendingUp, Wallet, PiggyBank,
} from 'lucide-react'
import { api, dateLabel, money } from '../api'
import { useI18n } from '../i18n'
import { CardsSkeleton, ChartSkeleton, PanelSkeleton } from '../components/Skeleton'
import { useSession } from '../session'
import type { Dashboard } from '../types'

const palette = ['#22795f', '#d6aa6a', '#8fae9f', '#8e99bd']

type Translate = (text: string, vars?: Record<string, string | number>) => string

const monthNames = [
  'Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun',
  'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr',
]

/** '2026-09' -> 'Sentabr 2026' */
function monthLabel(value: string, t: Translate) {
  const [year, month] = value.split('-')
  return `${t(monthNames[Number(month) - 1])} ${year}`
}

/** A period is either a day count ('7', '30') or a month ('2026-09'). */
const isMonth = (period: string) => period.includes('-')

export default function DashboardPage() {
  const { t, tn } = useI18n()
  const { user } = useSession()
  const [data, setData] = useState<Dashboard>()
  const [period, setPeriod] = useState('7')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const query = isMonth(period) ? `month=${period}` : `days=${period}`
      setData(await api<Dashboard>(`dashboard/?${query}`))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setLoading(false)
    }
  }, [period])

  useEffect(() => {
    load()
  }, [load])

  const max = Math.max(1, ...(data?.trend.flatMap(point => [Number(point.revenue), Number(point.expenses)]) || [1]))
  const totalExpense = Number(data?.expenses || 0)
  const maxMethod = Math.max(1, ...(data?.by_method.map(row => Number(row.revenue)) || [1]))

  function growth() {
    if (!data) return '—'
    const monthly = data.period.kind === 'month'
    const previous = Number(data.previous_revenue)
    if (!previous) return monthly ? t('Oldingi oyda tushum yo‘q') : t('Oldingi davrda tushum yo‘q')
    const change = ((Number(data.revenue) - previous) / previous * 100).toFixed(1)
    return monthly
      ? t('{change}% oldingi oyga', { change })
      : t('{change}% oldingi davrga', { change })
  }

  // Rang ma'noga bog'langan: yashil — pul kirdi, iliq — pul chiqdi,
  // natija kartasi esa musbat yoki manfiyligiga qarab rang oladi.
  const tiles = data ? [
    { name: 'Jami tushum', value: data.revenue, icon: Wallet, color: 'green', tone: 'in', note: growth() },
    { name: 'Kiritilgan xarajat', value: data.expenses, icon: ArrowDownLeft, color: 'orange', tone: 'out', note: t('To‘langan va to‘lanmagan') },
    { name: 'Sof pul oqimi', value: data.net_cash, icon: TrendingUp, color: 'green', tone: Number(data.net_cash) < 0 ? 'hero-down' : 'hero', note: t('Kirim − to‘langan xarajat − ombor xaridi') },
    { name: 'To‘langan cheklar', value: data.paid_count, icon: ReceiptText, color: 'violet', tone: 'flat', note: tn('{count} ta ochiq hisob', Number(data.open_count)), count: true },
  ] : []

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('RESTORAN PULSI')}</span>
          <h1>{t('Umumiy holat')}<span className="heading-dot">.</span></h1>
          <p>{t('Salom, {name}. Restoraningizdagi muhim raqamlar shu yerda.', { name: user?.name ?? '' })}</p>
        </div>
        <div className="heading-actions">
          <button className="button secondary icon-button" disabled={loading} aria-label={t('Yangilash')} onClick={load}>
            <RefreshCw size={17} />
          </button>
          <select value={period} onChange={event => setPeriod(event.target.value)} aria-label={t('Hisobot davri')}>
            <option value="7">{t('Oxirgi 7 kun')}</option>
            <option value="30">{t('Oxirgi 30 kun')}</option>
            {!!data?.months.length && (
              <optgroup label={t('Oylar')}>
                {data.months.map(month => (
                  <option key={month} value={month}>{monthLabel(month, t)}</option>
                ))}
              </optgroup>
            )}
          </select>
          <Link to="/finance" className="button secondary"><PiggyBank size={17} />{t('Umumiy moliya')}</Link>
          <Link to="/pos" className="button primary"><Plus size={17} />{t('Yangi buyurtma')}</Link>
        </div>
      </div>
      {error && <p className="alert error" role="alert">{error}</p>}
      {!data && loading && <div className="empty-state">{t('Hisobot yuklanmoqda…')}</div>}
      {!data && (
        <>
          <CardsSkeleton />
          <div className="dashboard-grid">
            <section className="panel"><ChartSkeleton /></section>
            <section className="panel"><PanelSkeleton /></section>
          </div>
        </>
      )}
      {data && (
        <>
          <div className="metric-grid">
            {tiles.map(tile => {
              const Icon = tile.icon
              return (
                <article key={tile.name} className={`metric-card tone-${tile.tone}`}>
                  <div className="metric-top">
                    <span>{t(tile.name)}</span>
                    <span className={`metric-icon ${tile.color}`}><Icon size={19} /></span>
                  </div>
                  <div className="metric-value">{money(tile.value)}<small>{tile.count ? t('ta') : t('so‘m')}</small></div>
                  <p>{tile.note}</p>
                </article>
              )
            })}
          </div>
          <div className="dashboard-grid">
            <section className="panel revenue-panel">
              <header className="panel-heading">
                <div>
                  <h2>{t('Tushum va xarajatlar')}</h2>
                  <p>{data.period.start} — {data.period.end} · {t('kunlar bo‘yicha')}</p>
                </div>
                <span className="pill subtle">
                  {isMonth(period) ? monthLabel(period, t) : tn('{count} kun', Number(period))}
                </span>
              </header>
              <div className="chart-legend">
                <span><i className="green-dot" />{t('Tushum')}</span>
                <span><i className="orange-dot" />{t('Xarajat')}</span>
                <small>{t('so‘m')}</small>
              </div>
              <div className="bar-chart" role="img" aria-label={t('Kunlik tushum va xarajatlar grafigi')}>
                <div className="chart-grid-lines">
                  <span>{money(max)}</span><span>{money(max / 2)}</span><span>0</span>
                </div>
                <div className="bar-groups">
                  {data.trend.map(point => (
                    <div
                      key={point.date}
                      className="bar-group"
                      title={t('{date}: tushum {revenue}, xarajat {expenses}', {
                        date: point.date,
                        revenue: money(point.revenue),
                        expenses: money(point.expenses),
                      })}
                    >
                      <div className="bars">
                        <span className="revenue-bar" style={{ height: `${Number(point.revenue) / max * 100}%` }} />
                        <span className="expense-bar" style={{ height: `${Number(point.expenses) / max * 100}%` }} />
                      </div>
                      <small>{point.date.slice(8)}</small>
                    </div>
                  ))}
                </div>
                {max === 1 && <div className="chart-empty">{t('Birinchi savdongizdan keyin grafik shakllanadi')}</div>}
              </div>
              <footer className="chart-footer">
                <span><Info size={14} />{t('Faqat tizimga kiritilgan ma’lumotlar')}</span>
                <Link to="/orders">{t('Buyurtmalar')} <ArrowRight size={15} /></Link>
              </footer>
            </section>
            <section className="panel">
              <header className="panel-heading">
                <div><h2>{t('Xarajatlar tarkibi')}</h2><p>{t('Pul nimaga sarflandi?')}</p></div>
                <Link to="/expenses" className="icon-button" aria-label={t('Xarajatlarni ochish')}><ArrowUpRight size={20} /></Link>
              </header>
              <div className="expense-total">{money(data.expenses)} <small>{t('so‘m')}</small></div>
              {!data.expense_categories.length ? (
                <div className="empty-state compact">
                  <Wallet size={36} strokeWidth={1.3} />
                  <strong>{t('Hali xarajat kiritilmagan')}</strong>
                  <span>{t('Yangi xarajat shu yerda aks etadi.')}</span>
                  <Link to="/expenses" className="text-link">{t('Xarajat qo‘shish')} →</Link>
                </div>
              ) : data.expense_categories.map((item, index) => (
                <Link key={item.category} to="/expenses" className="expense-category">
                  <div>
                    <span><i style={{ background: palette[index % palette.length] }} />{item.category}</span>
                    <strong>{money(item.total)}</strong>
                  </div>
                  <div className="progress-track">
                    <span style={{ width: `${Number(item.total) / totalExpense * 100}%` }} />
                  </div>
                </Link>
              ))}
            </section>
          </div>
          <section className="panel spaced">
            <header className="panel-heading">
              <div><h2>{t('To‘lov turlari')}</h2><p>{t('Tanlangan davrda pul qaysi yo‘l bilan tushdi')}</p></div>
              <span className="pill subtle">{t('Jami {amount} so‘m', { amount: money(data.revenue) })}</span>
            </header>
            {data.by_method.length ? (
              <div className="category-ranking">
                {data.by_method.map(row => (
                  <div key={row.method}>
                    <div>
                      <strong>{t(row.label)}</strong>
                      <span>
                        {Number(data.revenue)
                          ? t('{percent}% umumiy tushumdan', {
                            percent: (Number(row.revenue) / Number(data.revenue) * 100).toFixed(1),
                          })
                          : '—'}
                      </span>
                      <b>{money(row.revenue)} {t('so‘m')}</b>
                    </div>
                    <div className="progress-track">
                      <span style={{ width: `${Number(row.revenue) / maxMethod * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state compact">{t('Tanlangan davrda to‘lov qayd etilmagan.')}</div>
            )}
          </section>
          <div className="dashboard-bottom">
            <section className="panel">
              <header className="panel-heading">
                <div><h2>{t('So‘nggi buyurtmalar')}</h2><p>{t('Tanlangan davrdagi oxirgi harakatlar')}</p></div>
                <Link to="/orders" className="text-link">{t('Barchasi')} <ArrowRight size={15} /></Link>
              </header>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>{t('BUYURTMA')}</th><th>{t('VAQT')}</th><th>{t('SUMMA')}</th><th>{t('HOLAT')}</th></tr></thead>
                  <tbody>
                    {data.recent_orders.map(order => (
                      <tr key={order.id}>
                        <td>
                          <strong>#{String(order.id).padStart(4, '0')}</strong>
                          <small>{order.table ? t('{table}-stol', { table: order.table }) : t('Tezkor savdo')}</small>
                        </td>
                        <td>{dateLabel(order.created_at)}</td>
                        <td className="number">{money(order.total)}</td>
                        <td>
                          <span className={`status ${order.status}`}>
                            {order.status === 'paid' ? t('To‘langan') : t('Ochiq hisob')}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!data.recent_orders.length && (
                  <div className="empty-state compact">{t('Tanlangan davrda buyurtma qayd etilmagan.')}</div>
                )}
              </div>
            </section>
            <section className="insight-card">
              <span className="insight-icon"><Package size={23} /></span>
              <span className="eyebrow">{t('BUGUNGI NAZORAT')}</span>
              <h2>{t('Har bir mahsulot')}<br />{t('hisobda bo‘lsin.')}</h2>
              <p>
                {data.low_stock
                  ? tn('{count} ta mahsulot minimal qoldiqqa yetgan. Kirimni tekshiring.', Number(data.low_stock))
                  : t('Kun oxirida haqiqiy sarfni kiritib, ombor qoldig‘ini yangilang.')}
              </p>
              <Link to="/inventory" className="button">{t('Omborni ko‘rish')} <ArrowUpRight size={17} /></Link>
            </section>
          </div>
          <p className="data-note">
            <Info size={15} />{t(data.basis)} {t('Yangilandi: {date}.', { date: dateLabel(data.as_of) })}
          </p>
        </>
      )}
    </>
  )
}
