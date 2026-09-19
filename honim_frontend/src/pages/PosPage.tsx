import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom'
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

/** Yetkazib berish platformalari — kanal ham, to'lov turi ham shu nom bilan. */
const DELIVERY_METHODS = ['uzum', 'yandex']

/** Sotuv kanali marshrutdan aniqlanadi. */
const ROUTE_CHANNELS: Record<string, SaleChannel> = {
  '/pos/uzum': 'uzum',
  '/pos/yandex': 'yandex',
  '/pos/tezkor': 'takeaway',
}

/** Buyurtma yig'ish ekrani. Nima uchun ochilgani marshrutdan aniqlanadi:
 *  /pos/tezkor          - olib ketish
 *  /pos/uzum            - Uzum yetkazib berish
 *  /pos/yandex          - Yandex yetkazib berish
 *  /pos/stol/:tableId   - stolga yangi hisob (zal)
 *  /pos/hisob/:orderId  - ochiq hisobga qo'shish
 *  Shu sababli kassirda rejim yoki kanal tanlaydigan tugmalar yo'q: har biri
 *  o'z kirish joyidan ochiladi va noto'g'ri belgilab qo'yish imkoni yo'qoladi.
 */
export default function PosPage() {
  const { tableId, orderId } = useParams()
  const { pathname } = useLocation()
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
  // Stol bilan kelgan hisob — zal; qolgani marshrutda yozilgan.
  const channel: SaleChannel = tableId ? 'hall' : (ROUTE_CHANNELS[pathname] || 'takeaway')
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
  }, [cart, waiter, waiterId, channel, lockedRequest])

  useEffect(() => {
    // Uzum/Yandex buyurtmasining puli o'sha platforma orqali keladi, shuning
    // uchun to'lov turi kanal bilan birga tanlanadi.
    setPayment(previous => delivery
      ? channel
      : previous === 'uzum' || previous === 'yandex' ? 'cash' : previous)
    // Yetkazib berishda ofitsiant yo'q: tanlov ekrandan yo'qolgani uchun
    // uni holatda qoldirish «ko'rinmas ofitsiant»ga ulush yozib qo'yardi.
    if (delivery) {
      setWaiterId('')
      setWaiter('')
    }
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
  // Uzum va Yandex endi alohida kanal: ularga o'z kirish joyidan kiriladi va
  // to'lov turi avtomatik qo'yiladi. Zal va olib ketish savdosida ular
  // ro'yxatda turishi kassirni chalg'itardi.
  const methods = (user?.payment_methods || [])
    .filter(item => delivery ? item.method === channel : !DELIVERY_METHODS.includes(item.method))
  const paymentLabel = methods.find(item => item.method === payment)?.label || payment

  const stock = new Map((prep?.dishes || []).map(row => [row.dish, row]))
  // Miqdori kiritilmagan taom — tayyor emas. Oshxona talon kelgach
  // pishirmaydi, u faqat ertalab tayyorlanganidan yig'adi, demak kiritilmagan
  // degani «yo'q» degani. Qoldiq hali yuklanmagan bo'lsa cheklamaymiz —
  // aks holda sahifa ochilishi bilan hamma taom o'chiq ko'rinardi.
  const left = (id: number) => {
    if (!prep) return Infinity
    const row = stock.get(id)
    return row?.tracked ? row.remaining : 0
  }
  // Savatdagi miqdor hali sotilmagan, shuning uchun qoldiqdan alohida ayiriladi.
  const inCart = (id: number) => cart.find(line => line.dish.id === id)?.quantity || 0
  const oversold = cart
    .map(line => ({ name: line.dish.name, over: line.quantity - left(line.dish.id) }))
    .filter(item => item.over > 0)
  const pickedWaiter = waiters.find(item => String(item.id) === waiterId)
  const waiterFee = pickedWaiter ? (total * Number(pickedWaiter.commission)) / 100 : 0

  // Sarlavhada kanal ko'rinib tursin: kassir qaysi joydan sotayotganini
  // ekranga qarab bilishi kerak, yozib qo'yilgandan keyin emas.
  const CHANNEL_NAMES: Record<SaleChannel, string> = {
    hall: 'Zal', takeaway: 'Olib ketish', uzum: 'Uzum', yandex: 'Yandex',
  }
  const place = appending
    ? t('#{id} hisobiga qo‘shish', { id: bill?.id ?? orderId ?? '' })
    : table ? t('{table} · yangi hisob', { table: table.label }) : t(CHANNEL_NAMES[channel])

  function add(dish: Dish) {
    if (busy || locked || !dish.available) return
    // Tayyori qolmagan taom buyurtmaga tushmaydi: server ham qabul qilmaydi,
    // shuning uchun bu yerda to'xtatish kassirga xatoni oldindan ko'rsatadi.
    if (left(dish.id) - inCart(dish.id) <= 0) return
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
          waiter: delivery || waiterId ? '' : waiter,
          waiter_id: !delivery && waiterId ? Number(waiterId) : null,
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
      // Tarmoq noaniq tugasa xuddi shu so'rov saqlanib qoladi: qayta
      // bosilganda ikkinchi hisob ochilmasligi uchun. Lekin 400 — serverning
      // aniq javobi, ya'ni hisob umuman yozilmagan. Qulfni ochmasak, kassir
      // xatoni tuzatib qayta yubora olmay qolardi.
      setError((exception as Error).message)
      if ((exception as { status?: number }).status === 400) {
        setLockedRequest(undefined)
        setKey(crypto.randomUUID())
      }
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
          <h1>
            {t('Buyurtma')}<span className="heading-dot">.</span>
            {/* Platforma nishoni buyurtma yig'ilayotganda doim ko'rinib turadi:
                kassir qaysi kanalda ishlayotganini eslab qolishga majbur emas. */}
            {delivery && <span className={`channel-mark ${channel}`}>{channel}</span>}
          </h1>
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

      {delivery && (
        <p className="alert" role="status">
          {t('Yetkazib berish — puli kassaga tushmaydi, platforma hisobiga o‘tadi.')}
        </p>
      )}

      {/* Hech narsa tayyor deb belgilanmagan bo'lsa sotuv umuman bo'lmaydi —
          kassir nima qilishini darhol bilishi kerak. */}
      {!!prep && !prep.summary.tracked && (
        <p className="alert error" role="alert">
          <strong>{t('Bugun hech qanday taom tayyor deb belgilanmagan.')}</strong>{' '}
          {t('Oshxona nechta tayyorlaganini kiriting, shundan keyin sotuv boshlanadi.')}{' '}
          <Link to="/tayyor" className="text-link">{t('Tayyor taomlar')} →</Link>
        </p>
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
              // Hisoblanmagan taom «tayyor emas», tugagani esa «tugadi» —
              // ikkalasi ham sotilmaydi, lekin kassir farqini bilishi kerak:
              // biri kiritilmagan, ikkinchisi sotilib bitgan.
              const remaining = prep ? (row?.tracked ? row.remaining - inCart(dish.id) : 0) : null
              const ready = remaining === null || remaining > 0
              return (
              <button
                key={dish.id}
                className={`pos-dish${ready ? '' : ' not-ready'}`}
                disabled={!dish.available || busy || locked || !ready}
                onClick={() => add(dish)}
              >
                <DishArt name={dish.name} category={dish.category_name} image={dish.image} />
                {remaining !== null && (
                  <span className={`prep-badge${remaining <= 0 ? ' out' : remaining <= row!.warn_at ? ' low' : ''}`}>
                    {!row?.tracked
                      ? t('Tayyor emas')
                      : remaining <= 0 ? t('Tugadi') : tn('{count} ta qoldi', remaining)}
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
          {/* Yetkazib berishda tanlanadigan narsa yo'q: pul o'sha platformadan
              keladi, shuning uchun bitta tugmali ro'yxat ko'rsatilmaydi. */}
          {delivery ? (
            <p className="alert">
              {t('{method} hisobiga tushadi — kassaga naqd kelmaydi.', { method: paymentLabel })}
            </p>
          ) : (
            <>
              <p className="nav-caption">{t('TO‘LOV USULI')}</p>
              <div className="pay-grid">
                {methods.map(item => (
                  <button
                    key={item.method}
                    type="button"
                    className={payment === item.method ? 'selected' : undefined}
                    disabled={locked}
                    onClick={() => setPayment(item.method)}
                  >
                    {t(item.label)}
                  </button>
                ))}
              </div>
            </>
          )}
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
