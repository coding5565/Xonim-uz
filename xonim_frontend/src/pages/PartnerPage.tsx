import { useCallback, useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  AlertTriangle, ArrowLeft, Ban, ClipboardCheck, HandCoins, Pencil, RefreshCw, Tags, Truck, Undo2,
} from 'lucide-react'
import { api, dateLabel, list, money, today as todayKey } from '../api'
import AppModal from '../components/AppModal'
import { useI18n } from '../i18n'
import { useSession } from '../session'
import { CardsSkeleton, PanelSkeleton } from '../components/Skeleton'
import type { Dish, PartnerBoard, PartnerBoardRow, PartnerDelivery } from '../types'

const KIND_NAMES: Record<string, string> = {
  school: 'Maktab', university: 'Universitet', office: 'Ofis', other: 'Boshqa',
}
const STATUS_NAMES: Record<PartnerDelivery['status'], string> = {
  sent: 'Jo‘natildi', reported: 'Hisobot berildi', settled: 'Yopildi', cancelled: 'Bekor qilingan',
}

interface SettleForm {
  key: string
  amount: string
  payment_method: string
  paid_on: string
  note: string
}

/** Kiritilgan matnni butun songa aylantiradi; bo'sh va noto'g'risi nol. */
function count(value: string | undefined) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? Math.floor(parsed) : 0
}

/**
 * Bitta hamkorning ichki sahifasi — bu yerda hamma ish individual qilinadi.
 *
 * Kunning tartibi shu sahifada yuqoridan pastga o'qiladi: ertalab
 * «Jo'natish», kechqurun «Hisobot», so'ng «Pul qabul qilish». Shartnoma
 * narxlari eng pastda, chunki ular kuniga emas, oyiga bir marta
 * o'zgaradi.
 */
export default function PartnerPage() {
  const { t, tn } = useI18n()
  const { partnerId } = useParams()
  const navigate = useNavigate()
  const { user } = useSession()
  const owner = user?.role === 'owner'
  const id = Number(partnerId)

  const [board, setBoard] = useState<PartnerBoard>()
  const [dishes, setDishes] = useState<Dish[]>([])
  const [error, setError] = useState('')
  const [formError, setFormError] = useState('')
  const [busy, setBusy] = useState(false)

  // Jo'natish: taom id -> kiritilgan porsiya soni.
  const [sendOpen, setSendOpen] = useState(false)
  const [sendKey, setSendKey] = useState('')
  const [sendDraft, setSendDraft] = useState<Record<number, string>>({})
  const [sendNote, setSendNote] = useState('')

  // Hisobot: qator id -> nechta sotilgani.
  const [reporting, setReporting] = useState<PartnerDelivery>()
  const [reportDraft, setReportDraft] = useState<Record<number, string>>({})

  // Pul qabul qilish.
  const [settling, setSettling] = useState<PartnerDelivery>()
  const [settleForm, setSettleForm] = useState<SettleForm>({
    key: '', amount: '', payment_method: 'cash', paid_on: todayKey(), note: '',
  })

  // Bekor qilish: jo'natma yoki to'lov, ikkalasi ham sabab so'raydi.
  const [cancelling, setCancelling] = useState<PartnerDelivery>()
  const [voiding, setVoiding] = useState<{ id: number; amount: string }>()
  const [reason, setReason] = useState('')

  // Shartnoma narxlari: taom id -> narx matni.
  const [pricesOpen, setPricesOpen] = useState(false)
  const [priceDraft, setPriceDraft] = useState<Record<number, string>>({})
  const [priceWarnings, setPriceWarnings] = useState<string[]>([])

  const load = useCallback(async () => {
    setError('')
    try {
      // Davr — oxirgi 60 kun: bugungi ish ham, yopilmagan eski jo'natma ham
      // bitta sahifada ko'rinishi kerak.
      const start = new Date(`${todayKey()}T00:00:00`)
      start.setDate(start.getDate() - 60)
      const query = new URLSearchParams({
        partner: String(id), start: start.toISOString().slice(0, 10), end: todayKey(),
      })
      setBoard(await api<PartnerBoard>(`partner-board/?${query}`))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [id])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    list<Dish>('dishes/').then(setDishes).catch(() => setDishes([]))
  }, [])

  const partner: PartnerBoardRow | undefined = board?.partners.find(row => row.id === id)
  const deliveries = board?.deliveries || []
  const methods = board?.payment_methods || []

  // Narxi bor taomlar jo'natish oynasida tanlanadi; qolgani ham ko'rinadi,
  // lekin yozib bo'lmaydi — nega jo'natilmayotgani shundan ma'lum bo'ladi.
  const priced = useMemo(() => {
    const table = new Map((partner?.prices || []).map(row => [row.dish, row]))
    return dishes
      .filter(dish => !dish.archived && table.has(dish.id))
      .map(dish => ({ dish, price: table.get(dish.id)! }))
  }, [dishes, partner])
  const unpriced = useMemo(
    () => dishes.filter(dish => !dish.archived && !(partner?.prices || []).some(row => row.dish === dish.id)),
    [dishes, partner],
  )

  const sendLines = Object.entries(sendDraft)
    .map(([dish, value]) => ({ dish: Number(dish), quantity: count(value) }))
    .filter(line => line.quantity > 0)
  const sendTotal = sendLines.reduce((sum, line) => {
    const row = priced.find(item => item.dish.id === line.dish)
    return sum + (row ? Number(row.price.price) * line.quantity : 0)
  }, 0)

  const reportDue = (reporting?.lines || []).reduce(
    (sum, line) => sum + Number(line.price) * Math.min(count(reportDraft[line.id]), line.quantity), 0)

  /** Har bir amal uchun bitta naqsh: yubor, xatoni ko'rsat, sahifani yangila. */
  async function run(action: () => Promise<unknown>, close: () => void) {
    if (busy) return
    setBusy(true)
    setFormError('')
    try {
      await action()
      close()
      await load()
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function startSend() {
    // Kalit oyna ochilganda tug'iladi: ikki marta bosilsa ham bitta jo'natma.
    setSendKey(crypto.randomUUID())
    setSendDraft({})
    setSendNote('')
    setFormError('')
    setSendOpen(true)
  }

  function startReport(delivery: PartnerDelivery) {
    // Odatdagi hol — hammasi sotilgan, shuning uchun to'liq son oldindan
    // turadi va kassir faqat sotilmaganini tuzatadi.
    setReportDraft(Object.fromEntries(delivery.lines.map(line => [
      line.id, String(delivery.reported_at ? line.sold : line.quantity),
    ])))
    setFormError('')
    setReporting(delivery)
  }

  function startSettle(delivery: PartnerDelivery) {
    setSettleForm({
      key: crypto.randomUUID(),
      amount: delivery.remaining,
      payment_method: methods[0]?.method || 'cash',
      paid_on: todayKey(),
      note: '',
    })
    setFormError('')
    setSettling(delivery)
  }

  function startPrices() {
    setPriceDraft(Object.fromEntries((partner?.prices || []).map(row => [row.dish, row.price])))
    setPriceWarnings([])
    setFormError('')
    setPricesOpen(true)
  }

  async function savePrices(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    setBusy(true)
    setFormError('')
    try {
      const rows = Object.entries(priceDraft)
        .map(([dish, value]) => ({ dish: Number(dish), price: Number(value) }))
        .filter(row => row.price > 0)
      const answer = await api<{ warnings: string[] }>(`partners/${id}/prices/`, {
        method: 'PUT', body: JSON.stringify({ rows }),
      })
      setPriceWarnings(answer.warnings || [])
      await load()
      if (!answer.warnings?.length) setPricesOpen(false)
    } catch (exception) {
      setFormError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  if (!board) {
    return (
      <>
        <CardsSkeleton />
        <section className="panel"><PanelSkeleton rows={5} /></section>
      </>
    )
  }

  if (!partner) {
    return (
      <section className="panel">
        <div className="empty-state">
          <strong>{t('Hamkor topilmadi.')}</strong>
          <Link to="/hamkorlar" className="button secondary"><ArrowLeft size={16} />{t('Hamkorlar')}</Link>
        </div>
      </section>
    )
  }

  const open = deliveries.filter(row => row.status === 'sent')
  const owing = deliveries.filter(row => row.status === 'reported' && Number(row.remaining) > 0)

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">
            <Link to="/hamkorlar" className="text-link">{t('Hamkorlar')}</Link> · {t(KIND_NAMES[partner.kind] || partner.kind_label)}
          </span>
          <h1>{partner.name}<span className="heading-dot">.</span></h1>
          <p>
            {[partner.contact, partner.phone, partner.address].filter(Boolean).join(' · ')
              || t('Shartnoma bo‘yicha taom yetkazib beriladi.')}
          </p>
        </div>
        <div className="heading-actions">
          <button className="button secondary" onClick={() => load()}><RefreshCw size={17} />{t('Yangilash')}</button>
          {owner && (
            <button className="button secondary" onClick={startPrices}>
              <Tags size={17} />{t('Shartnoma narxlari')}
            </button>
          )}
          <button className="button primary" disabled={!partner.active} onClick={startSend}>
            <Truck size={17} />{t('Taom jo‘natish')}
          </button>
        </div>
      </div>

      {error && <p className="alert error">{error}</p>}
      {!partner.active && (
        <p className="alert">{t('Bu hamkor faolsizlantirilgan — yangi jo‘natma yozib bo‘lmaydi, lekin eski hisobni yopish mumkin.')}</p>
      )}

      <div className="report-metrics">
        <article>
          <span className="metric-icon blue"><Truck /></span>
          <div>
            <small>{t('Jo‘natilgan (60 kun)')}</small>
            <strong>{money(partner.sent_value)} <em>{t('so‘m')}</em></strong>
            <em>{tn('{count} porsiya', partner.sent_portions)}</em>
          </div>
        </article>
        <article>
          <span className="metric-icon violet"><ClipboardCheck /></span>
          <div>
            <small>{t('Hisobot kutilmoqda')}</small>
            <strong>{money(partner.pending_value)} <em>{t('so‘m')}</em></strong>
            <em>{tn('{count} ta jo‘natma', partner.pending_count)}</em>
          </div>
        </article>
        <article>
          <span className={`metric-icon ${Number(partner.debt) > 0 ? 'orange' : 'green'}`}><AlertTriangle /></span>
          <div>
            <small>{t('Qarz')}</small>
            <strong>{money(partner.debt)} <em>{t('so‘m')}</em></strong>
            <em>{partner.oldest_days > 0 ? tn('{count} kundan beri', partner.oldest_days) : t('qarz yo‘q')}</em>
          </div>
        </article>
        <article>
          <span className="metric-icon green"><HandCoins /></span>
          <div>
            <small>{t('Tushgan pul (60 kun)')}</small>
            <strong>{money(board.summary.received)} <em>{t('so‘m')}</em></strong>
            <em>{tn('{count} ta to‘lov', board.summary.settlements)}</em>
          </div>
        </article>
      </div>

      {(!!open.length || !!owing.length) && (
        <p className="alert">
          {!!open.length && tn('{count} ta jo‘natma bo‘yicha hisobot kutilmoqda.', open.length)}
          {!!open.length && !!owing.length && ' '}
          {!!owing.length && tn('{count} ta jo‘natma to‘lanmagan.', owing.length)}
        </p>
      )}

      <section className="panel spaced">
        <header className="panel-heading">
          <div>
            <h2><Truck size={17} /> {t('Jo‘natmalar')}</h2>
            <p>{t('Ertalab jo‘natiladi, kechqurun nechtasi sotilgani kiritiladi, so‘ng puli olinadi.')}</p>
          </div>
          <span className="muted">{tn('{count} ta jo‘natma', deliveries.length)}</span>
        </header>
        <div className="partner-deliveries">
          {deliveries.map(delivery => (
            <article key={delivery.id} className={`partner-delivery ${delivery.status}`}>
              <header>
                <div>
                  <strong>{delivery.date}</strong>
                  <small>
                    {t(STATUS_NAMES[delivery.status] || delivery.status_label)} · {delivery.actor_name}
                    {delivery.reported_at ? ` · ${t('hisobot')} ${dateLabel(delivery.reported_at)}` : ''}
                  </small>
                </div>
                <div className="partner-delivery-money">
                  <span>
                    <small>{t('Jo‘natilgan')}</small>
                    <strong>{money(delivery.total)}</strong>
                  </span>
                  <span>
                    <small>{t('Qarz')}</small>
                    <strong className={Number(delivery.remaining) > 0 ? 'owed' : undefined}>
                      {delivery.reported_at ? money(delivery.remaining) : '—'}
                    </strong>
                  </span>
                </div>
              </header>
              <ul className="partner-lines">
                {delivery.lines.map(line => (
                  <li key={line.id}>
                    <span>{line.name}</span>
                    <small>
                      {delivery.reported_at
                        ? t('{sent} dan {sold} ta sotildi', { sent: line.quantity, sold: line.sold })
                        : tn('{count} porsiya', line.quantity)}
                      {' · '}{money(line.price)} {t('so‘m')}
                    </small>
                    <strong>{money(delivery.reported_at ? line.earned : line.value)}</strong>
                  </li>
                ))}
              </ul>
              {delivery.note && <p className="muted">{delivery.note}</p>}
              {delivery.cancel_reason && (
                <p className="muted">{t('Bekor qilish sababi')}: {delivery.cancel_reason}</p>
              )}
              {!!delivery.settlements.length && (
                <div className="partner-payments">
                  {delivery.settlements.map(item => (
                    <span key={item.id} className={item.voided_at ? 'voided' : undefined}>
                      <strong>{money(item.amount)} {t('so‘m')}</strong>
                      <small>
                        {item.paid_on} · {t(methods.find(one => one.method === item.payment_method)?.label
                          || item.payment_method)}
                        {item.voided_at ? ` · ${t('bekor qilingan')}: ${item.void_reason}` : ''}
                      </small>
                      {owner && !item.voided_at && (
                        <button
                          className="text-link"
                          title={t('To‘lovni bekor qilish')}
                          onClick={() => { setReason(''); setFormError(''); setVoiding({ id: item.id, amount: item.amount }) }}
                        >
                          <Undo2 size={14} />
                        </button>
                      )}
                    </span>
                  ))}
                </div>
              )}
              <footer>
                {delivery.status !== 'cancelled' && (
                  <button className="button secondary small" onClick={() => startReport(delivery)}>
                    <ClipboardCheck size={15} />
                    {delivery.reported_at ? t('Hisobotni tuzatish') : t('Hisobot kiritish')}
                  </button>
                )}
                {delivery.status === 'reported' && Number(delivery.remaining) > 0 && (
                  <button className="button primary small" onClick={() => startSettle(delivery)}>
                    <HandCoins size={15} />{t('Pul qabul qilish')}
                  </button>
                )}
                {owner && delivery.status === 'sent' && (
                  <button
                    className="button danger small"
                    onClick={() => { setReason(''); setFormError(''); setCancelling(delivery) }}
                  >
                    <Ban size={15} />{t('Bekor qilish')}
                  </button>
                )}
              </footer>
            </article>
          ))}
          {!deliveries.length && (
            <div className="empty-state">
              <Truck size={34} strokeWidth={1.4} />
              <strong>{t('Oxirgi 60 kunda jo‘natma bo‘lmagan')}</strong>
              <p>{t('«Taom jo‘natish» tugmasi orqali bugungi porsiyalarni yozing.')}</p>
            </div>
          )}
        </div>
      </section>

      <section className="panel">
        <header className="panel-heading">
          <div>
            <h2><Tags size={17} /> {t('Shartnoma narxlari')}</h2>
            <p>{t('Narx bir marta belgilanadi va istalgan kuni o‘zgartiriladi — o‘zgarish faqat keyingi jo‘natmalarga tegadi.')}</p>
          </div>
          {owner && (
            <button className="button secondary small" onClick={startPrices}><Pencil size={15} />{t('O‘zgartirish')}</button>
          )}
        </header>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('TAOM')}</th>
                <th className="number">{t('HAMKOR NARXI')}</th>
                <th className="number">{t('MENYU NARXI')}</th>
                <th className="number">{t('CHEGIRMA')}</th>
              </tr>
            </thead>
            <tbody>
              {partner.prices.map(row => {
                const discount = Number(row.menu_price) - Number(row.price)
                return (
                  <tr key={row.dish} className={row.archived ? 'row-muted' : undefined}>
                    <td>
                      <strong>{row.dish_name}</strong>
                      {row.archived && <small>{t('arxivlangan')}</small>}
                    </td>
                    <td className="number"><strong>{money(row.price)}</strong></td>
                    <td className="number">{money(row.menu_price)}</td>
                    <td className="number">
                      {discount > 0 ? `−${money(discount)}` : discount < 0 ? `+${money(-discount)}` : '—'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          {!partner.prices.length && (
            <div className="empty-state compact">
              <strong>{t('Shartnoma narxi belgilanmagan')}</strong>
              <p>{t('Narxsiz taomni hamkorga jo‘natib bo‘lmaydi.')}</p>
            </div>
          )}
        </div>
      </section>

      {/* ── Jo'natish ── */}
      <AppModal
        open={sendOpen}
        title={t('{name} · taom jo‘natish', { name: partner.name })}
        onClose={() => { if (!busy) setSendOpen(false) }}
      >
        <form onSubmit={event => {
          event.preventDefault()
          run(() => api('partner-deliveries/', {
            method: 'POST',
            body: JSON.stringify({ key: sendKey, partner: id, note: sendNote, lines: sendLines }),
          }), () => setSendOpen(false))
        }}>
          <div className="prep-grid">
            {priced.map(({ dish, price }) => (
              <label key={dish.id} className="prep-tile">
                <span className="prep-name">{dish.name}</span>
                <span className="prep-state">
                  {money(price.price)} {t('so‘m')} · {t('menyuda {amount}', { amount: money(price.menu_price) })}
                </span>
                <input
                  value={sendDraft[dish.id] ?? ''}
                  onChange={event => setSendDraft(previous => ({ ...previous, [dish.id]: event.target.value }))}
                  type="number"
                  min="0"
                  max="9999"
                  step="1"
                  inputMode="numeric"
                  placeholder="0"
                  aria-label={t('{name} uchun porsiya soni', { name: dish.name })}
                />
              </label>
            ))}
          </div>
          {!priced.length && (
            <p className="alert">
              {t('Bu hamkor uchun hali narx belgilanmagan — jo‘natishdan oldin shartnoma narxlarini kiriting.')}
            </p>
          )}
          {!!unpriced.length && (
            <details className="partner-unpriced">
              <summary>{tn('Shartnomada narxi yo‘q: {count} ta taom', unpriced.length)}</summary>
              <p className="muted">{unpriced.map(dish => dish.name).join(', ')}</p>
            </details>
          )}
          <label>
            {t('Izoh (ixtiyoriy)')}
            <input
              value={sendNote}
              onChange={event => setSendNote(event.target.value)}
              maxLength={250}
              placeholder={t('Masalan, ikkinchi mashina')}
            />
          </label>
          <div className="salary-amount">
            {money(sendTotal)} <small>{t('so‘m')}</small>
          </div>
          <p className="data-note">
            {t('Bu — hammasi sotilgandagi summa. Kechqurun nechtasi sotilgani kiritilguncha jo‘natma «hisobot kutilmoqda» bo‘lib turadi.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy || !sendLines.length}>
            {busy ? t('Saqlanmoqda…') : t('Jo‘natildi deb yozish')}
          </button>
        </form>
      </AppModal>

      {/* ── Kechqurungi hisobot ── */}
      <AppModal
        open={!!reporting}
        title={t('Hisobot · {date}', { date: reporting?.date || '' })}
        onClose={() => { if (!busy) setReporting(undefined) }}
      >
        <form onSubmit={event => {
          event.preventDefault()
          if (!reporting) return
          run(() => api(`partner-deliveries/${reporting.id}/report/`, {
            method: 'POST',
            body: JSON.stringify({
              lines: reporting.lines.map(line => ({ line: line.id, sold: count(reportDraft[line.id]) })),
            }),
          }), () => setReporting(undefined))
        }}>
          <p className="muted">{t('Nechtasi sotilganini kiriting. Sotilmagani zarar bo‘lib qoladi — puli olinmaydi.')}</p>
          <div className="report-lines">
            {(reporting?.lines || []).map(line => {
              const sold = Math.min(count(reportDraft[line.id]), line.quantity)
              return (
                <div key={line.id} className="report-line">
                  <div>
                    <strong>{line.name}</strong>
                    <small>{tn('{count} porsiya jo‘natilgan', line.quantity)} · {money(line.price)} {t('so‘m')}</small>
                  </div>
                  <input
                    value={reportDraft[line.id] ?? ''}
                    onChange={event => setReportDraft(previous => ({ ...previous, [line.id]: event.target.value }))}
                    type="number"
                    min="0"
                    max={line.quantity}
                    step="1"
                    inputMode="numeric"
                    required
                    aria-label={t('{name}: nechtasi sotildi', { name: line.name })}
                  />
                  <span className={line.quantity - sold > 0 ? 'unsold' : undefined}>
                    {line.quantity - sold > 0 ? tn('{count} ta sotilmadi', line.quantity - sold) : t('hammasi sotildi')}
                  </span>
                </div>
              )
            })}
          </div>
          <div className="salary-amount">{money(reportDue)} <small>{t('so‘m to‘lanishi kerak')}</small></div>
          {!!reporting?.settlements.some(item => !item.voided_at) && (
            <p className="alert">
              {t('Bu jo‘natma bo‘yicha {amount} so‘m allaqachon olingan — hisobotni undan pastga tushirib bo‘lmaydi.', {
                amount: money(reporting.settled_total),
              })}
            </p>
          )}
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('Hisobotni saqlash')}
          </button>
        </form>
      </AppModal>

      {/* ── Pul qabul qilish ── */}
      <AppModal
        open={!!settling}
        title={t('{name} · pul qabul qilish', { name: partner.name })}
        onClose={() => { if (!busy) setSettling(undefined) }}
      >
        <form onSubmit={event => {
          event.preventDefault()
          if (!settling) return
          run(() => api(`partner-deliveries/${settling.id}/settle/`, {
            method: 'POST', body: JSON.stringify(settleForm),
          }), () => setSettling(undefined))
        }}>
          <div className="salary-amount">{money(settleForm.amount || 0)} <small>{t('so‘m')}</small></div>
          {!!settling && (
            <p className="alert">
              {t('{date} kungi jo‘natma · qarz {amount} so‘m', {
                date: settling.date, amount: money(settling.remaining),
              })}
            </p>
          )}
          <div className="form-row">
            <label>
              {t('Summa')}
              <input
                value={settleForm.amount}
                onChange={event => setSettleForm({ ...settleForm, amount: event.target.value })}
                type="number"
                min="1"
                step="any"
                max={settling?.remaining}
                required
                autoFocus
              />
            </label>
            <label>
              {t('To‘lov sanasi')}
              <input
                value={settleForm.paid_on}
                onChange={event => setSettleForm({ ...settleForm, paid_on: event.target.value })}
                type="date"
                max={todayKey()}
                required
              />
            </label>
          </div>
          <label>
            {t('To‘lov usuli')}
            <select
              value={settleForm.payment_method}
              onChange={event => setSettleForm({ ...settleForm, payment_method: event.target.value })}
            >
              {methods.map(item => <option key={item.method} value={item.method}>{t(item.label)}</option>)}
            </select>
          </label>
          <label>
            {t('Izoh')}
            <textarea
              value={settleForm.note}
              onChange={event => setSettleForm({ ...settleForm, note: event.target.value })}
              maxLength={250}
              rows={2}
            />
          </label>
          <p className="data-note">
            {t('Naqd olingan pul kassaga tushadi va «Kun yakuni»dagi kutilgan naqdga qo‘shiladi.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('Pul olindi deb yozish')}
          </button>
        </form>
      </AppModal>

      {/* ── Jo'natmani bekor qilish ── */}
      <AppModal
        open={!!cancelling}
        title={t('Jo‘natmani bekor qilish')}
        onClose={() => { if (!busy) setCancelling(undefined) }}
      >
        <form onSubmit={event => {
          event.preventDefault()
          if (!cancelling) return
          run(() => api(`partner-deliveries/${cancelling.id}/cancel/`, {
            method: 'POST', body: JSON.stringify({ reason }),
          }), () => setCancelling(undefined))
        }}>
          <p className="alert">
            {t('{date} kungi jo‘natma bekor qilinadi va masalliq omborga qaytariladi. Hisobot berilgandan keyin buni qilib bo‘lmaydi.', {
              date: cancelling?.date || '',
            })}
          </p>
          <label>
            {t('Sabab')}
            <input
              value={reason}
              onChange={event => setReason(event.target.value)}
              minLength={3}
              maxLength={200}
              required
              autoFocus
              placeholder={t('Masalan, mashina ketmadi')}
            />
          </label>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button danger full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('Bekor qilish')}
          </button>
        </form>
      </AppModal>

      {/* ── To'lovni bekor qilish ── */}
      <AppModal
        open={!!voiding}
        title={t('To‘lovni bekor qilish')}
        onClose={() => { if (!busy) setVoiding(undefined) }}
      >
        <form onSubmit={event => {
          event.preventDefault()
          if (!voiding) return
          run(() => api(`partner-settlements/${voiding.id}/void/`, {
            method: 'POST', body: JSON.stringify({ reason }),
          }), () => setVoiding(undefined))
        }}>
          <p className="alert">
            {t('{amount} so‘m to‘lov bekor qilinadi va qarz qaytadi. Yozuv tarixda qoladi.', {
              amount: money(voiding?.amount || 0),
            })}
          </p>
          <label>
            {t('Sabab')}
            <input
              value={reason}
              onChange={event => setReason(event.target.value)}
              minLength={3}
              maxLength={200}
              required
              autoFocus
            />
          </label>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button danger full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('To‘lovni bekor qilish')}
          </button>
        </form>
      </AppModal>

      {/* ── Shartnoma narxlari ── */}
      <AppModal
        open={pricesOpen}
        title={t('{name} · shartnoma narxlari', { name: partner.name })}
        onClose={() => { if (!busy) setPricesOpen(false) }}
      >
        <form onSubmit={savePrices}>
          <p className="muted">
            {t('Narxni faqat hamkorga jo‘natiladigan taomlarga qo‘ying. Bo‘sh qoldirilgan taom ro‘yxatdan chiqadi.')}
          </p>
          <div className="price-rows">
            {dishes.filter(dish => !dish.archived).map(dish => (
              <label key={dish.id} className="price-row">
                <span>
                  <strong>{dish.name}</strong>
                  <small>{t('menyuda {amount}', { amount: money(dish.price) })}</small>
                </span>
                <input
                  value={priceDraft[dish.id] ?? ''}
                  onChange={event => setPriceDraft(previous => ({ ...previous, [dish.id]: event.target.value }))}
                  type="number"
                  min="0"
                  step="any"
                  inputMode="numeric"
                  placeholder="—"
                  aria-label={t('{name} uchun hamkor narxi', { name: dish.name })}
                />
              </label>
            ))}
          </div>
          {!!priceWarnings.length && (
            <div className="alert">{priceWarnings.map(text => <p key={text}>{text}</p>)}</div>
          )}
          <p className="data-note">
            {t('Narx o‘zgarishi jo‘natilgan taomlarga tegmaydi — har bir jo‘natma o‘z narxini saqlab qoladi.')}
          </p>
          {formError && <p className="alert error">{formError}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('Narxlarni saqlash')}
          </button>
        </form>
      </AppModal>

      {owner && (
        <p className="data-note">
          <button className="text-link" onClick={() => navigate('/finance')}>
            {t('Hamkorlar moliyasi «Umumiy moliya» bo‘limida')} →
          </button>
        </p>
      )}
    </>
  )
}
