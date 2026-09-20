import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowUpRight, Clock3, Leaf, MapPin, Search, Sparkles, UtensilsCrossed } from 'lucide-react'
import { api, money } from '../api'
import { useI18n } from '../i18n'
import type { Category, Dish } from '../types'
import DishArt from '../components/DishArt'

interface Menu {
  name: string
  categories: Category[]
  dishes: Dish[]
}

/** Filial ko'rsatilmasa shu manzil ochiladi. Bitta filialli o'rnatish uchun. */
const DEFAULT_BRANCH = 'xonim'

export default function PublicMenu() {
  const { t, tn } = useI18n()
  // Filial manzildan olinadi: /menu/<slug>. Ilgari u kodda «xonim» deb
  // yozib qo'yilgan edi va ikkinchi filial o'z menyusini umuman
  // ocholmasdi — server esa har qanday slug'ni qo'llab-quvvatlaydi.
  const { slug } = useParams()
  const branch = slug || DEFAULT_BRANCH
  const [data, setData] = useState<Menu>()
  const [category, setCategory] = useState(0)
  const [search, setSearch] = useState('')
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setError('')
    try {
      setData(await api<Menu>(`public/menu/${encodeURIComponent(branch)}/`))
    } catch (exception) {
      setError((exception as Error).message)
    }
  }, [branch])

  useEffect(() => {
    load()
  }, [load])

  const visible = data?.dishes.filter(dish =>
    (!category || dish.category === category) &&
    dish.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()),
  ) || []
  const activeCategory = data?.categories.find(item => item.id === category)?.name || t('Barcha taomlar')

  return (
    <div className="public-menu">
      <header className="public-header">
        <Link to={slug ? `/menu/${slug}` : '/menu'} className="brand">
          <span className="brand-mark">x<span>•</span></span>
          {/* Filial nomi serverdan keladi — ilgari u olinardi-yu, hech
              qayerda ko'rsatilmasdi. */}
          <span className="brand-text">{data?.name || 'xonim'}<span>{t('RESTORAN MENYUSI')}</span></span>
        </Link>
        <div className="public-header-meta">
          <span className="open-badge"><i /> {t('Bugun ochiq')}</span>
          <span className="public-language">{t('O‘zbekcha')}</span>
        </div>
      </header>
      <section className="menu-hero">
        <div className="hero-copy">
          <span className="eyebrow"><Sparkles size={13} /> {t('DID BILAN TAYYORLANGAN')}</span>
          <h1>{t('Ta’mlar')}<br /><em>{t('bir dasturxonda.')}</em></h1>
          <p>{t('Sevimli taomlaringizni tanlang.')}<br />{t('Buyurtmani ofitsiantga ayting.')}</p>
          <div className="hero-details">
            <span><UtensilsCrossed size={15} /> {tn('{count} ta taom', data?.dishes.length || 0)}</span>
            <span><Clock3 size={15} /> {t('Har kuni xizmatda')}</span>
          </div>
        </div>
        <div className="hero-ornament"><Leaf size={142} strokeWidth={0.8} /><span>XONIM<br />RESTAURANT</span></div>
      </section>
      <main className="public-content">
        <div className="menu-intro">
          <div><span className="eyebrow">{t('MENYU')}</span><h2>{activeCategory}</h2></div>
          <span className="menu-count">{tn('{count} ta tanlov', visible.length)}</span>
        </div>
        <div className="public-controls">
          <div className="tabs" aria-label={t('Taom kategoriyalari')}>
            <button className={!category ? 'selected' : undefined} onClick={() => setCategory(0)}>{t('Barchasi')}</button>
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
              placeholder={t('Taom qidiring')}
              aria-label={t('Taom qidirish')}
            />
          </div>
        </div>
        {error && (
          <p className="alert error">{error} <button className="text-link" onClick={load}>{t('Qayta urinish')}</button></p>
        )}
        {!data && !error && <div className="empty-state">{t('Menyu tayyorlanmoqda…')}</div>}
        <div className="dish-grid">
          {visible.map(dish => (
            <article key={dish.id} className="dish-card">
              <div className="dish-image-wrap">
                <DishArt name={dish.name} category={dish.category_name} image={dish.image} />
                {!dish.available && <span className="dish-state unavailable">{t('Hozir mavjud emas')}</span>}
              </div>
              <div className="dish-details">
                <span className="eyebrow">{dish.category_name}</span>
                <h3>{dish.name}</h3>
                {dish.description && <p>{dish.description}</p>}
                <footer>
                  <strong>{money(dish.price)} <small>{t('so‘m')}</small></strong>
                  <span>{dish.portion}</span>
                </footer>
              </div>
            </article>
          ))}
        </div>
        {data && !visible.length && <p className="empty-state">{t('Qidiruv bo‘yicha taom topilmadi.')}</p>}
      </main>
      <footer className="public-footer">
        <div className="footer-mark">x<span>•</span></div>
        <strong>xonim.</strong>
        <p><MapPin size={14} /> {t('Buyurtma berish uchun ofitsiantga murojaat qiling.')}</p>
        <Link to="/login">{t('Xodimlar uchun kirish')} <ArrowUpRight size={14} /></Link>
      </footer>
    </div>
  )
}
