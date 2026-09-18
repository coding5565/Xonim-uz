import { dateLabel } from '../api'
import type { Order } from '../types'

export default function KitchenTicket({ order }: { order: Order }) {
  return (
    <div className="ticket-body">
      <div className="ticket-top">
        <strong>#{String(order.id).padStart(4, '0')}</strong>
        <time>{dateLabel(order.created_at)}</time>
      </div>
      <div className="ticket-place">
        {order.table ? `${order.table}-stol · ${order.waiter || 'Ofitsiant'}` : 'Tezkor savdo'}
      </div>
      <div className="ticket-lines">
        {order.lines.map(line => (
          <div key={line.id} className="ticket-line">
            <strong>{line.quantity} × {line.name}</strong>
            {line.note && <p>Izoh: {line.note}</p>}
          </div>
        ))}
      </div>
      <small>Kiritgan: {order.cashier_name || 'Kassa'}</small>
    </div>
  )
}
