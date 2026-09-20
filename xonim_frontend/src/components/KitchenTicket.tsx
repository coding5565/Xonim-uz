import { dateLabel } from '../api'
import { useI18n } from '../i18n'
import type { Order } from '../types'

export default function KitchenTicket({ order }: { order: Order }) {
  const { t } = useI18n()
  return (
    <div className="ticket-body">
      <div className="ticket-top">
        <strong>#{String(order.id).padStart(4, '0')}</strong>
        <time>{dateLabel(order.created_at)}</time>
      </div>
      <div className="ticket-place">
        {order.table
          ? `${t('{table}-stol', { table: order.table })} · ${order.waiter || t('Ofitsiant')}`
          : t(order.channel_label)}
      </div>
      <div className="ticket-lines">
        {order.lines.map(line => (
          <div key={line.id} className="ticket-line">
            <strong>{line.quantity} × {line.name}</strong>
            {line.note && <p>{t('Izoh')}: {line.note}</p>}
          </div>
        ))}
      </div>
      <small>{t('Kiritgan: {name}', { name: order.cashier_name || t('Kassa') })}</small>
    </div>
  )
}
