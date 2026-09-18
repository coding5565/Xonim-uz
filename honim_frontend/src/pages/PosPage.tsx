import { useEffect, useRef, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, ArrowRight, CheckCircle2, Minus, Plus, Search, ShoppingBag, Trash2 } from 'lucide-react'
import { api, list, money } from '../api'
import { useSession } from '../session'
import type { Category, Dish, Order, Table } from '../types'
import DishArt from '../components/DishArt'
import AppModal from '../components/AppModal'

interface CartLine {
  dish: Dish
  quantity: number
  note: string
}

/** Buyurtma yig'ish ekrani. Nima uchun ochilgani marshrutdan aniqlanadi:
 *  /pos/tezkor          - olib ketish
 *  /pos/stol/:tableId   - stolga yangi hisob
 *  /pos/hisob/:orderId  - ochiq hisobga qo'shish
 *  Shu sababli kassirda rejim tanlaydigan tugmalar yo'q.
 */
export default function PosPage() {
  const { tableId, orderId } = useParams()
  const navigate = useNavigate()
  const { user } = useSession()

  const [categories, setCategories] = useState<Category[]>([])
  const [dishes, setDishes] = useState<Dish[]>([])
  const [category, setCategory] = useState(0)
  const [search, setSearch] = useState('')
  const [waiter, setWaiter] = useState('')
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

  useEffect(() => {
    async function loadMenu() {
      try {
        const [loadedCategories, loadedDishes] = await Promise.all([
          list<Category>('categories/'),
          list<Dish>('dishes/'),
        ])
        setCategories(loadedCategories)
        setDishes(loadedDishes)
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
  }, [cart, waiter, lockedRequest])

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

  const place = appending
    ? `#${bill?.id ?? orderId} hisobiga qo‘shish`
    : table ? `${table.label} · yangi hisob` : 'Tezkor savdo'

  function add(dish: Dish) {
    if (busy || locked || !dish.available) return
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
          waiter: tableId ? waiter : '',
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
    if (confirm('Avval Buyurtmalar sahifasida bu hisob saqlanmaganini tekshiring. Tekshirdingizmi?')) {
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
          <h1>Buyurtma<span className="heading-dot">.</span></h1>
          <p>Taomni tanlang. Hisobni tizim hisoblaydi.</p>
        </div>
        <button className="button secondary" onClick={() => navigate('/pos')}>
          <ArrowLeft size={16} />Stollarga qaytish
        </button>
      </div>

      {error && <p className="alert error">{error}</p>}
      {result && (
        <div className="alert success">
          <CheckCircle2 size={20} />
          <span>
            {appending
              ? `#${result.id} hisobga qo‘shildi · yangi summa ${money(result.total)} so‘m.`
              : `#${result.id} buyurtma ${result.status === 'paid' ? 'to‘landi' : 'ochiq hisobga yozildi'} · ${money(result.total)} so‘m.`}
          </span>
        </div>
      )}
      {!!result?.print_problems?.length && (
        <div className="alert error" role="alert">
          <strong>Diqqat — talon chiqmadi!</strong>
          <span>
            {result.print_problems.join(' ')} Oshxona buyurtmani ko‘rmagan bo‘lishi mumkin —
            printerni tekshiring va «Buyurtmalar» bo‘limidan talonni qayta chiqaring.
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
              placeholder="Taom nomini yozing…"
              aria-label="Taom qidirish"
            />
          </div>
          <div className="tabs pos-tabs">
            <button className={!category ? 'selected' : undefined} onClick={() => setCategory(0)}>Barchasi</button>
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
            {filtered.map(dish => (
              <button
                key={dish.id}
                className="pos-dish"
                disabled={!dish.available || busy || locked}
                onClick={() => add(dish)}
              >
                <DishArt name={dish.name} category={dish.category_name} image={dish.image} />
                <div>
                  <span>{dish.portion}</span>
                  <h3>{dish.name}</h3>
                  <footer>
                    <strong>{money(dish.price)} <small>so‘m</small></strong>
                    <span className="add-circle"><Plus size={17} /></span>
                  </footer>
                  {!dish.available && <small>Hozir mavjud emas</small>}
                </div>
              </button>
            ))}
          </div>
        </section>

        <aside ref={cartPanel} className="cart panel">
          <header className="cart-header">
            <div><ShoppingBag size={20} /><h2>{place}</h2></div>
            <span className="pill">{count} ta</span>
          </header>

          {bill && (
            <p className="change-line">
              Hozirgi summa <strong>{money(bill.total)} so‘m</strong> → qo‘shilgach{' '}
              <strong>{money(Number(bill.total) + total)} so‘m</strong>
            </p>
          )}

          {!!tableId && (
            <label className="table-fields">
              Ofitsiant
              <input
                value={waiter}
                onChange={event => setWaiter(event.target.value)}
                disabled={locked}
                maxLength={100}
                placeholder="Ism (ixtiyoriy)"
              />
            </label>
          )}

          {!cart.length && (
            <div className="empty-cart">
              <ShoppingBag size={45} strokeWidth={1} />
              <h3>Buyurtma hali bo‘sh</h3>
              <p>Chap tomondan taomlarni tanlang.</p>
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
                    aria-label={`${line.dish.name} olib tashlash`}
                    onClick={() => adjust(line.dish.id, -line.quantity)}
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
                <div className="cart-line-bottom">
                  <div className="stepper">
                    <button disabled={busy || locked} onClick={() => adjust(line.dish.id, -1)} aria-label="Kamaytirish">
                      <Minus size={13} />
                    </button>
                    <span>{line.quantity}</span>
                    <button
                      disabled={busy || locked || line.quantity >= 999}
                      onClick={() => adjust(line.dish.id, 1)}
                      aria-label="Ko‘paytirish"
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
                  placeholder="Oshxona uchun izoh…"
                />
              </div>
            ))}
          </div>

          <footer className="cart-footer">
            <div className="cart-total"><span>Jami</span><strong>{money(total)} <small>so‘m</small></strong></div>
            {locked ? (
              <>
                <button className="button primary full" disabled={busy} onClick={() => submit(payment)}>
                  Oldingi amalni qayta tekshirish
                </button>
                <button className="button secondary full" disabled={busy} onClick={unlock}>
                  Hisobni tekshirdim, tahrirlash
                </button>
              </>
            ) : appending ? (
              <>
                <button className="button primary full" disabled={blocked} onClick={() => submit('')}>
                  Hisobga qo‘shish <ArrowRight size={17} />
                </button>
                <small className="muted">
                  Faqat yangi taomlar talon bo‘lib chiqadi, summa esa hisobga qo‘shiladi.
                </small>
              </>
            ) : (
              <>
                <button className="button primary full" disabled={blocked} onClick={() => submit('')}>
                  {tableId ? 'Stolga yuborish' : 'Buyurtmani yuborish'} <ArrowRight size={17} />
                </button>
                <small className="muted">
                  Talonlar oshxona va kassa printerlaridan chiqadi. To‘lov oxirida qayd etiladi.
                </small>
                <button
                  className="button secondary full"
                  disabled={blocked}
                  onClick={() => { setPayModal(true); setCashGiven(String(total)) }}
                >
                  Darhol to‘lov olish
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
          <span><ShoppingBag size={17} /> {count} ta buyurtma</span>
          <strong>{money(total)} →</strong>
        </button>
      )}

      <AppModal open={payModal} title="To‘lovni qayd etish" onClose={() => { if (!busy) setPayModal(false) }}>
        <div className="payment-amount">{money(total)} <small>so‘m</small></div>
        <form onSubmit={(event: FormEvent) => { event.preventDefault(); submit(payment) }}>
          <p className="nav-caption">TO‘LOV USULI</p>
          <div className="pay-grid">
            {methods.map(item => (
              <button
                key={item.method}
                type="button"
                className={payment === item.method ? 'selected' : undefined}
                disabled={locked}
                onClick={() => setPayment(item.method)}
              >
                {item.label}
              </button>
            ))}
          </div>
          {payment === 'cash' ? (
            <>
              <label>
                Berilgan naqd
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
                    {index === 0 ? 'Tayyor pul' : money(amount)}
                  </button>
                ))}
              </div>
              <p className="change-line">Qaytim <strong>{money(change)} so‘m</strong></p>
            </>
          ) : (
            <p className="alert">
              Faqat {paymentLabel} ilovasida/terminalida to‘lov muvaffaqiyatli o‘tganidan keyin qayd eting.
              To‘lov tizimi integratsiyasi hali ulanmagan — summa qo‘lda tasdiqlanadi.
            </p>
          )}
          {error && <p className="alert error">{error}</p>}
          <button className="button primary full" disabled={busy}>
            {busy ? 'Saqlanmoqda…' : 'To‘lovni tasdiqlash'}
          </button>
        </form>
      </AppModal>
    </>
  )
}
