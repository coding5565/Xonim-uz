import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  Banknote, CalendarDays, Download, Filter, PackageCheck, ReceiptText, RefreshCw, TrendingUp,
} from 'lucide-react'
import { api, download, list, money, today } from '../api'
import { useI18n } from '../i18n'
import type { Category, Dish, SalesReport } from '../types'

interface Filters {
  start: string
  end: string
  category: string
  dish: string
  group: string
}

function queryFor(filters: Filters) {
  const query = new URLSearchParams({ start: filters.start, end: filters.end, group: filters.group })
  if (filters.category) query.set('category', filters.category)
  if (filters.dish) query.set('dish', filters.dish)
  return query.toString()
}

function shiftDate(value: string, days: number) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10)
}

export default function ReportsPage() {
  const { t, tn } = useI18n()
  const [categories, setCategories] = useState<Category[]>([])
  const [dishes, setDishes] = useState<Dish[]>([])
  const [data, setData] = useState<SalesReport>()
  // Boshlang'ich filtr manzil satridan olinadi: moliya sahifasidan
  // «shu davrning hisoboti» havolasi shu orqali ishlaydi.
  const [params] = useSearchParams()
  const [filters, setFilters] = useState<Filters>({
    start: params.get('start') || today().slice(0, 8) + '01',
    end: params.get('end') || today(),
    category: params.get('category') || '',
    dish: params.get('dish') || '',
    group: params.get('group') || 'auto',
  })
  const [loading, setLoading] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')

  /** Takes the filters explicitly so a freshly chosen preset is not read from stale state. */
  async function load(next: Filters = filters) {
    setLoading(true)
    setError('')
    try {
      setData(await api<SalesReport>(`reports/sales/?${queryFor(next)}`))
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
        await load()
      } catch (exception) {
        setError((exception as Error).message)
      }
    }
    bootstrap()
    // Runs once on mount, exactly like the original page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function apply(patch: Partial<Filters>, reload = false) {
    const next = { ...filters, ...patch }
    setFilters(next)
    if (reload) load(next)
  }

  function preset(kind: 'today' | 'week' | 'month') {
    const end = today()
    const start = kind === 'today' ? end : kind === 'week' ? shiftDate(end, -6) : end.slice(0, 8) + '01'
    apply({ start, end }, true)
  }

  async function exportExcel() {
    setExporting(true)
    setError('')
    try {
      await download(
        `reports/sales/export/?${queryFor(filters)}`,
        `xonim-savdo-${filters.start}-${filters.end}.xlsx`,
      )
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setExporting(false)
    }
  }

  const visibleDishes = dishes.filter(item => !filters.category || item.category === Number(filters.category))
  const maxTrend = Math.max(1, ...(data?.trend.map(item => Number(item.revenue)) || [1]))
  const maxCategory = Math.max(1, ...(data?.categories.map(item => Number(item.revenue)) || [1]))

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('SAVDO TAHLILI')}</span>
          <h1>{t('Hisobotlar')}<span className="heading-dot">.</span></h1>
          <p>{t('Kunlik, oylik va istalgan sana oralig‘idagi savdolar.')}</p>
        </div>
        <button className="button primary" disabled={exporting || loading} onClick={exportExcel}>
          <Download size={17} />{exporting ? t('Tayyorlanmoqda…') : t('Excel yuklash')}
        </button>
      </div>
      <section className="panel report-filters">
        <header>
          <Filter size={19} />
          <div><h2>{t('Hisobot filtrlari')}</h2><p>{t('Natija faqat to‘langan cheklar asosida hisoblanadi')}</p></div>
          <div className="report-presets">
            <button onClick={() => preset('today')}>{t('Bugun')}</button>
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
            <select
              value={filters.category}
              onChange={event => apply({ category: event.target.value, dish: '' }, true)}
            >
              <option value="">{t('Barcha kategoriyalar')}</option>
              {categories.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            {t('Taom')}
            <select value={filters.dish} onChange={event => apply({ dish: event.target.value })}>
              <option value="">{t('Barcha taomlar')}</option>
              {visibleDishes.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </label>
          <label>
            {t('Grafik guruhi')}
            <select value={filters.group} onChange={event => apply({ group: event.target.value })}>
              <option value="auto">{t('Avtomatik')}</option>
              <option value="day">{t('Kunlik')}</option>
              <option value="month">{t('Oylik')}</option>
            </select>
          </label>
          <button className="button secondary" disabled={loading} onClick={() => load()}>
            <RefreshCw size={17} className={loading ? 'spin' : undefined} />{t('Ko‘rsatish')}
          </button>
        </div>
      </section>
      {error && <p className="alert error" role="alert">{error}</p>}
      {!data && loading && <div className="empty-state">{t('Hisobot hisoblanmoqda…')}</div>}
      {data && (
        <>
          <div className="report-metrics">
            <article>
              <span className="metric-icon green"><Banknote /></span>
              <div><small>{t('Jami tushum')}</small><strong>{money(data.summary.revenue)} <em>{t('so‘m')}</em></strong></div>
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
          <section className="profit-strip">
            <div><small>{t('Retsept tannarxi')}</small><strong>{money(data.summary.cost)} {t('so‘m')}</strong></div>
            <div><small>{t('Yalpi foyda')}</small><strong>{money(data.summary.gross_profit)} {t('so‘m')}</strong></div>
            <div><small>{t('Yalpi marja')}</small><strong>{Number(data.summary.gross_margin).toFixed(1)}%</strong></div>
            <p>
              {t('Yalpi foyda faqat retsept tannarxini ayiradi. Oylik va umumiy xarajatlar keyingi sof foyda hisobida ayiriladi.')}
            </p>
          </section>
          <div className="report-grid">
            <section className="panel report-trend">
              <header className="panel-heading">
                <div>
                  <h2>{t('Savdo dinamikasi')}</h2>
                  <p>
                    {data.filters.start} — {data.filters.end} · {data.filters.group === 'day' ? t('kunlik') : t('oylik')}
                  </p>
                </div>
                <CalendarDays size={20} />
              </header>
              <div className="report-chart" role="img" aria-label={t('Savdo tushumi grafigi')}>
                {data.trend.map(point => (
                  <div
                    key={point.date}
                    className="report-bar"
                    title={`${point.date}: ${money(point.revenue)} ${t('so‘m')}, ${tn('{count} chek', Number(point.orders))}`}
                  >
                    <div><span style={{ height: `${Number(point.revenue) / maxTrend * 100}%` }} /></div>
                    <small>{data.filters.group === 'month' ? point.date.slice(0, 7) : point.date.slice(5)}</small>
                  </div>
                ))}
                {!Number(data.summary.revenue) && (
                  <p className="chart-empty">{t('Tanlangan davrda to‘langan savdo yo‘q')}</p>
                )}
              </div>
              <footer>
                {data.summary.by_method.length
                  ? data.summary.by_method.map(row => (
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
                  {data.categories.map(item => (
                    <div key={item.category_id}>
                      <div>
                        <strong>{item.category}</strong>
                        <span>
                          {tn('{count} porsiya', Number(item.quantity))} · {tn('{count} chek', Number(item.orders))}
                        </span>
                        <b>{money(item.revenue)}</b>
                      </div>
                      <div className="progress-track">
                        <span style={{ width: `${Number(item.revenue) / maxCategory * 100}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state compact">{t('Kategoriya bo‘yicha ma’lumot yo‘q.')}</div>
              )}
            </section>
          </div>
          <section className="panel spaced">
            <header className="panel-heading">
              <div><h2>{t('Taomlar kesimida')}</h2><p>{t('Filtrlangan davrdagi barcha sotilgan taomlar')}</p></div>
              <span className="pill">{tn('{count} ta taom', data.dishes.length)}</span>
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
                  {data.dishes.map(item => (
                    <tr key={item.dish_id}>
                      <td><strong>{item.dish}</strong></td>
                      <td><span className="pill subtle">{item.category}</span></td>
                      <td>{item.quantity}</td>
                      <td>{item.orders}</td>
                      <td className="number">{money(item.revenue)} {t('so‘m')}</td>
                      <td>
                        <div className="share-cell">
                          <span
                            style={{
                              width: `${Number(data.summary.revenue)
                                ? Number(item.revenue) / Number(data.summary.revenue) * 100
                                : 0}%`,
                            }}
                          />
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {!data.dishes.length && (
                <div className="empty-state compact">{t('Tanlangan filtr bo‘yicha sotilgan taom topilmadi.')}</div>
              )}
            </div>
          </section>
          <p className="data-note">
            {t('Excel faylida Umumiy, Davrlar, Kategoriyalar va Taomlar varaqlari yaratiladi. Summalar kassadagi to‘langan cheklar bilan tenglashtiriladi.')}
          </p>
        </>
      )}
    </>
  )
}
