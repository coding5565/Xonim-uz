import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BadgePercent, Ban, Plus, Printer, RefreshCw, ShoppingBag, Trash2, Users } from 'lucide-react'
import { api, list, money } from '../api'
import { useSession } from '../session'
import { useI18n } from '../i18n'
import type { Order, SaleChannel, SalesSummary, Table, TableZone } from '../types'
import AppModal from '../components/AppModal'

/** Zal chizmasi: kirganda chapda divanlar, o'ngda stulli stollar, tashqarida alohida. */
const ZONES: { key: TableZone; title: string }[] = [
  { key: 'hall_left', title: 'Chap tomon · divan' },
  { key: 'hall_right', title: 'O‘ng tomon · stulli' },
]

/** Stol bilan bog'liq bo'lmagan savdo joylari. Har biri alohida kiriladi va
 *  alohida hisoblanadi: kanal marshrutda yozilgani uchun kassir uni tanlashni
 *  unuta olmaydi. */
const COUNTERS: { channel: SaleChannel; path: string; name: string; mark?: string }[] = [
  { channel: 'takeaway', path: '/pos/tezkor', name: 'Olib ketish' },
  // Platformalar o'z rangi va nomi bilan ajralib turadi: kassir shoshib
  // turganda ham qaysi tugmani bosayotganini o'ylab o'tirmasligi kerak.
  { channel: 'uzum', path: '/pos/uzum', name: 'Uzum', mark: 'uzum' },
  { channel: 'yandex', path: '/pos/yandex', name: 'Yandex', mark: 'yandex' },
]

/** Matn tarjimoni — modul darajasidagi funksiyalarga hook o'rniga uzatiladi. */
type Translate = (text: string, vars?: Record<string, string | number>) => string

function minutesSince(iso: string, t: Translate) {
  const passed = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (passed < 1) return t('hozir')
  if (passed < 60) return t('{count} daq', { count: passed })
  return t('{hours} soat {minutes} daq', { hours: Math.floor(passed / 60), minutes: passed % 60 })
}

function TableCard({ table, onOpen }: { table: Table; onOpen: (table: Table) => void }) {
  const { t, tn } = useI18n()
  const open = table.open_order
  const classes = ['table-card', open ? 'busy' : '', table.seating === 'divan' ? 'divan' : '']
  return (
    <button className={classes.filter(Boolean).join(' ')} onClick={() => onOpen(table)}>
      <strong>{table.label}</strong>
      {open ? (
        <>
          <span className="table-total">{money(open.total)} {t('so‘m')}</span>
          <span className="table-meta">{tn('{count} taom', open.items)} · {minutesSince(open.created_at, t)}</span>
          {open.waiter && <span className="table-meta">{open.waiter}</span>}
        </>
      ) : (
        <>
          <span className="table-state">{t('Bo‘sh')}</span>
          <span className="table-meta">{tn('{count} o‘rin', table.seats)}</span>
        </>
      )}
    </button>
  )
}

export default function TablesPage() {
  const navigate = useNavigate()
  const { user } = useSession()
  const { t, tn } = useI18n()
  const [tables, setTables] = useState<Table[]>([])
  const [summary, setSummary] = useState<SalesSummary>()
  const [selected, setSelected] = useState<Table>()
  const [bill, setBill] = useState<Order>()
  const [method, setMethod] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = useCallback(async () => {
    try {
      const [loadedTables, loadedSummary] = await Promise.all([
        list<Table>('tables/'),
        api<SalesSummary>('sales/summary/'),
      ])
      setTables(loadedTables.filter(item => item.active))
      setSummary(loadedSummary)
      setError('')
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    // Boshqa kassir yoki ofitsiant hisobni o'zgartirsa, xarita o'zi yangilanadi.
    const timer = window.setInterval(load, 10000)
    return () => window.clearInterval(timer)
  }, [load])

  async function openTable(table: Table) {
    if (!table.open_order) {
      navigate(`/pos/stol/${table.id}`)
      return
    }
    setSelected(table)
    setMethod('')
    setNotice('')
    setError('')
    try {
      setBill(await api<Order>(`orders/${table.open_order.id}/`))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }

  async function pay(chosen: string) {
    if (!bill || busy) return
    setBusy(true)
    setMethod(chosen)
    setError('')
    try {
      await api(`orders/${bill.id}/pay/`, { method: 'POST', body: JSON.stringify({ payment_method: chosen }) })
      setSelected(undefined)
      setBill(undefined)
      await load()
    } catch (exception) {
      setError((exception as Error).message)
      setMethod('')
    } finally {
      setBusy(false)
    }
  }

  /** Noto'g'ri bosilgan taomni ochiq hisobdan olib tashlaydi. */
  async function removeLine(lineId: number, name: string) {
    if (!bill) return
    if (!confirm(t('«{name}» hisobdan olib tashlansinmi?', { name }))) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      setBill(await api<Order>(`orders/${bill.id}/lines/${lineId}/`, { method: 'DELETE' }))
      setNotice(t('{name} olib tashlandi.', { name }))
      await load()
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  /** Chegirma so'mda kiritiladi; foiz tanlansa summaga aylantiriladi. */
  async function setDiscount() {
    if (!bill) return
    const gross = Number(bill.total) + Number(bill.discount)
    const typed = prompt(
      t('Chegirma summasi, so‘m (yoki «10%» ko‘rinishida).\nHisob summasi: {sum} so‘m.\nOlib tashlash uchun 0 yozing.',
        { sum: money(gross) }),
      bill.discount === '0.00' ? '' : bill.discount,
    )
    if (typed === null) return
    const trimmed = typed.trim()
    const amount = trimmed.endsWith('%')
      ? Math.round(gross * Number(trimmed.slice(0, -1)) / 100)
      : Number(trimmed)
    if (!Number.isFinite(amount) || amount < 0) return setError(t('Chegirma noto‘g‘ri kiritildi.'))
    const reason = amount ? prompt(t('Chegirma sababi?')) : ''
    if (amount && (!reason || !reason.trim())) return
    setBusy(true)
    setError('')
    setNotice('')
    try {
      setBill(await api<Order>(`orders/${bill.id}/discount/`, {
        method: 'POST',
        body: JSON.stringify({ amount: String(amount), reason: (reason || '').trim() }),
      }))
      setNotice(amount
        ? t('Chegirma qo‘llandi: {sum} so‘m.', { sum: money(amount) })
        : t('Chegirma olib tashlandi.'))
      await load()
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  /** Butun hisobni to'lovsiz yopadi. Sabab so'raladi — jurnalga yoziladi. */
  async function cancelBill() {
    if (!bill) return
    const reason = prompt(t('Nima uchun bekor qilinyapti?'))
    if (!reason || reason.trim().length < 3) return
    setBusy(true)
    setError('')
    try {
      await api(`orders/${bill.id}/cancel/`, { method: 'POST', body: JSON.stringify({ reason: reason.trim() }) })
      setSelected(undefined)
      setBill(undefined)
      await load()
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function reprint() {
    if (!bill) return
    setBusy(true)
    setError('')
    try {
      await api(`orders/${bill.id}/print/`, { method: 'POST' })
      setNotice(t('Chek printerga yuborildi.'))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  const zoneTables = (zone: TableZone) => tables.filter(item => item.zone === zone)
  const outside = zoneTables('outside')
  const busyCount = tables.filter(item => item.open_order).length
  const openTotal = tables.reduce((sum, item) => sum + Number(item.open_order?.total || 0), 0)
  const methods = user?.payment_methods || []

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('SAVDO ISH JOYI')}</span>
          <h1>{t('Stollar')}<span className="heading-dot">.</span></h1>
          <p>{t('Bo‘sh stolga bosing — buyurtma oching. Band stolga bosing — hisob va to‘lov.')}</p>
        </div>
        <div className="heading-actions">
          <button className="button secondary icon-button" aria-label={t('Yangilash')} onClick={load}>
            <RefreshCw size={17} className={loading ? 'spin' : undefined} />
          </button>
        </div>
      </div>

      {/* Stolsiz savdo: har kanal alohida kiriladi va alohida hisoblanadi. */}
      <div className="counter-entries">
        {COUNTERS.map(item => {
          const today = summary?.today_by_channel.find(row => row.channel === item.channel)
          return (
            <button
              key={item.channel}
              className={`counter-entry ${item.channel}`}
              onClick={() => navigate(item.path)}
            >
              <span className="counter-icon">
                {item.mark ? <b>{item.mark}</b> : <ShoppingBag size={19} />}
              </span>
              <span className="counter-name">{t(item.name)}</span>
              <span className="counter-total">
                {money(today?.revenue || 0)} <small>{t('so‘m')}</small>
              </span>
              <span className="counter-note">{tn('{count} ta chek', today?.orders || 0)}</span>
            </button>
          )
        })}
      </div>

      {error && <p className="alert error" role="alert">{error}</p>}

      <div className="inventory-summary">
        <div><Users size={21} /><span><strong>{busyCount}</strong> {tn('band stol', busyCount)}</span></div>
        <div><span className="warning-dot" /><span><strong>{money(openTotal)}</strong> {t('so‘m ochiq hisobda')}</span></div>
        <p>{t('Band stollar sariq rangda. Chapdagi uchtasi divanli, qolganlari stulli.')}</p>
      </div>

      {loading && !tables.length && <div className="empty-state">{t('Stollar yuklanmoqda…')}</div>}

      <div className="floor">
        <section className="floor-zone">
          <header><h2>{t('Ichkari zal')}</h2><span>{t('KIRISH PASTDA')}</span></header>
          <div className="floor-hall">
            <div className="floor-side">
              <small>{t(ZONES[0].title).toUpperCase()}</small>
              <div className="table-grid">
                {zoneTables('hall_left').map(table => (
                  <TableCard key={table.id} table={table} onOpen={openTable} />
                ))}
              </div>
            </div>
            <div className="floor-divider" />
            <div className="floor-side">
              <small>{t(ZONES[1].title).toUpperCase()}</small>
              <div className="table-grid">
                {zoneTables('hall_right').map(table => (
                  <TableCard key={table.id} table={table} onOpen={openTable} />
                ))}
              </div>
            </div>
          </div>
        </section>

        {!!outside.length && (
          <section className="floor-zone">
            <header><h2>{t('Tashqari')}</h2><span>{tn('{count} TA STOL', outside.length)}</span></header>
            <div className="table-grid">
              {outside.map(table => <TableCard key={table.id} table={table} onOpen={openTable} />)}
            </div>
          </section>
        )}
      </div>

      <AppModal
        open={!!selected}
        title={t('{table} · hisob', { table: selected?.label || '' })}
        onClose={() => { if (!busy) { setSelected(undefined); setBill(undefined) } }}
      >
        {bill && (
          <>
            {Number(bill.discount) > 0 && (
              <div className="bill-discount">
                <span>{t('Oraliq jami')}</span>
                <b>{money(Number(bill.total) + Number(bill.discount))}</b>
                <span>{t('Chegirma')} · {bill.discount_reason}</span>
                <b className="owed">−{money(bill.discount)}</b>
              </div>
            )}
            <div className="cart-total">
              <span>{t('Jami')}</span>
              <strong>{money(bill.total)} <small>{t('so‘m')}</small></strong>
            </div>
            <div className="bill-lines">
              {bill.lines.map(line => (
                <div key={line.id}>
                  <span>
                    {line.quantity} × {line.name}
                    {line.note && <small>{t('izoh')}: {line.note}</small>}
                  </span>
                  <strong>{money(Number(line.price) * line.quantity)}</strong>
                  <button
                    className="line-remove"
                    disabled={busy || bill.lines.length === 1}
                    title={bill.lines.length === 1
                      ? t('Oxirgi qator — butun hisobni bekor qiling')
                      : t('Olib tashlash')}
                    aria-label={t('{name} ni olib tashlash', { name: line.name })}
                    onClick={() => removeLine(line.id, line.name)}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              ))}
            </div>

            <button
              className="button secondary full"
              disabled={busy}
              onClick={() => navigate(`/pos/hisob/${bill.id}`)}
            >
              <Plus size={17} />{t('Taom qo‘shish')}
            </button>

            <p className="nav-caption">{t('TO‘LOVNI QAYD ETISH')}</p>
            <div className="pay-grid">
              {methods.map(item => (
                <button
                  key={item.method}
                  className={method === item.method ? 'selected' : undefined}
                  disabled={busy}
                  onClick={() => pay(item.method)}
                >
                  {item.label}
                </button>
              ))}
            </div>

            {notice && <p className="alert success">{notice}</p>}
            {error && <p className="alert error">{error}</p>}
            <button className="button secondary full" disabled={busy} onClick={reprint}>
              <Printer size={17} />{t('Chekni chop etish')}
            </button>
            <button className="button secondary full" disabled={busy} onClick={setDiscount}>
              <BadgePercent size={17} />{Number(bill.discount) > 0 ? t('Chegirmani o‘zgartirish') : t('Chegirma berish')}
            </button>
            <button className="button danger full" disabled={busy} onClick={cancelBill}>
              <Ban size={17} />{t('Hisobni bekor qilish')}
            </button>
          </>
        )}
      </AppModal>
    </>
  )
}
