import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Banknote, CalendarDays, Clock3, Filter, PackageCheck, ReceiptText, RefreshCw, Search, TrendingUp, UserRound, Wallet,
} from 'lucide-react'
import { api, dateLabel, list, money, today } from '../api'
import { useSession } from '../session'
import { useI18n } from '../i18n'
import ShiftClosePanel from '../components/ShiftClosePanel'
import type { Category, Dish, SalesBoard, SalesSummary } from '../types'

interface Filters {
  start: string
  end: string
  category: string
  dish: string
  mine: boolean
}

function queryFor(filters: Filters) {
  const query = new URLSearchParams({ start: filters.start, end: filters.end })
  if (filters.category) query.set('category', filters.category)
  if (filters.dish) query.set('dish', filters.dish)
  if (filters.mine) query.set('mine', 'true')
  return query.toString()
}

function shiftDate(value: string, days: number) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10)
}

const hourLabel = (hour: number) => `${String(hour).padStart(2, '0')}:00`

export default function SalesPage() {
  const { user } = useSession()
  const { t, tn } = useI18n()
  const [categories, setCategories] = useState<Category[]>([])
  const [dishes, setDishes] = useState<Dish[]>([])
  const [data, setData] = useState<SalesBoard>()
  const [summary, setSummary] = useState<SalesSummary>()
  // Moliya va hisobot sahifalaridan kelgan davr shu yerda qabul qilinadi.
  const [params] = useSearchParams()
  const [filters, setFilters] = useState<Filters>({
    start: params.get('start') || today(),
    end: params.get('end') || today(),
    category: params.get('category') || '',
    dish: params.get('dish') || '',
    mine: params.get('mine') === 'true',
  })
  const [dishQuery, setDishQuery] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  /** The live strip ignores the filters below: it always shows where the till stands right now. */
  const loadSummary = useCallback(async () => {
    try {
      setSummary(await api<SalesSummary>('sales/summary/'))
    } catch {
      setSummary(undefined)
    }
  }, [])

  /** Filters are passed in so a freshly clicked preset is not read from stale state. */
  async function load(next: Filters = filters) {
    setLoading(true)
    setError('')
    try {
      setData(await api<SalesBoard>(`sales/board/?${queryFor(next)}`))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    async function bootstrap() {
      try {
        const [loadedCategories, loadedDishes] = await Promise.all([
          list<Category>('categories/'),
          list<Dish>('dishes/'),
        ])
        setCategories(loadedCategories)
        setDishes(loadedDishes)
        await Promise.all([load(), loadSummary()])
      } catch (exception) {
        setError((exception as Error).message)
      }
    }
    bootstrap()
    // Runs once; later loads go through the filter controls.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function apply(patch: Partial<Filters>, reload = false) {
    const next = { ...filters, ...patch }
    setFilters(next)
    if (reload) load(next)
  }

  function preset(kind: 'today' | 'yesterday' | 'week' | 'month') {
    const now = today()
    if (kind === 'today') return apply({ start: now, end: now }, true)
    if (kind === 'yesterday') {
      const day = shiftDate(now, -1)
      return apply({ start: day, end: day }, true)
    }
    if (kind === 'week') return apply({ start: shiftDate(now, -6), end: now }, true)
    return apply({ start: now.slice(0, 8) + '01', end: now }, true)
  }

  const visibleDishes = dishes.filter(item => !filters.category || item.category === Number(filters.category))
  const maxHour = Math.max(1, ...(data?.hours.map(row => Number(row.revenue)) || [1]))
  const maxDay = Math.max(1, ...(data?.days.map(row => Number(row.revenue)) || [1]))
  const maxCategory = Math.max(1, ...(data?.categories.map(row => Number(row.revenue)) || [1]))
  const maxCashier = Math.max(1, ...(data?.cashiers.map(row => Number(row.revenue)) || [1]))
  const soldRows = data?.dishes.filter(row =>
    `${row.dish} ${row.category}`.toLocaleLowerCase().includes(dishQuery.toLocaleLowerCase()),
  ) || []
  const multiDay = !!data && data.filters.start !== data.filters.end

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">SAVDO NAZORATI</span>
          <h1>Sotuv<span className="heading-dot">.</span></h1>
          <p>Nima sotildi, qaysi soatda va qaysi kassa orqali — hammasi shu yerda.</p>
        </div>
        <button className="button secondary" disabled={loading} onClick={() => { load(); loadSummary() }}>
          <RefreshCw size={17} className={loading ? 'spin' : undefined} />Yangilash
        </button>
      </div>

      {summary && (
        <>
          <div className="sales-summary">
            <article>
              <Wallet size={21} />
              <div>
                <small>BUGUN</small>
                <strong>{money(summary.today.revenue)} so‘m</strong>
                <span>{summary.today.orders} ta chek</span>
              </div>
            </article>
            <article>
              <CalendarDays size={21} />
              <div>
                <small>KECHA</small>
                <strong>{money(summary.yesterday.revenue)} so‘m</strong>
                <span>{summary.yesterday.orders} ta chek</span>
              </div>
            </article>
            <article>
              <TrendingUp size={21} />
              <div>
                <small>OXIRGI 7 KUN</small>
                <strong>{money(summary.last_7_days.revenue)} so‘m</strong>
                <span>{summary.last_7_days.orders} ta chek</span>
              </div>
            </article>
            <article className="open">
              <ReceiptText size={21} />
              <div>
                <small>TO‘LOV KUTILMOQDA</small>
                <strong>{money(summary.open.revenue)} so‘m</strong>
                <span>{summary.open.orders} ta ochiq hisob</span>
              </div>
            </article>
          </div>
          <p className="sales-note">
            {summary.today_by_method.map(row => (
              <span key={row.method}>Bugun {row.label.toLocaleLowerCase()}: <b>{money(row.revenue)} so‘m</b></span>
            ))}
            <span>
              Sizning bugungi savdongiz: <b>{money(summary.mine_today.revenue)} so‘m</b> ({summary.mine_today.orders} ta chek)
            </span>
          </p>
        </>
      )}

      <ShiftClosePanel />

      <section className="panel report-filters">
        <header>
          <Filter size={19} />
          <div><h2>Filtrlar</h2><p>Natija faqat to‘langan cheklar asosida hisoblanadi</p></div>
          <div className="report-presets">
            <button onClick={() => preset('today')}>Bugun</button>
            <button onClick={() => preset('yesterday')}>Kecha</button>
            <button onClick={() => preset('week')}>7 kun</button>
            <button onClick={() => preset('month')}>Shu oy</button>
          </div>
        </header>
        <div className="report-filter-grid">
          <label>
            Boshlanish
            <input
              value={filters.start}
              onChange={event => apply({ start: event.target.value })}
              type="date"
              max={filters.end}
              required
            />
          </label>
          <label>
            Tugash
            <input
              value={filters.end}
              onChange={event => apply({ end: event.target.value })}
              type="date"
              min={filters.start}
              max={today()}
              required
            />
          </label>
          <label>
            Kategoriya
            <select value={filters.category} onChange={event => apply({ category: event.target.value, dish: '' }, true)}>
              <option value="">Barcha kategoriyalar</option>
              {categories.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            Taom
            <select value={filters.dish} onChange={event => apply({ dish: event.target.value }, true)}>
              <option value="">Barcha taomlar</option>
              {visibleDishes.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={filters.mine}
              onChange={event => apply({ mine: event.target.checked }, true)}
            />
            Faqat mening savdolarim
          </label>
          <button className="button secondary" disabled={loading} onClick={() => load()}>
            <RefreshCw size={17} className={loading ? 'spin' : undefined} />Ko‘rsatish
          </button>
        </div>
      </section>

      {error && <p className="alert error" role="alert">{error}</p>}
      {!data && loading && <div className="empty-state">Savdo hisoblanmoqda…</div>}

      {data && (
        <>
          <div className="report-metrics">
            <article>
              <span className="metric-icon green"><Banknote /></span>
              <div><small>Tushum</small><strong>{money(data.summary.revenue)} <em>so‘m</em></strong></div>
            </article>
            <article>
              <span className="metric-icon violet"><ReceiptText /></span>
              <div><small>To‘langan cheklar</small><strong>{data.summary.orders} <em>ta</em></strong></div>
            </article>
            <article>
              <span className="metric-icon orange"><PackageCheck /></span>
              <div><small>Sotilgan porsiya</small><strong>{data.summary.items} <em>ta</em></strong></div>
            </article>
            <article>
              <span className="metric-icon blue"><TrendingUp /></span>
              <div><small>O‘rtacha chek</small><strong>{money(data.summary.average_check)} <em>so‘m</em></strong></div>
            </article>
          </div>

          <p className="sales-note">
            {data.summary.top_dish && <span>Eng ko‘p sotilgan: <b>{data.summary.top_dish}</b></span>}
            {data.summary.peak_hour !== null && (
              <span>Eng gavjum soat: <b>{hourLabel(data.summary.peak_hour)}</b> ({money(data.summary.peak_hour_revenue || 0)} so‘m)</span>
            )}
            {data.methods.map(row => (
              <span key={row.method}>{row.label}: <b>{money(row.revenue)} so‘m</b></span>
            ))}
            {filters.mine && <span><b>Faqat {user?.name} savdolari</b></span>}
          </p>

          <div className="report-grid">
            <section className="panel report-trend">
              <header className="panel-heading">
                <div>
                  <h2>{multiDay ? 'Kunlar bo‘yicha' : 'Soatlar bo‘yicha'}</h2>
                  <p>{data.filters.start}{multiDay ? ` — ${data.filters.end}` : ''}</p>
                </div>
                {multiDay ? <CalendarDays size={20} /> : <Clock3 size={20} />}
              </header>
              <div className="report-chart" role="img" aria-label="Savdo taqsimoti">
                {(multiDay ? data.days : data.hours).map(row => {
                  const point = row as { hour?: number; date?: string; revenue: string; orders: number }
                  const key = multiDay ? point.date! : String(point.hour)
                  const caption = multiDay ? point.date!.slice(5) : hourLabel(point.hour!)
                  const height = Number(point.revenue) / (multiDay ? maxDay : maxHour) * 100
                  return (
                    <div
                      key={key}
                      className="report-bar"
                      title={`${caption}: ${money(point.revenue)} so‘m, ${point.orders} chek`}
                    >
                      <div><span style={{ height: `${height}%` }} /></div>
                      <small>{caption}</small>
                    </div>
                  )
                })}
                {!data.summary.orders && <p className="chart-empty">Tanlangan davrda to‘langan savdo yo‘q</p>}
              </div>
              <footer>
                {data.methods.length
                  ? data.methods.map(row => (
                    <span key={row.method}>{row.label}: <strong>{money(row.revenue)}</strong></span>
                  ))
                  : <span>To‘lov qayd etilmagan</span>}
              </footer>
            </section>

            <section className="panel report-categories">
              <header className="panel-heading">
                <div><h2>Kategoriya bo‘yicha</h2><p>Qaysi yo‘nalish ko‘proq sotildi?</p></div>
              </header>
              {data.categories.length ? (
                <div className="category-ranking">
                  {data.categories.map(row => (
                    <div key={row.category_id}>
                      <div>
                        <strong>{row.category}</strong>
                        <span>{row.quantity} porsiya · {row.orders} chek</span>
                        <b>{money(row.revenue)}</b>
                      </div>
                      <div className="progress-track">
                        <span style={{ width: `${Number(row.revenue) / maxCategory * 100}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state compact">Kategoriya bo‘yicha ma’lumot yo‘q.</div>
              )}
            </section>
          </div>

          <section className="panel spaced">
            <header className="panel-heading">
              <div><h2>Nima sotildi</h2><p>Har bir taom bo‘yicha miqdor va tushum</p></div>
              <div className="search-field">
                <Search size={17} />
                <input
                  value={dishQuery}
                  onChange={event => setDishQuery(event.target.value)}
                  placeholder="Taom yoki kategoriya…"
                  aria-label="Sotilgan taomni qidirish"
                />
              </div>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>TAOM</th><th>KATEGORIYA</th><th>PORSIYA</th><th>CHEKLAR</th><th>TUSHUM</th><th>ULUSH</th></tr>
                </thead>
                <tbody>
                  {soldRows.map(row => (
                    <tr key={row.dish_id}>
                      <td><strong>{row.dish}</strong></td>
                      <td><span className="pill subtle">{row.category}</span></td>
                      <td>{row.quantity}</td>
                      <td>{row.orders}</td>
                      <td className="number">{money(row.revenue)} so‘m</td>
                      <td>
                        <div className="share-cell">
                          <span
                            style={{
                              width: `${Number(data.summary.revenue)
                                ? Number(row.revenue) / Number(data.summary.revenue) * 100
                                : 0}%`,
                            }}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!soldRows.length && (
                <div className="empty-state compact">
                  {data.dishes.length ? 'Qidiruv bo‘yicha taom topilmadi.' : 'Tanlangan davrda sotilgan taom yo‘q.'}
                </div>
              )}
            </div>
          </section>

          {data.cashiers.length > 1 && (
            <section className="panel spaced">
              <header className="panel-heading">
                <div><h2>Kassirlar kesimida</h2><p>Kim qancha chek yopdi</p></div>
                <UserRound size={20} />
              </header>
              <div className="category-ranking">
                {data.cashiers.map(row => (
                  <div key={row.name}>
                    <div>
                      <strong>{row.name}</strong>
                      <span>{row.orders} chek · {row.quantity} porsiya</span>
                      <b>{money(row.revenue)}</b>
                    </div>
                    <div className="progress-track">
                      <span style={{ width: `${Number(row.revenue) / maxCashier * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="panel spaced">
            <header className="panel-heading">
              <div><h2>So‘nggi cheklar</h2><p>Tanlangan davrdagi oxirgi 20 ta to‘lov</p></div>
              <span className="pill">{data.checks.length} ta</span>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr><th>HISOB</th><th>STOL / OFITSIANT</th><th>VAQT</th><th>TO‘LOV</th><th>KASSIR</th><th>SUMMA</th></tr>
                </thead>
                <tbody>
                  {data.checks.map(check => (
                    <tr key={check.id}>
                      <td><strong>#{String(check.id).padStart(4, '0')}</strong><small>{check.items} ta porsiya</small></td>
                      <td>{check.table ? `${check.table}-stol` : 'Tezkor savdo'}<small>{check.waiter || '—'}</small></td>
                      <td>{dateLabel(check.paid_at)}</td>
                      <td><span className="pill subtle">{check.payment_label}</span></td>
                      <td>{check.cashier_name}</td>
                      <td className="number">{money(check.total)} so‘m</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.checks.length && (
                <div className="empty-state compact">Tanlangan davrda to‘langan chek yo‘q.</div>
              )}
            </div>
          </section>

          <p className="data-note">
            Bu bo‘limda faqat to‘langan cheklar ko‘rsatiladi. To‘lov kutilayotgan hisoblar «Buyurtmalar» bo‘limida.
          </p>
        </>
      )}
    </>
  )
}
