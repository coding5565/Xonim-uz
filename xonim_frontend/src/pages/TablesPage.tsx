import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { BadgePercent, Ban, Plus, Printer, RefreshCw, ShoppingBag, Trash2, Users } from 'lucide-react'
import { api, list, money } from '../api'
import { useSession } from '../session'
import { useI18n } from '../i18n'
import { useLiveData } from '../live'
import type { Order, SaleChannel, SalesSummary, Table, TableZone } from '../types'
import AppModal from '../components/AppModal'

/** Zal chizmasi: kirganda chapda divanlar, o'ngda stulli stollar, tashqarida alohida. */
const ZONES: { key: TableZone; title: string }[] = [
  { key: 'hall_left', title: 'Chap tomon · divan' },
  { key: 'hall_right', title: 'O‘ng tomon · stulli' },
]

/** Yetkazib berish platformalari — kanal ham, to'lov turi ham shu nom bilan. */
const DELIVERY_METHODS = ['uzum', 'yandex']

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

/** Ochiq tasdiq oynasi. `undefined` — hech narsa so'ralmayapti. */
type Dialog =
  | { kind: 'remove-line'; lineId: number; name: string }
  | { kind: 'discount' }
  | { kind: 'cancel' }

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
          <span className="table-total">{money(open.payable)} {t('so‘m')}</span>
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
  // Bo'lib to'lash: hisobning bir qismi boshqa usul bilan kelishi mumkin.
  const [splitMethod, setSplitMethod] = useState('')
  const [splitAmount, setSplitAmount] = useState('')
  const [busy, setBusy] = useState(false)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  // Tasdiqlash va matn so'rash uchun brauzerning confirm()/prompt() oynalari
  // ishlatilardi. Planshetda ular ilovaning o'ziga o'xshamaydi, uslub
  // qo'llab bo'lmaydi va kiosk rejimida umuman o'chirib qo'yilishi mumkin —
  // shunda chegirma ham, bekor qilish ham ishlamay qolardi.
  const [dialog, setDialog] = useState<Dialog>()
  const [reasonText, setReasonText] = useState('')
  const [discountText, setDiscountText] = useState('')

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
  }, [load])

  // Boshqa kassir hisobni yopsa yoki stol bo'shasa, xarita o'zi yangilanadi —
  // shu jumladan boshqa oynadan qaytilgan zahoti.
  useLiveData(load, 10)

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
    const payable = Number(bill.payable)
    const second = Math.max(0, Number(splitAmount) || 0)
    // Hisobga teng yoki undan katta bo'lsa bu bo'linish emas — kassir
    // usulni almashtirgani ma'qul.
    if (second >= payable) {
      setError(t('Bu summa hisobdan kichik bo‘lishi kerak. Hammasi shu usul bilan bo‘lsa, uni asosiy qilib tanlang.'))
      return
    }
    const other = methods.find(item => item.method !== chosen
      && item.method === (splitMethod || (chosen === 'cash' ? 'card' : 'cash')))
      || methods.find(item => item.method !== chosen)
    setBusy(true)
    setMethod(chosen)
    setError('')
    try {
      await api(`orders/${bill.id}/pay/`, {
        method: 'POST',
        body: JSON.stringify({
          payment_method: chosen,
          // Bo'sh qoldirilsa server bo'linishni umuman ko'rmaydi.
          split_method: second > 0 && other ? other.method : '',
          split_amount: second > 0 && other ? String(second) : null,
        }),
      })
      setSelected(undefined)
      setBill(undefined)
      setSplitAmount('')
      setSplitMethod('')
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
      setDialog(undefined)
    }
  }

  /** Chegirma so'mda kiritiladi; foiz tanlansa summaga aylantiriladi. */
  async function applyDiscount() {
    if (!bill) return
    const gross = Number(bill.total) + Number(bill.discount)
    const typed = discountText.trim()
    const amount = typed.endsWith('%')
      ? Math.round(gross * Number(typed.slice(0, -1)) / 100)
      : Number(typed)
    if (!Number.isFinite(amount) || amount < 0) return setError(t('Chegirma noto‘g‘ri kiritildi.'))
    if (amount && !reasonText.trim()) return setError(t('Chegirma sababini yozing.'))
    setBusy(true)
    setError('')
    setNotice('')
    try {
      setBill(await api<Order>(`orders/${bill.id}/discount/`, {
        method: 'POST',
        body: JSON.stringify({ amount: String(amount), reason: reasonText.trim() }),
      }))
      setNotice(amount
        ? t('Chegirma qo‘llandi: {sum} so‘m.', { sum: money(amount) })
        : t('Chegirma olib tashlandi.'))
      setDialog(undefined)
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
    if (reasonText.trim().length < 3) return setError(t('Sababni yozing.'))
    setBusy(true)
    setError('')
    try {
      await api(`orders/${bill.id}/cancel/`, { method: 'POST', body: JSON.stringify({ reason: reasonText.trim() }) })
      setDialog(undefined)
      setSelected(undefined)
      setBill(undefined)
      await load()
    } catch (exception) {
      setError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  /** Oynani ochadi va maydonlarni tozalaydi. */
  function ask(next: Dialog) {
    setError('')
    setReasonText('')
    setDiscountText(next.kind === 'discount' && bill?.discount !== '0.00' ? (bill?.discount || '') : '')
    setDialog(next)
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
  const openTotal = tables.reduce((sum, item) => sum + Number(item.open_order?.payable || 0), 0)
  // Stol hisobi doim zal savdosi. Uzum va Yandex alohida kanal bo'lib, o'z
  // kirish joyidan kiritiladi va puli platforma hisobiga tushadi — zaldagi
  // mehmon ular bilan to'lay olmaydi, shuning uchun ro'yxatda turmaydi.
  const methods = (user?.payment_methods || [])
    .filter(item => !DELIVERY_METHODS.includes(item.method))

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
            {/* Xizmat haqi hisob ustiga qo'shiladi: mijoz to'laydigan summa
                undan katta bo'ladi, shuning uchun ikkalasi ham ko'rinadi. */}
            {Number(bill.service_charge) > 0 && (
              <div className="bill-discount">
                <span>{t('Taomlar')}</span>
                <b>{money(bill.total)}</b>
                <span>{t('Xizmat haqi')} · {bill.waiter}</span>
                <b>+{money(bill.service_charge)}</b>
              </div>
            )}
            <div className="cart-total">
              <span>{Number(bill.service_charge) > 0 ? t('Mijoz to‘laydi') : t('Jami')}</span>
              <strong>{money(bill.payable)} <small>{t('so‘m')}</small></strong>
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
                    onClick={() => ask({ kind: 'remove-line', lineId: line.id, name: line.name })}
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
            {/* Hisobning bir qismi boshqa usul bilan kelsa, kassir shu
                yerga faqat O'SHA qismni yozadi va so'ng asosiy usulni
                bosadi. Bo'sh qolsa — odatdagi bitta usulli to'lov. */}
            <div className="split-pay">
              <label>
                {t('Boshqa usuldan, so‘m')}
                <input
                  value={splitAmount}
                  onChange={event => setSplitAmount(event.target.value)}
                  type="number"
                  min="0"
                  max={bill.payable}
                  step="any"
                  inputMode="decimal"
                  placeholder="0"
                  disabled={busy}
                />
              </label>
              {methods.length > 1 && (
                <label>
                  {t('Usul')}
                  <select
                    value={splitMethod}
                    onChange={event => setSplitMethod(event.target.value)}
                    disabled={busy}
                  >
                    <option value="">{t('o‘zi tanlansin')}</option>
                    {methods.map(item => (
                      <option key={item.method} value={item.method}>{t(item.label)}</option>
                    ))}
                  </select>
                </label>
              )}
            </div>
            {Number(splitAmount) > 0 && (
              <p className="data-note">
                {t('Qolgani esa quyidagi tugmadan tanlangan usul bilan hisoblanadi.')}
              </p>
            )}
            <div className="pay-grid">
              {methods.map(item => (
                <button
                  key={item.method}
                  className={method === item.method ? 'selected' : undefined}
                  disabled={busy}
                  onClick={() => pay(item.method)}
                >
                  {t(item.label)}
                </button>
              ))}
            </div>

            {notice && <p className="alert success">{notice}</p>}
            {error && <p className="alert error">{error}</p>}
            <button className="button secondary full" disabled={busy} onClick={reprint}>
              <Printer size={17} />{t('Chekni chop etish')}
            </button>
            <button className="button secondary full" disabled={busy} onClick={() => ask({ kind: 'discount' })}>
              <BadgePercent size={17} />{Number(bill.discount) > 0 ? t('Chegirmani o‘zgartirish') : t('Chegirma berish')}
            </button>
            <button className="button danger full" disabled={busy} onClick={() => ask({ kind: 'cancel' })}>
              <Ban size={17} />{t('Hisobni bekor qilish')}
            </button>
          </>
        )}
      </AppModal>

      {/* Tasdiqlash oynalari. Ilgari bu uchtasi brauzerning confirm() va
          prompt() oynalari edi. */}
      <AppModal
        open={dialog?.kind === 'remove-line'}
        title={t('Taomni olib tashlash')}
        onClose={() => { if (!busy) setDialog(undefined) }}
      >
        {dialog?.kind === 'remove-line' && (
          <>
            <p className="data-note">
              {t('«{name}» hisobdan olib tashlansinmi?', { name: dialog.name })}
            </p>
            {error && <p className="alert error">{error}</p>}
            <button
              className="button danger full"
              disabled={busy}
              onClick={() => removeLine(dialog.lineId, dialog.name)}
            >
              <Trash2 size={17} />{t('Olib tashlash')}
            </button>
            <button className="button secondary full" disabled={busy} onClick={() => setDialog(undefined)}>
              {t('Bekor qilish')}
            </button>
          </>
        )}
      </AppModal>

      <AppModal
        open={dialog?.kind === 'discount'}
        title={t('Chegirma')}
        onClose={() => { if (!busy) setDialog(undefined) }}
      >
        {dialog?.kind === 'discount' && bill && (
          <form onSubmit={event => { event.preventDefault(); applyDiscount() }}>
            <p className="data-note">
              {t('Hisob summasi: {sum} so‘m. Olib tashlash uchun 0 yozing.', {
                sum: money(Number(bill.total) + Number(bill.discount)),
              })}
            </p>
            <label>
              {t('Chegirma summasi, so‘m (yoki «10%» ko‘rinishida)')}
              <input
                value={discountText}
                onChange={event => setDiscountText(event.target.value)}
                placeholder="0"
                autoFocus
              />
            </label>
            <label>
              {t('Chegirma sababi')}
              <input
                value={reasonText}
                onChange={event => setReasonText(event.target.value)}
                maxLength={120}
                placeholder={t('Masalan: doimiy mijoz')}
              />
            </label>
            {error && <p className="alert error">{error}</p>}
            <button className="button primary full" disabled={busy}>
              {busy ? t('Saqlanmoqda…') : t('Saqlash')}
            </button>
          </form>
        )}
      </AppModal>

      <AppModal
        open={dialog?.kind === 'cancel'}
        title={t('Hisobni bekor qilish')}
        onClose={() => { if (!busy) setDialog(undefined) }}
      >
        {dialog?.kind === 'cancel' && (
          <form onSubmit={event => { event.preventDefault(); cancelBill() }}>
            <p className="data-note">{t('Hisob tarixda qoladi, lekin tushumga kirmaydi.')}</p>
            <label>
              {t('Nima uchun bekor qilinyapti?')}
              <input
                value={reasonText}
                onChange={event => setReasonText(event.target.value)}
                maxLength={200}
                minLength={3}
                required
                autoFocus
              />
            </label>
            {error && <p className="alert error">{error}</p>}
            <button className="button danger full" disabled={busy}>
              <Ban size={17} />{busy ? t('Saqlanmoqda…') : t('Bekor qilish')}
            </button>
          </form>
        )}
      </AppModal>
    </>
  )
}
