import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, CalendarDays, Coins, Filter, PackageSearch, TrendingDown } from 'lucide-react'
import { api, money, today } from '../api'
import type { Ingredient, StockUsage } from '../types'

interface Props {
  ingredients: Ingredient[]
  /** Manzil satridagi filtrlar — sahifalararo havolalar shu orqali ishlaydi. */
  filters: { start: string; end: string; ingredient: string }
  onChange: (patch: Partial<Props['filters']>) => void
}

function shiftDate(value: string, days: number) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10)
}

export default function StockUsagePanel({ ingredients, filters, onChange }: Props) {
  const [data, setData] = useState<StockUsage>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const query = `start=${filters.start}&end=${filters.end}${filters.ingredient ? `&ingredient=${filters.ingredient}` : ''}`

  const load = useCallback(async (search: string) => {
    setLoading(true)
    setError('')
    try {
      setData(await api<StockUsage>(`stock/usage/?${search}`))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(query)
  }, [load, query])

  function preset(kind: 'today' | 'week' | 'month' | 'quarter') {
    const now = today()
    if (kind === 'today') return onChange({ start: now, end: now })
    if (kind === 'week') return onChange({ start: shiftDate(now, -6), end: now })
    if (kind === 'month') return onChange({ start: `${now.slice(0, 8)}01`, end: now })
    return onChange({ start: shiftDate(now, -89), end: now })
  }

  // Aralash birliklarda (kg + litr) miqdor jamlanmaydi, shuning uchun grafik
  // pul bo'yicha chiziladi.
  const mixed = !!data && !data.summary.unit
  const useValue = !!data && (mixed || Number(data.summary.used_value) > 0)
  const maxUsed = Math.max(1, ...(data?.series.map(row => Number(useValue ? row.used_value : row.used)) || [1]))

  return (
    <>
      <section className="panel report-filters">
        <header>
          <Filter size={19} />
          <div><h2>Davr</h2><p>Qaysi kundan qaysi kungacha qancha masalliq ketgani</p></div>
          <div className="report-presets">
            <button onClick={() => preset('today')}>Bugun</button>
            <button onClick={() => preset('week')}>7 kun</button>
            <button onClick={() => preset('month')}>Shu oy</button>
            <button onClick={() => preset('quarter')}>90 kun</button>
          </div>
        </header>
        <div className="report-filter-grid">
          <label>
            Boshlanish
            <input
              value={filters.start}
              onChange={event => onChange({ start: event.target.value })}
              type="date"
              max={filters.end}
            />
          </label>
          <label>
            Tugash
            <input
              value={filters.end}
              onChange={event => onChange({ end: event.target.value })}
              type="date"
              min={filters.start}
              max={today()}
            />
          </label>
          <label>
            Mahsulot
            <select value={filters.ingredient} onChange={event => onChange({ ingredient: event.target.value })}>
              <option value="">Barcha mahsulotlar</option>
              {ingredients.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
        </div>
      </section>

      {error && <p className="alert error">{error}</p>}

      {data && (
        <>
          <div className="report-metrics">
            <article>
              <span className="metric-icon orange"><TrendingDown /></span>
              <div>
                <small>Davrda sarflangan</small>
                <strong>{money(data.summary.used_value)} <em>so‘m</em></strong>
                <em>
                  {data.summary.days} kun · kuniga {money(data.summary.per_day_value)} so‘m
                  {data.summary.unit && ` · ${money(data.summary.used)} ${data.summary.unit}`}
                </em>
              </div>
            </article>
            <article>
              <span className="metric-icon blue"><PackageSearch /></span>
              <div>
                <small>Kirim qilingan</small>
                <strong>{money(data.summary.received_value)} <em>so‘m</em></strong>
                <em>{data.summary.moves} ta harakat</em>
              </div>
            </article>
            <article>
              <span className="metric-icon green"><Coins /></span>
              <div>
                <small>Hozirgi ombor qiymati</small>
                <strong>{money(data.summary.stock_value)} <em>so‘m</em></strong>
                <em>{data.summary.items_moved} ta mahsulot harakatda</em>
              </div>
            </article>
            <article>
              <span className={`metric-icon ${data.summary.unpriced_moves ? 'orange' : 'violet'}`}>
                <AlertTriangle />
              </span>
              <div>
                <small>Narxsiz harakatlar</small>
                <strong>{data.summary.unpriced_moves} <em>ta</em></strong>
                <em>{data.summary.unpriced_moves ? 'Bular so‘m hisobiga kirmaydi' : 'Hammasi narx bilan yozilgan'}</em>
              </div>
            </article>
          </div>

          <section className="panel">
            <header className="panel-heading">
              <div>
                <h2>Kunlik sarf</h2>
                <p>
                  {data.filters.group === 'month' ? 'Oylar bo‘yicha' : 'Kunlar bo‘yicha'} ·{' '}
                  {useValue ? 'so‘m hisobida' : `miqdor hisobida (${data.summary.unit})`}
                </p>
              </div>
              <CalendarDays size={18} />
            </header>
            <div className="report-chart" role="img" aria-label="Masalliq sarfi grafigi">
              {data.series.map(point => (
                <div
                  key={point.date}
                  className="report-bar"
                  title={point.used
                    ? `${point.label}: ${money(point.used_value)} so‘m · ${point.used} sarflandi, ${point.received} kirim`
                    : `${point.label}: ${money(point.used_value)} so‘m sarflandi, ${money(point.received_value)} so‘m kirim`}
                >
                  <div>
                    <span style={{ height: `${(Number(useValue ? point.used_value : point.used) / maxUsed) * 100}%` }} />
                  </div>
                  <small>{point.label}</small>
                </div>
              ))}
              {!data.summary.moves && <p className="chart-empty">Bu davrda ombor harakati bo‘lmagan</p>}
            </div>
          </section>

          <section className="panel spaced">
            <header className="panel-heading">
              <div>
                <h2>Mahsulot bo‘yicha</h2>
                <p>Ochilish qoldig‘i, kirim, sarf va yopilish — eng ko‘p pul ketgani yuqorida</p>
              </div>
              <span className="pill subtle">{data.summary.items_moved} ta</span>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>MAHSULOT</th><th>OCHILISH</th><th>KIRIM</th><th>SARF</th><th>SARF SUMMASI</th>
                    <th>PUL ULUSHI</th><th>KUNIGA</th><th>YETADI</th><th>YOPILISH</th>
                  </tr>
                </thead>
                <tbody>
                  {data.ingredients.map(row => (
                    <tr key={row.id}>
                      <td>
                        <strong>{row.name}</strong>
                        <small>
                          {Number(row.unit_cost) ? `${money(row.unit_cost)} so‘m/${row.unit}` : 'narx yo‘q'}
                          {row.low ? ' · kam qolgan' : ''}
                        </small>
                      </td>
                      <td className="number">{money(row.opening)} {row.unit}</td>
                      <td className="number">{Number(row.received) ? `+${money(row.received)}` : '—'}</td>
                      <td className="number">
                        −{money(row.used)} {row.unit}
                        {Number(row.sold) > 0 && <small>sotuvdan {money(row.sold)}</small>}
                      </td>
                      <td className="number">{Number(row.used_value) ? `${money(row.used_value)} so‘m` : '—'}</td>
                      <td>
                        {row.share ? (
                          <>
                            <div className="share-cell"><span style={{ width: `${Math.min(100, Number(row.share))}%` }} /></div>
                            <small>{row.share}%</small>
                          </>
                        ) : <span className="muted">narxsiz</span>}
                      </td>
                      <td className="number">{money(row.per_day)} {row.unit}</td>
                      <td className="number">
                        {row.days_left
                          ? <span className={Number(row.days_left) <= 3 ? 'owed' : undefined}>{row.days_left} kun</span>
                          : '—'}
                      </td>
                      <td className="number">{money(row.closing)} {row.unit}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.ingredients.length && (
                <div className="empty-state">Bu davrda hech bir mahsulot harakat qilmagan.</div>
              )}
            </div>
          </section>

          {!!data.idle.length && (
            <section className="panel spaced">
              <header className="panel-heading">
                <div>
                  <h2>Harakatsiz mahsulotlar</h2>
                  <p>Bu davrda na kirim, na sarf bo‘lgan — retseptga ulanmagan bo‘lishi mumkin</p>
                </div>
                <Link to="/recipes" className="text-link">Retseptlarni ko‘rish →</Link>
              </header>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>MAHSULOT</th><th>QOLDIQ</th><th>TANNARX</th><th>QOLDIQ QIYMATI</th></tr></thead>
                  <tbody>
                    {data.idle.map(row => (
                      <tr key={row.id}>
                        <td><strong>{row.name}</strong></td>
                        <td className="number">{money(row.quantity)} {row.unit}</td>
                        <td className="number">{Number(row.unit_cost) ? `${money(row.unit_cost)} so‘m` : '—'}</td>
                        <td className="number">{Number(row.stock_value) ? `${money(row.stock_value)} so‘m` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          )}

          <p className="data-note">
            Sarf summasi harakat yozilgan paytdagi ombor tannarxida hisoblanadi, shuning uchun narx keyin
            o‘zgarsa ham eski hisobot o‘zgarmaydi. Kirimda narx yozilmagan bo‘lsa, o‘sha harakat so‘m
            hisobiga kirmaydi.
          </p>
        </>
      )}
      {loading && !data && <div className="empty-state">Hisoblanmoqda…</div>}
    </>
  )
}
