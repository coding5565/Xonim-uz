import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, ChefHat, Clock3, RefreshCw, Utensils } from 'lucide-react'
import { api } from '../api'
import type { Order } from '../types'
import KitchenTicket from '../components/KitchenTicket'

const actionLabel = (status: string) =>
  status === 'queued' ? 'Tayyorlashni boshlash'
    : status === 'preparing' ? 'Tayyor bo‘ldi'
      : 'Mijozga topshirildi'

export default function KitchenPage() {
  const [orders, setOrders] = useState<Order[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState<number>()
  const [error, setError] = useState('')
  const [updated, setUpdated] = useState<Date>()

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      setOrders(await api<Order[]>('kitchen/orders/'))
      setUpdated(new Date())
      setError('')
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const timer = window.setInterval(() => load(true), 4000)
    return () => window.clearInterval(timer)
  }, [load])

  async function advance(order: Order) {
    const next = order.preparation_status === 'queued' ? 'preparing'
      : order.preparation_status === 'preparing' ? 'ready'
        : 'served'
    setBusy(order.id)
    setError('')
    try {
      await api(`kitchen/orders/${order.id}/status/`, { method: 'POST', body: JSON.stringify({ status: next }) })
      await load(true)
    } catch (exception) {
      setError((exception as Error).message)
      await load(true)
    } finally {
      setBusy(undefined)
    }
  }

  const queued = orders.filter(order => order.preparation_status === 'queued')
  const preparing = orders.filter(order => order.preparation_status === 'preparing')
  const ready = orders.filter(order => order.preparation_status === 'ready')

  const columns = [
    { key: 'queued', rows: queued, icon: Clock3, actionIcon: ChefHat, title: 'Yangi buyurtmalar', caption: 'Tayyorlashni boshlash kerak', empty: 'Yangi buyurtma yo‘q', emptyIcon: CheckCircle2, isNew: true },
    { key: 'preparing', rows: preparing, icon: ChefHat, actionIcon: CheckCircle2, title: 'Tayyorlanmoqda', caption: 'Oshpaz ishlayotgan buyurtmalar', empty: 'Jarayonda buyurtma yo‘q', emptyIcon: ChefHat, isNew: false },
    { key: 'ready', rows: ready, icon: CheckCircle2, actionIcon: Utensils, title: 'Tayyor', caption: 'Mijozga berilishi kerak', empty: 'Tayyor buyurtma yo‘q', emptyIcon: Utensils, isNew: false },
  ]

  return (
    <>
      <div className="page-heading kitchen-heading">
        <div>
          <span className="eyebrow">JONLI OSHXONA EKRANI</span>
          <h1>Oshxona<span className="heading-dot">.</span></h1>
          <p>Kassadan tushgan buyurtmalar har 4 soniyada avtomatik yangilanadi.</p>
        </div>
        <button className="button secondary" disabled={loading} onClick={() => load()}>
          <RefreshCw size={17} className={loading ? 'spin' : undefined} />Yangilash
        </button>
      </div>
      {error && <p className="alert error">{error}</p>}
      <div className="kitchen-summary">
        <div><span className="kitchen-dot queued" /><strong>{queued.length}</strong><small>Yangi</small></div>
        <div><span className="kitchen-dot preparing" /><strong>{preparing.length}</strong><small>Tayyorlanmoqda</small></div>
        <div><span className="kitchen-dot ready" /><strong>{ready.length}</strong><small>Tayyor</small></div>
        {updated && (
          <span>
            Yangilandi: {updated.toLocaleTimeString('uz-UZ', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
          </span>
        )}
      </div>
      <div className="kitchen-board">
        {columns.map(column => {
          const Icon = column.icon
          const ActionIcon = column.actionIcon
          const EmptyIcon = column.emptyIcon
          return (
            <section key={column.key} className={`kitchen-column ${column.key}`}>
              <header>
                <Icon size={19} />
                <div><h2>{column.title}</h2><p>{column.caption}</p></div>
                <strong>{column.rows.length}</strong>
              </header>
              <div className="kitchen-cards">
                {column.rows.map(order => (
                  <article key={order.id} className={`kitchen-ticket${column.isNew ? ' is-new' : ''}`}>
                    <KitchenTicket order={order} />
                    <button className="button kitchen-action" disabled={busy === order.id} onClick={() => advance(order)}>
                      <ActionIcon size={17} />
                      {busy === order.id ? 'Saqlanmoqda…' : actionLabel(order.preparation_status)}
                    </button>
                  </article>
                ))}
                {!column.rows.length && (
                  <div className="kitchen-empty"><EmptyIcon /><span>{column.empty}</span></div>
                )}
              </div>
            </section>
          )
        })}
      </div>
    </>
  )
}
