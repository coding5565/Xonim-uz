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
  /** Moliya sahifasidan kelgan to'lov turi: faqat shu yo'l bilan to'langanlari. */
  method: string
  mine: boolean
}

function queryFor(filters: Filters) {
  const query = new URLSearchParams({ start: filters.start, end: filters.end })
  if (filters.category) query.set('category', filters.category)
  if (filters.dish) query.set('dish', filters.dish)
  if (filters.method) query.set('method', filters.method)
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
    method: params.get('method') || '',
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
          <span className="eyebrow">{t('SAVDO NAZORATI')}</span>
          <h1>{t('Sotuv')}<span className="heading-dot">.</span></h1>
          <p>{t('Nima sotildi, qaysi soatda va qaysi kassa orqali — hammasi shu yerda.')}</p>
        </div>
        <button className="button secondary" disabled={loading} onClick={() => { load(); loadSummary() }}>
          <RefreshCw size={17} className={loading ? 'spin' : undefined} />{t('Yangilash')}
        </button>
      </div>

      {summary && (
        <>
          <div className="sales-summary">
            <article>
              <Wallet size={21} />
              <div>
                <small>{t('BUGUN')}</small>
                <strong>{money(summary.today.revenue)} {t('so‘m')}</strong>
                <span>{tn('{count} ta chek', summary.today.orders)}</span>
              </div>
            </article>
            <article>
              <CalendarDays size={21} />
              <div>
                <small>{t('KECHA')}</small>
                <strong>{money(summary.yesterday.revenue)} {t('so‘m')}</strong>
                <span>{tn('{count} ta chek', summary.yesterday.orders)}</span>
              </div>
            </article>
            <article>
              <TrendingUp size={21} />
              <div>
                <small>{t('OXIRGI 7 KUN')}</small>
                <strong>{money(summary.last_7_days.revenue)} {t('so‘m')}</strong>
                <span>{tn('{count} ta chek', summary.last_7_days.orders)}</span>
              </div>
            </article>
            <article className="open">
              <ReceiptText size={21} />
              <div>
                <small>{t('TO‘LOV KUTILMOQDA')}</small>
                <strong>{money(summary.open.revenue)} {t('so‘m')}</strong>
                <span>{tn('{count} ta ochiq hisob', summary.open.orders)}</span>
              </div>
            </article>
          </div>
          <p className="sales-note">
            {summary.today_by_method.map(row => (
              <span key={row.method}>
                {t('Bugun {method}', { method: t(row.label).toLocaleLowerCase() })}: <b>{money(row.revenue)} {t('so‘m')}</b>
              </span>
            ))}
            <span>
              {t('Sizning bugungi savdongiz')}: <b>{money(summary.mine_today.revenue)} {t('so‘m')}</b>{' '}
              ({tn('{count} ta chek', summary.mine_today.orders)})
            </span>
          </p>
        </>
      )}

      <ShiftClosePanel />

      <section className="panel report-filters">
        <header>
          <Filter size={19} />
          <div><h2>{t('Filtrlar')}</h2><p>{t('Natija faqat to‘langan cheklar asosida hisoblanadi')}</p></div>
          <div className="report-presets">
            <button onClick={() => preset('today')}>{t('Bugun')}</button>
            <button onClick={() => preset('yesterday')}>{t('Kecha')}</button>
            <button onClick={() => preset('week')}>{t('7 kun')}</button>
            <button onClick={() => preset('month')}>{t('Shu oy')}</button>
          </div>
        </header>
        <div className="report-filter-grid">
          <label>
            {t('Boshlanish')}
            <input
              value={filters.start}
              onChange={event => apply({ start: event.target.value })}
              type="date"
              max={filters.end}
              required
            />
          </label>
          <label>
            {t('Tugash')}
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
            {t('Kategoriya')}
            <select value={filters.category} onChange={event => apply({ category: event.target.value, dish: '' }, true)}>
              <option value="">{t('Barcha kategoriyalar')}</option>
              {categories.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            {t('Taom')}
            <select value={filters.dish} onChange={event => apply({ dish: event.target.value }, true)}>
              <option value="">{t('Barcha taomlar')}</option>
              {visibleDishes.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            {t('To‘lov turi')}
            <select value={filters.method} onChange={event => apply({ method: event.target.value }, true)}>
              <option value="">{t('Hammasi')}</option>
              {(user?.payment_methods || []).map(item => (
                <option key={item.method} value={item.method}>{t(item.label)}</option>
              ))}
            </select>
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={filters.mine}
              onChange={event => apply({ mine: event.target.checked }, true)}
            />
            {t('Faqat mening savdolarim')}
          </label>
          <button className="button secondary" disabled={loading} onClick={() => load()}>
            <RefreshCw size={17} className={loading ? 'spin' : undefined} />{t('Ko‘rsatish')}
          </button>
        </div>
      </section>

      {error && <p className="alert error" role="alert">{error}</p>}
      {!data && loading && <div className="empty-state">{t('Savdo hisoblanmoqda…')}</div>}

      {data && (
        <>
          <div className="report-metrics">
            <article>
              <span className="metric-icon green"><Banknote /></span>
              <div><small>{t('Tushum')}</small><strong>{money(data.summary.revenue)} <em>{t('so‘m')}</em></strong></div>
            </article>
            <article>
              <span className="metric-icon violet"><ReceiptText /></span>
              <div><small>{t('To‘langan cheklar')}</small><strong>{data.summary.orders} <em>{t('ta')}</em></strong></div>
            </article>
            <article>
              <span className="metric-icon orange"><PackageCheck /></span>
              <div><small>{t('Sotilgan porsiya')}</small><strong>{data.summary.items} <em>{t('ta')}</em></strong></div>
            </article>
            <article>
              <span className="metric-icon blue"><TrendingUp /></span>
              <div><small>{t('O‘rtacha chek')}</small><strong>{money(data.summary.average_check)} <em>{t('so‘m')}</em></strong></div>
            </article>
          </div>

          <p className="sales-note">
            {data.summary.top_dish && <span>{t('Eng ko‘p sotilgan')}: <b>{data.summary.top_dish}</b></span>}
            {data.summary.peak_hour !== null && (
              <span>
                {t('Eng gavjum soat')}: <b>{hourLabel(data.summary.peak_hour)}</b>{' '}
                ({money(data.summary.peak_hour_revenue || 0)} {t('so‘m')})
              </span>
            )}
            {data.methods.map(row => (
              <span key={row.method}>{t(row.label)}: <b>{money(row.revenue)} {t('so‘m')}</b></span>
            ))}
            {!!filters.method && (
              <span>
                <b>
                  {t('Faqat {method} orqali to‘langanlari', {
                    method: t((user?.payment_methods || []).find(item => item.method === filters.method)?.label || filters.method),
                  })}
                </b>
              </span>
            )}
            {filters.mine && <span><b>{t('Faqat {name} savdolari', { name: user?.name || '' })}</b></span>}
          </p>

          <div className="report-grid">
            <section className="panel report-trend">
              <header className="panel-heading">
                <div>
                  <h2>{multiDay ? t('Kunlar bo‘yicha') : t('Soatlar bo‘yicha')}</h2>
                  <p>{data.filters.start}{multiDay ? ` — ${data.filters.end}` : ''}</p>
                </div>
                {multiDay ? <CalendarDays size={20} /> : <Clock3 size={20} />}
              </header>
              <div className="report-chart" role="img" aria-label={t('Savdo taqsimoti')}>
                {(multiDay ? data.days : data.hours).map(row => {
                  const point = row as { hour?: number; date?: string; revenue: string; orders: number }
                  const key = multiDay ? point.date! : String(point.hour)
                  const caption = multiDay ? point.date!.slice(5) : hourLabel(point.hour!)
                  const height = Number(point.revenue) / (multiDay ? maxDay : maxHour) * 100
                  return (
                    <div
                      key={key}
                      className="report-bar"
                      title={`${caption}: ${money(point.revenue)} ${t('so‘m')}, ${tn('{count} chek', point.orders)}`}
                    >
                      <div><span style={{ height: `${height}%` }} /></div>
                      <small>{caption}</small>
                    </div>
                  )
                })}
                {!data.summary.orders && <p className="chart-empty">{t('Tanlangan davrda to‘langan savdo yo‘q')}</p>}
              </div>
              <footer>
                {data.methods.length
                  ? data.methods.map(row => (
                    <span key={row.method}>{t(row.label)}: <strong>{money(row.revenue)}</strong></span>
                  ))
                  : <span>{t('To‘lov qayd etilmagan')}</span>}
              </footer>
            </section>

            <section className="panel report-categories">
              <header className="panel-heading">
                <div><h2>{t('Kategoriya bo‘yicha')}</h2><p>{t('Qaysi yo‘nalish ko‘proq sotildi?')}</p></div>
              </header>
              {data.categories.length ? (
                <div className="category-ranking">
                  {data.categories.map(row => (
                    <div key={row.category_id}>
                      <div>
                        <strong>{row.category}</strong>
                        <span>{tn('{count} porsiya', row.quantity)} · {tn('{count} chek', row.orders)}</span>
                        <b>{money(row.revenue)}</b>
                      </div>
                      <div className="progress-track">
                        <span style={{ width: `${Number(row.revenue) / maxCategory * 100}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state compact">{t('Kategoriya bo‘yicha ma’lumot yo‘q.')}</div>
              )}
            </section>
          </div>

          {/* Zal, olib ketish, Uzum va Yandex savdosi alohida ko'rinadi. */}
          <section className="panel spaced">
            <header className="panel-heading">
              <div><h2>{t('Savdo kanallari')}</h2><p>{t('Buyurtma qayerdan kelgani bo‘yicha')}</p></div>
              <span className="pill subtle">{money(data.summary.revenue)} {t('so‘m')}</span>
            </header>
            {data.channels.length ? (
              <div className="category-ranking">
                {data.channels.map(row => (
                  <div key={row.channel}>
                    <div>
                      <strong>{t(row.label)}{row.delivery ? ` · ${t('yetkazib berish')}` : ''}</strong>
                      <span>{tn('{count} chek', row.orders)}</span>
                      <b>{money(row.revenue)}</b>
                    </div>
                    <div className="progress-track">
                      <span style={{ width: `${Number(data.summary.revenue) ? Number(row.revenue) / Number(data.summary.revenue) * 100 : 0}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state compact">{t('Bu davrda savdo yo‘q.')}</div>
            )}
          </section>

          <section className="panel spaced">
            <header className="panel-heading">
              <div><h2>{t('Nima sotildi')}</h2><p>{t('Har bir taom bo‘yicha miqdor va tushum')}</p></div>
              <div className="search-field">
                <Search size={17} />
                <input
                  value={dishQuery}
                  onChange={event => setDishQuery(event.target.value)}
                  placeholder={t('Taom yoki kategoriya…')}
                  aria-label={t('Sotilgan taomni qidirish')}
                />
              </div>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t('TAOM')}</th><th>{t('KATEGORIYA')}</th><th>{t('PORSIYA')}</th>
                    <th>{t('CHEKLAR')}</th><th>{t('TUSHUM')}</th><th>{t('ULUSH')}</th>
                  </tr>
                </thead>
                <tbody>
                  {soldRows.map(row => (
                    <tr key={row.dish_id}>
                      <td><strong>{row.dish}</strong></td>
                      <td><span className="pill subtle">{row.category}</span></td>
                      <td>{row.quantity}</td>
                      <td>{row.orders}</td>
                      <td className="number">{money(row.revenue)} {t('so‘m')}</td>
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
                  {data.dishes.length
                    ? t('Qidiruv bo‘yicha taom topilmadi.')
                    : t('Tanlangan davrda sotilgan taom yo‘q.')}
                </div>
              )}
            </div>
          </section>

          {data.cashiers.length > 1 && (
            <section className="panel spaced">
              <header className="panel-heading">
                <div><h2>{t('Kassirlar kesimida')}</h2><p>{t('Kim qancha chek yopdi')}</p></div>
                <UserRound size={20} />
              </header>
              <div className="category-ranking">
                {data.cashiers.map(row => (
                  <div key={row.name}>
                    <div>
                      <strong>{row.name}</strong>
                      <span>{tn('{count} chek', row.orders)} · {tn('{count} porsiya', row.quantity)}</span>
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
              <div><h2>{t('So‘nggi cheklar')}</h2><p>{t('Tanlangan davrdagi oxirgi 20 ta to‘lov')}</p></div>
              <span className="pill">{tn('{count} ta', data.checks.length)}</span>
            </header>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>{t('HISOB')}</th><th>{t('STOL / OFITSIANT')}</th><th>{t('VAQT')}</th>
                    <th>{t('TO‘LOV')}</th><th>{t('KASSIR')}</th><th>{t('SUMMA')}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.checks.map(check => (
                    <tr key={check.id}>
                      <td>
                        <strong>#{String(check.id).padStart(4, '0')}</strong>
                        <small>{tn('{count} ta porsiya', check.items)}</small>
                      </td>
                      <td>
                        {check.table ? t('{table}-stol', { table: check.table }) : t(check.channel_label)}
                        <small>{check.waiter || '—'}</small>
                      </td>
                      <td>{dateLabel(check.paid_at)}</td>
                      <td><span className="pill subtle">{check.payment_label}</span></td>
                      <td>{check.cashier_name}</td>
                      <td className="number">{money(check.total)} {t('so‘m')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.checks.length && (
                <div className="empty-state compact">{t('Tanlangan davrda to‘langan chek yo‘q.')}</div>
              )}
            </div>
          </section>

          <p className="data-note">
            {t('Bu bo‘limda faqat to‘langan cheklar ko‘rsatiladi. To‘lov kutilayotgan hisoblar «Buyurtmalar» bo‘limida.')}
          </p>
        </>
      )}
    </>
  )
}
