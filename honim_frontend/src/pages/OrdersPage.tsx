import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Printer, ReceiptText, Search, Undo2 } from 'lucide-react'
import { api, dateLabel, list, money } from '../api'
import { useSession } from '../session'
import { useI18n } from '../i18n'
import type { Order } from '../types'
import AppModal from '../components/AppModal'

/** Bekor qilingan va qaytarilgan hisob to'langanidan boshqa rangda turadi. */
const statusTone = (status: Order['status']) =>
  status === 'paid' ? 'paid' : status === 'open' ? 'open' : 'neutral'

export default function OrdersPage() {
  const { user } = useSession()
  const { t, tn } = useI18n()
  const manager = user?.role === 'owner'
  const [orders, setOrders] = useState<Order[]>([])
  const [filter, setFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [error, setError] = useState('')
  const [selected, setSelected] = useState<Order>()
  const [method, setMethod] = useState('cash')
  const [busy, setBusy] = useState(false)
  const [printing, setPrinting] = useState(false)
  const [printed, setPrinted] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    try {
      setOrders(await list<Order>('orders/'))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const methods = user?.payment_methods || []
  const methodLabel = (value: string) =>
    methods.find(item => item.method === value)?.label || t('To‘lov olinmagan')

  const visible = orders.filter(order =>
    (filter === 'all' || order.status === filter) &&
    `${order.id} ${order.table} ${order.waiter}`.toLowerCase().includes(query.toLowerCase()),
  )

  async function pay(event: FormEvent) {
    event.preventDefault()
    if (!selected) return
    setBusy(true)
    setError('')
    try {
      setSelected(await api<Order>(`orders/${selected.id}/pay/`, {
        method: 'POST',
        body: JSON.stringify({ payment_method: method }),
      }))
      await load()
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  /** To'langan hisobni qaytaradi: pul ham, ombor ham orqaga qaytadi. */
  async function refund() {
    if (!selected) return
    const reason = prompt(t('Nima uchun qaytarilyapti?'))
    if (!reason || reason.trim().length < 3) return
    setBusy(true)
    setError('')
    try {
      const updated = await api<Order>(`orders/${selected.id}/refund/`, {
        method: 'POST',
        body: JSON.stringify({ reason: reason.trim() }),
      })
      setSelected(updated)
      await load()
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  async function printReceipt() {
    if (!selected) return
    setPrinting(true)
    setError('')
    setPrinted('')
    try {
      await api(`orders/${selected.id}/print/`, { method: 'POST' })
      setPrinted(t('Chek printerga yuborildi.'))
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setPrinting(false)
    }
  }

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{t('SAVDO TARIXI')}</span>
          <h1>{t('Buyurtmalar')}<span className="heading-dot">.</span></h1>
          <p>{t('To‘lov kutilayotgan hisoblar, to‘lovlar va chek tafsilotlari.')}</p>
        </div>
        <Link to="/pos" className="button primary">{t('Kassaga o‘tish')} <ArrowRight size={17} /></Link>
      </div>
      {error && <p className="alert error">{error}</p>}
      <section className="panel">
        <div className="table-toolbar">
          <div className="tabs">
            <button className={filter === 'all' ? 'selected' : undefined} onClick={() => setFilter('all')}>{t('Barchasi')}</button>
            <button className={filter === 'open' ? 'selected' : undefined} onClick={() => setFilter('open')}>{t('To‘lov kutilmoqda')}</button>
            <button className={filter === 'paid' ? 'selected' : undefined} onClick={() => setFilter('paid')}>{t('To‘langan')}</button>
            <button className={filter === 'cancelled' ? 'selected' : undefined} onClick={() => setFilter('cancelled')}>{t('Bekor qilingan')}</button>
            <button className={filter === 'refunded' ? 'selected' : undefined} onClick={() => setFilter('refunded')}>{t('Qaytarilgan')}</button>
          </div>
          <div className="search-field">
            <Search size={17} />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              aria-label={t('Buyurtma qidirish')}
              placeholder={t('Raqam, stol yoki ofitsiant…')}
            />
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('HISOB')}</th>
                <th>{t('STOL / OFITSIANT')}</th>
                <th>{t('VAQT')}</th>
                <th>{t('SUMMA')}</th>
                <th>{t('HOLAT')}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {visible.map(order => (
                <tr key={order.id}>
                  <td><strong>#{String(order.id).padStart(4, '0')}</strong><small>{tn('{count} xil taom', order.lines.length)}</small></td>
                  <td>{order.table ? t('{table}-stol', { table: order.table }) : t('Tezkor savdo')}<small>{order.waiter || '—'}</small></td>
                  <td>{dateLabel(order.created_at)}</td>
                  <td className="number">{money(order.total)} {t('so‘m')}</td>
                  <td>
                    <span className={`status ${statusTone(order.status)}`}>
                      {order.status === 'open' ? t('To‘lov kutilmoqda') : t(order.status_label)}
                    </span>
                    {order.void_reason && <small>{order.void_reason}</small>}
                  </td>
                  <td>
                    <button className="text-link" onClick={() => { setSelected(order); setError(''); setPrinted('') }}>
                      {t('Ochish')} <ArrowRight size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!visible.length && (
            <div className="empty-state">
              <ReceiptText size={38} strokeWidth={1.3} />
              <h3>{loading ? t('Yuklanmoqda…') : t('Hali buyurtmalar yo‘q')}</h3>
              <p>{t('Kassada yaratilgan hisoblar shu yerda saqlanadi.')}</p>
            </div>
          )}
        </div>
      </section>
      <AppModal
        open={!!selected}
        title={t('Hisob #{id}', { id: selected?.id || '' })}
        onClose={() => { if (!busy) setSelected(undefined) }}
      >
        {selected && (
          <>
            <div className="receipt">
              <h2>HONIM</h2>
              <p>{selected.status === 'paid' ? t('TO‘LOV QAYDI') : t('OLDINDAN HISOB')}</p>
              <small>{dateLabel(selected.created_at)} · #{selected.id}</small>
              {selected.table && <p>{t('Stol')}: {selected.table} · {selected.waiter}</p>}
              <div className="receipt-lines">
                {selected.lines.map(line => (
                  <div key={line.id}>
                    <span>
                      {line.name}
                      <small>{line.quantity} × {money(line.price)} {line.note ? `· ${line.note}` : ''}</small>
                    </span>
                    <strong>{money(Number(line.price) * line.quantity)}</strong>
                  </div>
                ))}
              </div>
              <div className="cart-total"><span>{t('JAMI')}</span><strong>{money(selected.total)}</strong></div>
              <p>{methodLabel(selected.payment_method)}</p>
              <small>{t('Mahalliy sinov cheki · fiskal chek emas')}</small>
            </div>
            {error && <p className="alert error">{error}</p>}
            {selected.status === 'open' && (
              <form onSubmit={pay}>
                <label>
                  {t('To‘lov usuli')}
                  <select value={method} onChange={event => setMethod(event.target.value)}>
                    {methods.map(item => <option key={item.method} value={item.method}>{t(item.label)}</option>)}
                  </select>
                </label>
                <button className="button primary full" disabled={busy}>
                  {busy ? t('Saqlanmoqda…') : t('To‘lovni qayd etish')}
                </button>
              </form>
            )}
            {selected.status === 'paid' && manager && (
              <button className="button danger full" disabled={busy} onClick={refund}>
                <Undo2 size={17} />{t('To‘lovni qaytarish')}
              </button>
            )}
            {(selected.status === 'cancelled' || selected.status === 'refunded') && (
              <p className="alert">
                <strong>{selected.status_label}</strong> · {selected.void_reason}
                {selected.voided_by_name && ` · ${selected.voided_by_name}`}
              </p>
            )}
            {printed && <p className="alert success">{printed}</p>}
            <button className="button primary full" disabled={printing} onClick={printReceipt}>
              <Printer size={17} />{printing ? t('Chiqarilmoqda…') : t('Chekni chop etish')}
            </button>
            <button className="button secondary full" onClick={() => window.print()}>
              {t('Brauzer orqali chiqarish')}
            </button>
          </>
        )}
      </AppModal>
    </>
  )
}
