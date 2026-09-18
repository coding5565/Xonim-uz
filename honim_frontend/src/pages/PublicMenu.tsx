import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, Clock3, Leaf, MapPin, Search, Sparkles, UtensilsCrossed } from 'lucide-react'
import { api, money } from '../api'
import type { Category, Dish } from '../types'
import DishArt from '../components/DishArt'

interface Menu {
  name: string
  categories: Category[]
  dishes: Dish[]
}

export default function PublicMenu() {
  const [data, setData] = useState<Menu>()
  const [category, setCategory] = useState(0)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      setData(await api<Menu>('public/menu/honim/'))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const visible = data?.dishes.filter(dish =>
    (!category || dish.category === category) &&
    dish.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()),
  ) || []
  const activeCategory = data?.categories.find(item => item.id === category)?.name || 'Barcha taomlar'

  return (
    <div className="public-menu">
      <header className="public-header">
        <Link to="/menu" className="brand">
          <span className="brand-mark">h<span>•</span></span>
          <span className="brand-text">honim<span>RESTORAN MENYUSI</span></span>
        </Link>
        <div className="public-header-meta">
          <span className="open-badge"><i /> Bugun ochiq</span>
          <span className="public-language">O‘zbekcha</span>
        </div>
      </header>
      <section className="menu-hero">
        <div className="hero-copy">
          <span className="eyebrow"><Sparkles size={13} /> DID BILAN TAYYORLANGAN</span>
          <h1>Ta’mlar<br /><em>bir dasturxonda.</em></h1>
          <p>Sevimli taomlaringizni tanlang.<br />Buyurtmani ofitsiantga ayting.</p>
          <div className="hero-details">
            <span><UtensilsCrossed size={15} /> {data?.dishes.length || 0} ta taom</span>
            <span><Clock3 size={15} /> Har kuni xizmatda</span>
          </div>
        </div>
        <div className="hero-ornament"><Leaf size={142} strokeWidth={0.8} /><span>HONIM<br />RESTAURANT</span></div>
      </section>
      <main className="public-content">
        <div className="menu-intro">
          <div><span className="eyebrow">MENYU</span><h2>{activeCategory}</h2></div>
          <span className="menu-count">{visible.length} ta tanlov</span>
        </div>
        <div className="public-controls">
          <div className="tabs" aria-label="Taom kategoriyalari">
            <button className={!category ? 'selected' : undefined} onClick={() => setCategory(0)}>Barchasi</button>
            {data?.categories.map(item => (
              <button
                key={item.id}
                className={category === item.id ? 'selected' : undefined}
                onClick={() => setCategory(item.id)}
              >
                {item.name}
              </button>
            ))}
          </div>
          <div className="search-field">
            <Search size={18} />
            <input
              value={search}
              onChange={event => setSearch(event.target.value)}
              placeholder="Taom qidiring"
              aria-label="Taom qidirish"
            />
          </div>
        </div>
        {error && (
          <p className="alert error">{error} <button className="text-link" onClick={load}>Qayta urinish</button></p>
        )}
        {!data && !error && <div className="empty-state">Menyu tayyorlanmoqda…</div>}
        <div className="dish-grid">
          {visible.map(dish => (
            <article key={dish.id} className="dish-card">
              <div className="dish-image-wrap">
                <DishArt name={dish.name} category={dish.category_name} image={dish.image} />
                {!dish.available && <span className="dish-state unavailable">Hozir mavjud emas</span>}
              </div>
              <div className="dish-details">
                <span className="eyebrow">{dish.category_name}</span>
                <h3>{dish.name}</h3>
                {dish.description && <p>{dish.description}</p>}
                <footer>
                  <strong>{money(dish.price)} <small>so‘m</small></strong>
                  <span>{dish.portion}</span>
                </footer>
              </div>
            </article>
          ))}
        </div>
        {data && !visible.length && <p className="empty-state">Qidiruv bo‘yicha taom topilmadi.</p>}
      </main>
      <footer className="public-footer">
        <div className="footer-mark">h<span>•</span></div>
        <strong>honim.</strong>
        <p><MapPin size={14} /> Buyurtma berish uchun ofitsiantga murojaat qiling.</p>
        <Link to="/login">Xodimlar uchun kirish <ArrowUpRight size={14} /></Link>
      </footer>
    </div>
  )
}
