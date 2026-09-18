import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Printer, RefreshCw, ShoppingBag, Users } from 'lucide-react'
import { api, list, money } from '../api'
import { useSession } from '../session'
import type { Order, Table, TableZone } from '../types'
import AppModal from '../components/AppModal'

/** Zal chizmasi: kirganda chapda divanlar, o'ngda stulli stollar, tashqarida alohida. */
const ZONES: { key: TableZone; title: string }[] = [
  { key: 'hall_left', title: 'Chap tomon · divan' },
  { key: 'hall_right', title: 'O‘ng tomon · stulli' },
]

function minutesSince(iso: string) {
  const passed = Math.round((Date.now() - new Date(iso).getTime()) / 60000)
  if (passed < 1) return 'hozir'
  if (passed < 60) return `${passed} daq`
  return `${Math.floor(passed / 60)} soat ${passed % 60} daq`
}

function TableCard({ table, onOpen }: { table: Table; onOpen: (table: Table) => void }) {
  const open = table.open_order
  const classes = ['table-card', open ? 'busy' : '', table.seating === 'divan' ? 'divan' : '']
  return (
    <button className={classes.filter(Boolean).join(' ')} onClick={() => onOpen(table)}>
      <strong>{table.label}</strong>
      {open ? (
        <>
          <span className="table-total">{money(open.total)} so‘m</span>
          <span className="table-meta">{open.items} taom · {minutesSince(open.created_at)}</span>
          {open.waiter && <span className="table-meta">{open.waiter}</span>}
        </>
      ) : (
        <>
          <span className="table-state">Bo‘sh</span>
          <span className="table-meta">{table.seats} o‘rin</span>
        </>
      )}
    </button>
  )
}

export default function TablesPage() {
  const navigate = useNavigate()
  const { user } = useSession()
  const [tables, setTables] = useState<Table[]>([])
  const [selected, setSelected] = useState<Table>()
  const [bill, setBill] = useState<Order>()
  const [method, setMethod] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = useCallback(async () => {
    try {
      setTables((await list<Table>('tables/')).filter(item => item.active))
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

  async function reprint() {
    if (!bill) return
    setBusy(true)
    setError('')
    try {
      await api(`orders/${bill.id}/print/`, { method: 'POST' })
      setNotice('Chek printerga yuborildi.')
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
          <span className="eyebrow">SAVDO ISH JOYI</span>
          <h1>Stollar<span className="heading-dot">.</span></h1>
          <p>Bo‘sh stolga bosing — buyurtma oching. Band stolga bosing — hisob va to‘lov.</p>
        </div>
        <div className="heading-actions">
          <button className="button secondary icon-button" aria-label="Yangilash" onClick={load}>
            <RefreshCw size={17} className={loading ? 'spin' : undefined} />
          </button>
          <button className="button primary" onClick={() => navigate('/pos/tezkor')}>
            <ShoppingBag size={17} />Tezkor savdo
          </button>
        </div>
      </div>

      {error && <p className="alert error" role="alert">{error}</p>}

      <div className="inventory-summary">
        <div><Users size={21} /><span><strong>{busyCount}</strong> band stol</span></div>
        <div><span className="warning-dot" /><span><strong>{money(openTotal)}</strong> so‘m ochiq hisobda</span></div>
        <p>Band stollar sariq rangda. Chapdagi uchtasi divanli, qolganlari stulli.</p>
      </div>

      {loading && !tables.length && <div className="empty-state">Stollar yuklanmoqda…</div>}

      <div className="floor">
        <section className="floor-zone">
          <header><h2>Ichkari zal</h2><span>KIRISH PASTDA</span></header>
          <div className="floor-hall">
            <div className="floor-side">
              <small>{ZONES[0].title.toUpperCase()}</small>
              <div className="table-grid">
                {zoneTables('hall_left').map(table => (
                  <TableCard key={table.id} table={table} onOpen={openTable} />
                ))}
              </div>
            </div>
            <div className="floor-divider" />
            <div className="floor-side">
              <small>{ZONES[1].title.toUpperCase()}</small>
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
            <header><h2>Tashqari</h2><span>{outside.length} TA STOL</span></header>
            <div className="table-grid">
              {outside.map(table => <TableCard key={table.id} table={table} onOpen={openTable} />)}
            </div>
          </section>
        )}
      </div>

      <AppModal
        open={!!selected}
        title={`${selected?.label || ''} · hisob`}
        onClose={() => { if (!busy) { setSelected(undefined); setBill(undefined) } }}
      >
        {bill && (
          <>
            <div className="cart-total">
              <span>Jami</span>
              <strong>{money(bill.total)} <small>so‘m</small></strong>
            </div>
            <div className="bill-lines">
              {bill.lines.map(line => (
                <div key={line.id}>
                  <span>
                    {line.quantity} × {line.name}
                    {line.note && <small>izoh: {line.note}</small>}
                  </span>
                  <strong>{money(Number(line.price) * line.quantity)}</strong>
                </div>
              ))}
            </div>

            <button
              className="button secondary full"
              disabled={busy}
              onClick={() => navigate(`/pos/hisob/${bill.id}`)}
            >
              <Plus size={17} />Taom qo‘shish
            </button>

            <p className="nav-caption">TO‘LOVNI QAYD ETISH</p>
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
              <Printer size={17} />Chekni chop etish
            </button>
          </>
        )}
      </AppModal>
    </>
  )
}
