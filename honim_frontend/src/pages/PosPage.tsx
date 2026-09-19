import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, CheckCircle2, Minus, Plus, Search, ShoppingBag, Trash2 } from 'lucide-react'
import { api, list, money } from '../api'
import { useSession } from '../session'
import { useI18n } from '../i18n'
import type { Category, Dish, Order, PrepStatus, SaleChannel, Table, Waiter } from '../types'
import DishArt from '../components/DishArt'
import AppModal from '../components/AppModal'

interface CartLine {
  dish: Dish
  quantity: number
  note: string
}

/** Sotuv kanallari. Zal stol bilan kelgan hisobga qo'yiladi, qolgani
 *  tezkor savdoda tanlanadi. Uzum va Yandex puli kassaga tushmaydi. */
const CHANNELS: { value: SaleChannel; name: string }[] = [
  { value: 'takeaway', name: 'Olib ketish' },
  { value: 'uzum', name: 'Uzum' },
  { value: 'yandex', name: 'Yandex' },
  { value: 'hall', name: 'Zal' },
]

/** Buyurtma yig'ish ekrani. Nima uchun ochilgani marshrutdan aniqlanadi:
 *  /pos/tezkor          - olib ketish yoki yetkazib berish (kanal tanlanadi)
 *  /pos/stol/:tableId   - stolga yangi hisob
 *  /pos/hisob/:orderId  - ochiq hisobga qo'shish
 *  Shu sababli kassirda rejim tanlaydigan tugmalar yo'q.
 */
export default function PosPage() {
  const { tableId, orderId } = useParams()
  const navigate = useNavigate()
  const { user } = useSession()
  const { t, tn } = useI18n()

  const [categories, setCategories] = useState<Category[]>([])
  const [dishes, setDishes] = useState<Dish[]>([])
  const [category, setCategory] = useState(0)
  const [search, setSearch] = useState('')
  const [waiter, setWaiter] = useState('')
  const [waiters, setWaiters] = useState<Waiter[]>([])
  const [waiterId, setWaiterId] = useState('')
  // Zal hisobi stoldan kelgani uchun kanal tanlanmaydi.
  const [pickedChannel, setPickedChannel] = useState<SaleChannel>('takeaway')
  // Bugun tayyorlangan porsiyalar: kartada qoldiq ko'rinib tursin.
  const [prep, setPrep] = useState<PrepStatus>()
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [payModal, setPayModal] = useState(false)
  const [payment, setPayment] = useState('cash')
  const [result, setResult] = useState<Order>()
  const [cashGiven, setCashGiven] = useState('')
  const [cart, setCart] = useState<CartLine[]>([])
  const [key, setKey] = useState(() => crypto.randomUUID())
  // Natijasi noma'lum qolgan so'rov shu yerda saqlanadi: qayta bosilganda
  // aynan o'zi yuboriladi, ikkinchi hisob ochilmaydi.
  const [lockedRequest, setLockedRequest] = useState<{ path: string; body: string }>()
  const [table, setTable] = useState<Table>()
  const [bill, setBill] = useState<Order>()
  const cartPanel = useRef<HTMLElement>(null)

  const appending = !!orderId
  // Zal hisobi stoldan kelgani uchun kanal so'ralmaydi; tezkor savdoda tanlanadi.
  const channel: SaleChannel = tableId ? 'hall' : pickedChannel
  const delivery = channel === 'uzum' || channel === 'yandex'

  useEffect(() => {
    async function loadMenu() {
      try {
        const [loadedCategories, loadedDishes, loadedWaiters, loadedPrep] = await Promise.all([
          list<Category>('categories/'),
          list<Dish>('dishes/'),
          list<Waiter>('waiters/'),
          api<PrepStatus>('dish-prep/'),
        ])
        setCategories(loadedCategories)
        setDishes(loadedDishes)
        setWaiters(loadedWaiters.filter(item => item.active))
        setPrep(loadedPrep)
      } catch (exception) {
        setError((exception as Error).message)
      }
    }
    loadMenu()
  }, [])

  useEffect(() => {
    async function loadContext() {
      try {
        if (tableId) setTable(await api<Table>(`tables/${tableId}/`))
        if (orderId) setBill(await api<Order>(`orders/${orderId}/`))
      } catch (exception) {
        setError((exception as Error).message)
      }
    }
    loadContext()
  }, [tableId, orderId])

  useEffect(() => {
    if (!lockedRequest) setKey(crypto.randomUUID())
  }, [cart, waiter, waiterId, pickedChannel, lockedRequest])

  useEffect(() => {
    // Uzum/Yandex buyurtmasining puli o'sha platforma orqali keladi, shuning
    // uchun to'lov turi kanal bilan birga tanlanadi.
    setPayment(previous => delivery
      ? channel
      : previous === 'uzum' || previous === 'yandex' ? 'cash' : previous)
  }, [channel, delivery])

  const total = cart.reduce((sum, line) => sum + Math.round(Number(line.dish.price) * 100) * line.quantity, 0) / 100
  const filtered = dishes.filter(dish =>
    !dish.archived &&
    (!category || dish.category === category) &&
    dish.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()),
  )
  const change = Math.max(0, Number(cashGiven) - total)
  const count = cart.reduce((sum, line) => sum + line.quantity, 0)
  const locked = !!lockedRequest
  const methods = user?.payment_methods || []
  const paymentLabel = methods.find(item => item.method === payment)?.label || payment

  const stock = new Map((prep?.dishes || []).map(row => [row.dish, row]))
  // Miqdori kiritilmagan taom cheklanmaydi — u haqda hech narsa da'vo qilmaymiz.
  const left = (id: number) => {
    const row = stock.get(id)
    return row?.tracked ? row.remaining : Infinity
  }
  // Savatdagi miqdor hali sotilmagan, shuning uchun qoldiqdan alohida ayiriladi.
  const inCart = (id: number) => cart.find(line => line.dish.id === id)?.quantity || 0
  const oversold = cart
    .map(line => ({ name: line.dish.name, over: line.quantity - left(line.dish.id) }))
    .filter(item => item.over > 0)
  const pickedWaiter = waiters.find(item => String(item.id) === waiterId)
  const waiterFee = pickedWaiter ? (total * Number(pickedWaiter.commission)) / 100 : 0

  const place = appending
    ? t('#{id} hisobiga qo‘shish', { id: bill?.id ?? orderId ?? '' })
    : table ? t('{table} · yangi hisob', { table: table.label }) : t('Tezkor savdo')

  function add(dish: Dish) {
    if (busy || locked || !dish.available) return
    // Qoldiq tugaganda ogohlantiriladi, lekin to'xtatilmaydi: oshxona
    // qo'shimcha pishirgan bo'lishi mumkin. Faqat nolni kesib o'tgan
    // paytda so'raladi — keyingi har bosishda takrorlanmaydi.
    if (left(dish.id) - inCart(dish.id) === 0
      && !confirm(t('«{name}» tizimda tugagan. Baribir qo‘shilsinmi?', { name: dish.name }))) return
    setCart(previous => previous.some(line => line.dish.id === dish.id)
      ? previous.map(line => line.dish.id === dish.id
        ? { ...line, quantity: Math.min(999, line.quantity + 1) }
        : line)
      : [...previous, { dish, quantity: 1, note: '' }])
    setResult(undefined)
  }

  function adjust(id: number, amount: number) {
    if (locked) return
    setCart(previous => previous
      .map(line => line.dish.id === id ? { ...line, quantity: line.quantity + amount } : line)
      .filter(line => line.quantity > 0))
  }

  function setNote(id: number, note: string) {
    setCart(previous => previous.map(line => line.dish.id === id ? { ...line, note } : line))
  }

  async function submit(method: string) {
    if (busy) return
    setBusy(true)
    setError('')
    const lines = cart.map(line => ({ dish: line.dish.id, quantity: line.quantity, note: line.note }))
    const request = lockedRequest ?? (appending
      ? { path: `orders/${orderId}/lines/`, body: JSON.stringify({ key, lines }) }
      : {
        path: 'orders/',
        body: JSON.stringify({
          key,
          table: '',
          table_id: tableId ? Number(tableId) : null,
          // Ro'yxatdan tanlangan bo'lsa ism serverda qo'yiladi; qo'lda
          // yozilgani esa ofitsiantlar ro'yxati bo'sh bo'lgandagina yuboriladi.
          waiter: waiterId ? '' : waiter,
          waiter_id: waiterId ? Number(waiterId) : null,
          channel,
          payment_method: method,
          lines,
        }),
      })
    if (!lockedRequest) setLockedRequest(request)
    try {
      const saved = await api<Order>(request.path, { method: 'POST', body: request.body })
      setLockedRequest(undefined)
      setCart([])
      setKey(crypto.randomUUID())
      setPayModal(false)
      setCashGiven('')
      setWaiterId('')
      // Qoldiq sotuvdan keyin kamayadi — keyingi buyurtmada yangisi ko'rinsin.
      api<PrepStatus>('dish-prep/').then(setPrep).catch(() => {})
      // Talon chiqmagan bo'lsa kassir buni ko'rishi shart, shuning uchun
      // xaritaga qaytmaymiz — ogohlantirish shu yerda qoladi.
      if ((tableId || appending) && !saved.print_problems?.length) {
        navigate('/pos')
        return
      }
      setResult(saved)
    } catch (exception) {
      // Tarmoq noaniq tugasa ham xuddi shu so'rov saqlanib qoladi.
      setError((exception as Error).message)
    } finally {
      setBusy(false)
    }
  }

  function unlock() {
    if (confirm(t('Avval Buyurtmalar sahifasida bu hisob saqlanmaganini tekshiring. Tekshirdingizmi?'))) {
      setLockedRequest(undefined)
      setKey(crypto.randomUUID())
      setError('')
    }
  }

  const blocked = !cart.length || busy

  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">{place.toUpperCase()}</span>
          <h1>{t('Buyurtma')}<span className="heading-dot">.</span></h1>
          <p>{t('Taomni tanlang. Hisobni tizim hisoblaydi.')}</p>
        </div>
        <button className="button secondary" onClick={() => navigate('/pos')}>
          <ArrowLeft size={16} />{t('Stollarga qaytish')}
        </button>
      </div>

      {error && <p className="alert error">{error}</p>}
      {result && (
        <div className="alert success">
          <CheckCircle2 size={20} />
          <span>
            {appending
              ? t('#{id} hisobga qo‘shildi · yangi summa {sum} so‘m.', { id: result.id, sum: money(result.total) })
              : t('#{id} buyurtma {state} · {sum} so‘m.', {
                id: result.id,
                state: result.status === 'paid' ? t('to‘landi') : t('ochiq hisobga yozildi'),
                sum: money(result.total),
              })}
          </span>
        </div>
      )}
      {!!result?.print_problems?.length && (
        <div className="alert error" role="alert">
          <strong>{t('Diqqat — talon chiqmadi!')}</strong>
          <span>
            {result.print_problems.join(' ')}{' '}
            {t('Oshxona buyurtmani ko‘rmagan bo‘lishi mumkin — printerni tekshiring va «Buyurtmalar» bo‘limidan talonni qayta chiqaring.')}
          </span>
        </div>
      )}

      {!tableId && !appending && (
        <div className="channel-switch" role="group" aria-label={t('Savdo kanali')}>
          {CHANNELS.map(item => (
            <button
              key={item.value}
              className={channel === item.value ? 'selected' : undefined}
              disabled={locked}
              onClick={() => setPickedChannel(item.value)}
            >
              {t(item.name)}
            </button>
          ))}
          <span className="muted">
            {delivery
              ? t('Yetkazib berish — puli kassaga tushmaydi, platforma hisobiga o‘tadi.')
              : t('Puli kassaga tushadi.')}
          </span>
        </div>
      )}

      <div className="pos-layout">
        <section>
          <div className="search-field wide">
            <Search size={19} />
            <input
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder={t('Taom nomini yozing…')}
              aria-label={t('Taom qidirish')}
            />
          </div>
          <div className="tabs pos-tabs">
            <button className={!category ? 'selected' : undefined} onClick={() => setCategory(0)}>{t('Barchasi')}</button>
            {categories.map(item => (
              <button
                key={item.id}
                className={category === item.id ? 'selected' : undefined}
                onClick={() => setCategory(item.id)}
              >
                {item.name}
              </button>
            ))}
          </div>
          <div className="pos-dishes">
            {filtered.map(dish => {
              const row = stock.get(dish.id)
              const remaining = row?.tracked ? row.remaining - inCart(dish.id) : null
              return (
              <button
                key={dish.id}
                className="pos-dish"
                disabled={!dish.available || busy || locked}
                onClick={() => add(dish)}
              >
                <DishArt name={dish.name} category={dish.category_name} image={dish.image} />
                {remaining !== null && (
                  <span className={`prep-badge${remaining <= 0 ? ' out' : remaining <= row!.warn_at ? ' low' : ''}`}>
                    {remaining <= 0 ? t('Tugadi') : tn('{count} ta qoldi', remaining)}
                  </span>
                )}
                <div>
                  <span>{dish.portion}</span>
                  <h3>{dish.name}</h3>
                  <footer>
                    <strong>{money(dish.price)} <small>{t('so‘m')}</small></strong>
                    <span className="add-circle"><Plus size={17} /></span>
                  </footer>
                  {!dish.available && <small>{t('Hozir mavjud emas')}</small>}
                </div>
              </button>
              )
            })}
          </div>
        </section>

        <aside ref={cartPanel} className="cart panel">
          <header className="cart-header">
            <div><ShoppingBag size={20} /><h2>{place}</h2></div>
            <span className="pill">{tn('{count} ta', count)}</span>
          </header>

          {bill && (
            <p className="change-line">
              {t('Hozirgi summa')} <strong>{money(bill.total)} {t('so‘m')}</strong> → {t('qo‘shilgach')}{' '}
              <strong>{money(Number(bill.total) + total)} {t('so‘m')}</strong>
            </p>
          )}

          {/* Yetkazib berishda ofitsiant yo'q — buyurtmani platforma oladi. */}
          {!appending && !delivery && (waiters.length ? (
            <label className="table-fields">
              {t('Ofitsiant')}
              <select value={waiterId} onChange={event => setWaiterId(event.target.value)} disabled={locked}>
                <option value="">{t('Belgilanmagan')}</option>
                {waiters.map(item => (
                  <option key={item.id} value={item.id}>{item.name} · {item.commission}%</option>
                ))}
              </select>
              {!!pickedWaiter && !!waiterFee && (
                <small className="muted">
                  {t('Ulushi: {fee} so‘m ({percent}%)', { fee: money(waiterFee), percent: pickedWaiter.commission })}
                </small>
              )}
            </label>
          ) : !!tableId && (
            <label className="table-fields">
              {t('Ofitsiant')}
              <input
                value={waiter}
                onChange={event => setWaiter(event.target.value)}
                disabled={locked}
                maxLength={100}
                placeholder={t('Ism (ixtiyoriy)')}
              />
            </label>
          ))}

          {!!oversold.length && (
            <p className="alert" role="status">
              {t('Tayyorlangan miqdordan ko‘p:')}{' '}
              {oversold.map(item => t('{name} +{count}', { name: item.name, count: item.over })).join(' · ')}
            </p>
          )}

          {!cart.length && (
            <div className="empty-cart">
              <ShoppingBag size={45} strokeWidth={1} />
              <h3>{t('Buyurtma hali bo‘sh')}</h3>
              <p>{t('Chap tomondan taomlarni tanlang.')}</p>
            </div>
          )}
          <div className="cart-lines">
            {cart.map(line => (
              <div key={line.dish.id} className="cart-line">
                <div className="cart-line-top">
                  <strong>{line.dish.name}</strong>
                  <button
                    className="icon-button"
                    disabled={locked}
                    aria-label={t('{name} olib tashlash', { name: line.dish.name })}
                    onClick={() => adjust(line.dish.id, -line.quantity)}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
                <div className="cart-line-bottom">
                  <div className="stepper">
                    <button disabled={busy || locked} onClick={() => adjust(line.dish.id, -1)} aria-label={t('Kamaytirish')}>
                      <Minus size={13} />
                    </button>
                    <span>{line.quantity}</span>
                    <button
                      disabled={busy || locked || line.quantity >= 999}
                      onClick={() => adjust(line.dish.id, 1)}
                      aria-label={t('Ko‘paytirish')}
                    >
                      <Plus size={13} />
                    </button>
                  </div>
                  <strong>{money(Number(line.dish.price) * line.quantity)}</strong>
                </div>
                <input
                  value={line.note}
                  onChange={event => setNote(line.dish.id, event.target.value)}
                  disabled={locked}
                  className="line-note"
                  maxLength={200}
                  placeholder={t('Oshxona uchun izoh…')}
                />
              </div>
            ))}
          </div>

          <footer className="cart-footer">
            <div className="cart-total"><span>{t('Jami')}</span><strong>{money(total)} <small>{t('so‘m')}</small></strong></div>
            {locked ? (
              <>
                <button className="button primary full" disabled={busy} onClick={() => submit(payment)}>
                  {t('Oldingi amalni qayta tekshirish')}
                </button>
                <button className="button secondary full" disabled={busy} onClick={unlock}>
                  {t('Hisobni tekshirdim, tahrirlash')}
                </button>
              </>
            ) : appending ? (
              <>
                <button className="button primary full" disabled={blocked} onClick={() => submit('')}>
                  {t('Hisobga qo‘shish')} <ArrowRight size={17} />
                </button>
                <small className="muted">
                  {t('Faqat yangi taomlar talon bo‘lib chiqadi, summa esa hisobga qo‘shiladi.')}
                </small>
              </>
            ) : (
              <>
                <button className="button primary full" disabled={blocked} onClick={() => submit('')}>
                  {tableId ? t('Stolga yuborish') : t('Buyurtmani yuborish')} <ArrowRight size={17} />
                </button>
                <small className="muted">
                  {t('Talonlar oshxona va kassa printerlaridan chiqadi. To‘lov oxirida qayd etiladi.')}
                </small>
                <button
                  className="button secondary full"
                  disabled={blocked}
                  onClick={() => { setPayModal(true); setCashGiven(String(total)) }}
                >
                  {t('Darhol to‘lov olish')}
                </button>
              </>
            )}
          </footer>
        </aside>
      </div>

      {!!cart.length && (
        <button
          className="mobile-cart-cta"
          onClick={() => cartPanel.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
        >
          <span><ShoppingBag size={17} /> {tn('{count} ta buyurtma', count)}</span>
          <strong>{money(total)} →</strong>
        </button>
      )}

      <AppModal open={payModal} title={t('To‘lovni qayd etish')} onClose={() => { if (!busy) setPayModal(false) }}>
        <div className="payment-amount">{money(total)} <small>{t('so‘m')}</small></div>
        <form onSubmit={(event: FormEvent) => { event.preventDefault(); submit(payment) }}>
          <p className="nav-caption">{t('TO‘LOV USULI')}</p>
          <div className="pay-grid">
            {methods.map(item => (
              <button
                key={item.method}
                type="button"
                className={payment === item.method ? 'selected' : undefined}
                // Uzum buyurtmasi naqd bo'lolmaydi: pul platformadan keladi.
                disabled={locked || (delivery && item.method !== channel)}
                onClick={() => setPayment(item.method)}
              >
                {t(item.label)}
              </button>
            ))}
          </div>
          {payment === 'cash' ? (
            <>
              <label>
                {t('Berilgan naqd')}
                <input
                  value={cashGiven}
                  onChange={event => setCashGiven(event.target.value)}
                  type="number"
                  min={total}
                  step="0.01"
                  required
                />
              </label>
              <div className="pay-grid">
                {[total, 50000, 100000, 200000].map((amount, index) => (
                  <button key={index} type="button" onClick={() => setCashGiven(String(amount))}>
                    {index === 0 ? t('Tayyor pul') : money(amount)}
                  </button>
                ))}
              </div>
              <p className="change-line">{t('Qaytim')} <strong>{money(change)} {t('so‘m')}</strong></p>
            </>
          ) : (
            <p className="alert">
              {t('Faqat {method} ilovasida/terminalida to‘lov muvaffaqiyatli o‘tganidan keyin qayd eting. To‘lov tizimi integratsiyasi hali ulanmagan — summa qo‘lda tasdiqlanadi.', { method: paymentLabel })}
            </p>
          )}
          {error && <p className="alert error">{error}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? t('Saqlanmoqda…') : t('To‘lovni tasdiqlash')}
          </button>
        </form>
      </AppModal>
    </>
  )
}
