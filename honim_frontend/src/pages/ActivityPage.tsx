import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { ChevronLeft, ChevronRight, Filter, History, RefreshCw, ShieldCheck, X } from 'lucide-react'
import { api, today } from '../api'
import { useI18n } from '../i18n'
import type { ActivityFacet, ActivityLog } from '../types'

interface Filters {
  start: string
  end: string
  action: string
  actor: string
}

const NO_FILTER: Filters = { start: '', end: '', action: '', actor: '' }

function shiftDate(value: string, days: number) {
  const [year, month, day] = value.split('-').map(Number)
  return new Date(Date.UTC(year, month - 1, day + days)).toISOString().slice(0, 10)
}

const stamp = (value: string, locale: string) =>
  new Intl.DateTimeFormat(locale, {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    timeZone: 'Asia/Tashkent',
  }).format(new Date(value))

/** Harakat turlarini bo‘limlarga ajratadi, tanlov ro‘yxati o‘qilishi uchun. */
function byGroup(actions: ActivityFacet[]) {
  const groups = new Map<string, ActivityFacet[]>()
  for (const item of actions) {
    const bucket = groups.get(item.group)
    if (bucket) bucket.push(item)
    else groups.set(item.group, [item])
  }
  return [...groups.entries()]
}

export default function ActivityPage() {
  // Filtrlar manzil satrida saqlanadi: boshqa sahifalardan «shu xodimning
  // harakatlari» kabi havolalar to'g'ridan-to'g'ri ochilishi uchun.
  const { t, tn, locale } = useI18n()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<ActivityLog>()
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const filters: Filters = {
    start: params.get('start') || '',
    end: params.get('end') || '',
    action: params.get('action') || '',
    actor: params.get('actor') || '',
  }
  const search = params.toString()

  const load = useCallback(async (query: string) => {
    setLoading(true)
    setError('')
    try {
      setData(await api<ActivityLog>(`audit/?${query}`))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load(search)
  }, [load, search])

  function write(next: Filters, wanted: number) {
    const query = new URLSearchParams()
    for (const [key, value] of Object.entries(next)) if (value) query.set(key, value)
    if (wanted > 1) query.set('page', String(wanted))
    setParams(query, { replace: true })
  }

  function apply(patch: Partial<Filters>) {
    // Filtr o'zgarsa, ro'yxat boshidan ko'riladi.
    write({ ...filters, ...patch }, 1)
  }

  const setPage = (wanted: number) => write(filters, wanted)

  function preset(kind: 'today' | 'yesterday' | 'week' | 'month' | 'all') {
    const now = today()
    if (kind === 'today') return apply({ start: now, end: now })
    if (kind === 'yesterday') {
      const day = shiftDate(now, -1)
      return apply({ start: day, end: day })
    }
    if (kind === 'week') return apply({ start: shiftDate(now, -6), end: now })
    if (kind === 'month') return apply({ start: `${now.slice(0, 8)}01`, end: now })
    return apply({ start: '', end: '' })
  }

  const rows = data?.results || []
  const filtered = !!(filters.action || filters.actor)
  const firstRow = data ? (data.page - 1) * data.page_size + 1 : 0
  const lastRow = data ? Math.min(data.page * data.page_size, data.count) : 0
  const active = Object.values(filters).some(Boolean)

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('TO‘LIQ NAZORAT')}</span>
          <h1>{t('Harakatlar')}<span className="heading-dot">.</span></h1>
          <p>{t('Kim, qachon va nima qilgani — barchasi saqlanadi va hech qachon o‘chirilmaydi.')}</p>
        </div>
        <button className="button secondary" disabled={loading} onClick={() => load(search)}>
          <RefreshCw size={17} className={loading ? 'spin' : undefined} />{t('Yangilash')}
        </button>
      </div>

      {error && <p className="alert error">{error}</p>}

      <div className="inventory-summary">
        <div>
          <History size={21} />
          <span><strong>{data?.count ?? 0}</strong> {tn('ta harakat tanlovda', data?.count ?? 0)}</span>
        </div>
        <div>
          <ShieldCheck size={21} />
          <span>
            <strong>{data?.pages ?? 1}</strong>{' '}
            {tn('sahifa · har birida {size} tadan', data?.pages ?? 1, { size: data?.page_size ?? 100 })}
          </span>
        </div>
        <p>
          {filtered && data
            ? tn('Tanlangan sana oralig‘ida jami {count} ta yozuv bor.', data.total)
            : t('Jurnal to‘liq saqlanadi — eski yozuvlar hech qachon tozalanmaydi.')}
        </p>
      </div>

      <section className="panel report-filters log-filters">
        <header>
          <Filter size={19} />
          <div><h2>{t('Filtrlar')}</h2><p>{t('Kun bo‘yicha va harakat turi bo‘yicha saralang')}</p></div>
          <div className="report-presets">
            <button onClick={() => preset('today')}>{t('Bugun')}</button>
            <button onClick={() => preset('yesterday')}>{t('Kecha')}</button>
            <button onClick={() => preset('week')}>{t('7 kun')}</button>
            <button onClick={() => preset('month')}>{t('Shu oy')}</button>
            <button onClick={() => preset('all')}>{t('Hammasi')}</button>
          </div>
        </header>
        <div className="report-filter-grid">
          <label>
            {t('Boshlanish')}
            <input
              value={filters.start}
              onChange={event => apply({ start: event.target.value })}
              type="date"
              max={filters.end || today()}
            />
          </label>
          <label>
            {t('Tugash')}
            <input
              value={filters.end}
              onChange={event => apply({ end: event.target.value })}
              type="date"
              min={filters.start || undefined}
              max={today()}
            />
          </label>
          <label>
            {t('Harakat turi')}
            <select value={filters.action} onChange={event => apply({ action: event.target.value })}>
              <option value="">{t('Barcha harakatlar')}</option>
              {byGroup(data?.actions || []).map(([group, items]) => (
                <optgroup key={group} label={group}>
                  {items.map(item => (
                    <option key={item.action} value={item.action}>{item.label} ({item.count})</option>
                  ))}
                </optgroup>
              ))}
            </select>
          </label>
          <label>
            {t('Xodim')}
            <select value={filters.actor} onChange={event => apply({ actor: event.target.value })}>
              <option value="">{t('Barcha xodimlar')}</option>
              {(data?.actors || []).map(item => (
                <option key={item.id} value={item.id}>{item.name} ({item.count})</option>
              ))}
            </select>
          </label>
        </div>
        {active && (
          <button className="button secondary filter-reset" onClick={() => write(NO_FILTER, 1)}>
            <X size={16} />{t('Filtrlarni tozalash')}
          </button>
        )}
      </section>

      <section className="panel">
        <header className="panel-heading">
          <div>
            <h2>{t('Harakatlar jurnali')}</h2>
            <p>{data?.count ? `${firstRow}–${lastRow} / ${data.count}` : t('Yozuv topilmadi')}</p>
          </div>
        </header>
        <div className="table-wrap">
          <table className="log-table">
            <thead>
              <tr><th>{t('VAQT')}</th><th>{t('HARAKAT')}</th><th>{t('TAFSILOT')}</th><th>{t('XODIM')}</th></tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.id}>
                  <td className="log-time">{stamp(row.created_at, locale)}</td>
                  <td>
                    <span className="log-action" data-group={row.group}>{row.label}</span>
                    <small>{row.group}</small>
                  </td>
                  <td className="log-detail">{row.description || '—'}</td>
                  <td>{row.actor}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!loading && !rows.length && <div className="empty-state">{t('Bu tanlov bo‘yicha harakat topilmadi.')}</div>}
        </div>
        {!!data && data.pages > 1 && (
          <div className="log-pager">
            <button className="button secondary" disabled={loading || data.page <= 1} onClick={() => setPage(data.page - 1)}>
              <ChevronLeft size={16} />{t('Oldingi')}
            </button>
            <label>
              {t('Sahifa')}
              <select value={data.page} onChange={event => setPage(Number(event.target.value))}>
                {Array.from({ length: data.pages }, (_, index) => index + 1).map(number => (
                  <option key={number} value={number}>{number}</option>
                ))}
              </select>
              <span>/ {data.pages}</span>
            </label>
            <button className="button secondary" disabled={loading || data.page >= data.pages} onClick={() => setPage(data.page + 1)}>
              {t('Keyingi')}<ChevronRight size={16} />
            </button>
          </div>
        )}
      </section>
    </>
  )
}
