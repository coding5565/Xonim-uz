import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { ArrowRight, Printer, ReceiptText, Search } from 'lucide-react'
import { api, dateLabel, list, money } from '../api'
import { useSession } from '../session'
import type { Order } from '../types'
import AppModal from '../components/AppModal'

export default function OrdersPage() {
  const { user } = useSession()
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
  const methodLabel = (value: string) => methods.find(item => item.method === value)?.label || 'To‘lov olinmagan'

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

  async function printReceipt() {
    if (!selected) return
    setPrinting(true)
    setError('')
    setPrinted('')
    try {
      await api(`orders/${selected.id}/print/`, { method: 'POST' })
      setPrinted('Chek printerga yuborildi.')
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
          <span className="eyebrow">SAVDO TARIXI</span>
          <h1>Buyurtmalar<span className="heading-dot">.</span></h1>
          <p>To‘lov kutilayotgan hisoblar, to‘lovlar va chek tafsilotlari.</p>
        </div>
        <Link to="/pos" className="button primary">Kassaga o‘tish <ArrowRight size={17} /></Link>
      </div>
      {error && <p className="alert error">{error}</p>}
      <section className="panel">
        <div className="table-toolbar">
          <div className="tabs">
            <button className={filter === 'all' ? 'selected' : undefined} onClick={() => setFilter('all')}>Barchasi</button>
            <button className={filter === 'open' ? 'selected' : undefined} onClick={() => setFilter('open')}>To‘lov kutilmoqda</button>
            <button className={filter === 'paid' ? 'selected' : undefined} onClick={() => setFilter('paid')}>To‘langan</button>
          </div>
          <div className="search-field">
            <Search size={17} />
            <input
              value={query}
              onChange={event => setQuery(event.target.value)}
              aria-label="Buyurtma qidirish"
              placeholder="Raqam, stol yoki ofitsiant…"
            />
          </div>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>HISOB</th><th>STOL / OFITSIANT</th><th>VAQT</th><th>SUMMA</th><th>HOLAT</th><th /></tr>
            </thead>
            <tbody>
              {visible.map(order => (
                <tr key={order.id}>
                  <td><strong>#{String(order.id).padStart(4, '0')}</strong><small>{order.lines.length} xil taom</small></td>
                  <td>{order.table ? `${order.table}-stol` : 'Tezkor savdo'}<small>{order.waiter || '—'}</small></td>
                  <td>{dateLabel(order.created_at)}</td>
                  <td className="number">{money(order.total)} so‘m</td>
                  <td>
                    <span className={`status ${order.status}`}>
                      {order.status === 'paid' ? 'To‘langan' : 'To‘lov kutilmoqda'}
                    </span>
                  </td>
                  <td>
                    <button className="text-link" onClick={() => { setSelected(order); setError(''); setPrinted('') }}>
                      Ochish <ArrowRight size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!visible.length && (
            <div className="empty-state">
              <ReceiptText size={38} strokeWidth={1.3} />
              <h3>{loading ? 'Yuklanmoqda…' : 'Hali buyurtmalar yo‘q'}</h3>
              <p>Kassada yaratilgan hisoblar shu yerda saqlanadi.</p>
            </div>
          )}
        </div>
      </section>
      <AppModal
        open={!!selected}
        title={`Hisob #${selected?.id || ''}`}
        onClose={() => { if (!busy) setSelected(undefined) }}
      >
        {selected && (
          <>
            <div className="receipt">
              <h2>HONIM</h2>
              <p>{selected.status === 'paid' ? 'TO‘LOV QAYDI' : 'OLDINDAN HISOB'}</p>
              <small>{dateLabel(selected.created_at)} · #{selected.id}</small>
              {selected.table && <p>Stol: {selected.table} · {selected.waiter}</p>}
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
              <div className="cart-total"><span>JAMI</span><strong>{money(selected.total)}</strong></div>
              <p>{methodLabel(selected.payment_method)}</p>
              <small>Mahalliy sinov cheki · fiskal chek emas</small>
            </div>
            {error && <p className="alert error">{error}</p>}
            {selected.status === 'open' && (
              <form onSubmit={pay}>
                <label>
                  To‘lov usuli
                  <select value={method} onChange={event => setMethod(event.target.value)}>
                    {methods.map(item => <option key={item.method} value={item.method}>{item.label}</option>)}
                  </select>
                </label>
                <button className="button primary full" disabled={busy}>
                  {busy ? 'Saqlanmoqda…' : 'To‘lovni qayd etish'}
                </button>
              </form>
            )}
            {printed && <p className="alert success">{printed}</p>}
            <button className="button primary full" disabled={printing} onClick={printReceipt}>
              <Printer size={17} />{printing ? 'Chiqarilmoqda…' : 'Chekni chop etish'}
            </button>
            <button className="button secondary full" onClick={() => window.print()}>
              Brauzer orqali chiqarish
            </button>
          </>
        )}
      </AppModal>
    </>
  )
}
