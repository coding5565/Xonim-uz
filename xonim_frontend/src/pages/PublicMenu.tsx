import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowUpRight, Clock3, Leaf, MapPin, Search, Sparkles, UtensilsCrossed, X } from 'lucide-react'
import { api, money } from '../api'
import { useI18n } from '../i18n'
import type { Category, Dish } from '../types'
import DishArt from '../components/DishArt'
import DishSheet from '../components/DishSheet'
import MenuIntro from '../components/MenuIntro'
import './PublicMenu.css'

interface Menu {
  name: string
  categories: Category[]
  dishes: Dish[]
}

interface Section {
  id: number
  title: string
  dishes: Dish[]
  /** Bo'limgacha nechta taom bor — kartalar ketma-ket paydo bo'lishi uchun. */
  start: number
}

/** Filial ko'rsatilmasa shu manzil ochiladi. Bitta filialli o'rnatish uchun. */
const DEFAULT_BRANCH = 'xonim'

const INTRO_SEEN_KEY = 'xonim-menu-intro-seen'

/** Birinchi ekrandagi kartalar kirish animatsiyasi bilan chiqadi, qolganlari — surilganda. */
const FIRST_SCREEN_CARDS = 8

const SKELETON_CARDS = 6

/**
 * Kirish animatsiyasi har QR skanerlashda bir marta ochiladi (brauzer
 * yorlig'i yopilguncha). `?intro=1` uni majburan ochadi, `?intro=0` o'chiradi.
 * Harakatni kamaytirish yoqilgan qurilmalarda ochilmaydi.
 */
function shouldPlayIntro(): boolean {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false
  const forced = new URLSearchParams(window.location.search).get('intro')
  if (forced === '0') return false
  if (forced === '1') return true
  try {
    return !sessionStorage.getItem(INTRO_SEEN_KEY)
  } catch {
    // Maxfiy rejimda sessionStorage yopiq bo'lishi mumkin — animatsiya baribir ochiladi.
    return true
  }
}

/** Likopchalar uchun: avval har kategoriyadan bittadan, keyin qolganlari. */
function pickPlateImages(dishes: Dish[] | undefined): string[] {
  if (!dishes) return []
  // Bir xil rasm bir necha taomga qo'yilgan bo'lishi mumkin — likopchalar takrorlanmasin.
  const seen = new Set<string>()
  const shown = dishes.filter(dish => {
    if (!dish.image || !dish.available || seen.has(dish.image)) return false
    seen.add(dish.image)
    return true
  })
  const firstOfCategory = new Map<number, Dish>()
  for (const dish of shown) {
    if (!firstOfCategory.has(dish.category)) firstOfCategory.set(dish.category, dish)
  }
  const picked = [...firstOfCategory.values()]
  for (const dish of shown) {
    if (picked.length >= 6) break
    if (!picked.includes(dish)) picked.push(dish)
  }
  return picked.slice(0, 6).map(dish => dish.image as string)
}

/** Taomlarni bo'limlarga ajratadi; bo'limlar menyudagi tartibda turadi. */
function groupByCategory(dishes: Dish[], categories: Category[]): Section[] {
  const order = new Map(categories.map((item, index) => [item.id, index]))
  const groups = new Map<number, Dish[]>()
  for (const dish of dishes) groups.set(dish.category, [...(groups.get(dish.category) || []), dish])
  let start = 0
  return [...groups.entries()]
    .sort((a, b) => (order.get(a[0]) ?? 999) - (order.get(b[0]) ?? 999))
    .map(([id, list]) => {
      const section = { id, title: list[0].category_name, dishes: list, start }
      start += list.length
      return section
    })
}

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
  const [opened, setOpened] = useState<Dish | null>(null)
  const [introOn, setIntroOn] = useState(shouldPlayIntro)
  const [entering, setEntering] = useState(false)
  const enterTimer = useRef(0)
  const chips = useRef<HTMLDivElement>(null)
  const list = useRef<HTMLDivElement>(null)

  const plateImages = useMemo(() => pickPlateImages(data?.dishes), [data])
  // Parda ochila boshlaganda menyu ham qatma-qat paydo bo'ladi.
  const startEntering = useCallback(() => {
    setEntering(true)
    enterTimer.current = window.setTimeout(() => setEntering(false), 2600)
  }, [])
  const finishIntro = useCallback(() => setIntroOn(false), [])
  const closeDish = useCallback(() => setOpened(null), [])
  useEffect(() => () => window.clearTimeout(enterTimer.current), [])
  useEffect(() => {
    if (!introOn) return
    try { sessionStorage.setItem(INTRO_SEEN_KEY, '1') } catch { /* yopiq bo'lsa, har safar ochiladi */ }
  }, [introOn])

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

  const query = search.trim().toLocaleLowerCase()
  const visible = useMemo(() => data?.dishes.filter(dish =>
    (!category || dish.category === category) &&
    (!query || dish.name.toLocaleLowerCase().includes(query) || dish.description.toLocaleLowerCase().includes(query)),
  ) || [], [data, category, query])
  // «Barchasi» va qidiruvsiz — bo'limlarga bo'lib ko'rsatiladi; aks holda bitta ro'yxat.
  const sections = useMemo<Section[]>(() => {
    if (!data || !visible.length) return []
    if (!category && !query) return groupByCategory(visible, data.categories)
    const title = category ? data.categories.find(item => item.id === category)?.name || '' : t('Barcha taomlar')
    return [{ id: category, title, dishes: visible, start: 0 }]
  }, [data, visible, category, query, t])

  // Past qismdagi kartalar ekranga kirganda yumshoq paydo bo'ladi. `data-in`
  // atributi qo'lda qo'yiladi (class emas) — React qayta chizganda o'chirib yubormasin.
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return
    const cards = document.querySelectorAll<HTMLElement>('.mm-card[data-reveal]:not([data-in])')
    if (!cards.length) return
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue
        const card = entry.target as HTMLElement
        card.dataset.in = '1'
        observer.unobserve(card)
      }
    }, { rootMargin: '0px 0px -6% 0px' })
    cards.forEach(card => observer.observe(card))
    return () => observer.disconnect()
  }, [sections])

  // Tanlangan chip ko'rinib tursin (chiplar yonga suriladi).
  useEffect(() => {
    chips.current?.querySelector('.selected')?.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' })
  }, [category])

  const pickCategory = (id: number) => {
    setCategory(id)
    // Sahifa pastga surilgan bo'lsa, yangi ro'yxat boshiga qaytariladi.
    const top = list.current?.getBoundingClientRect().top ?? 0
    if (top < 70) list.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const canReveal = typeof IntersectionObserver !== 'undefined'

  return (
    <div className={`public-menu${entering ? ' is-entering' : ''}`}>
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
        <div className="mm-search">
          <Search size={18} />
          <input
            value={search}
            onChange={event => setSearch(event.target.value)}
            placeholder={t('Taom qidiring')}
            aria-label={t('Taom qidirish')}
            enterKeyHint="search"
            autoComplete="off"
          />
          {search && (
            <button type="button" className="mm-search-clear" onClick={() => setSearch('')} aria-label={t('Qidiruvni tozalash')}>
              <X size={16} />
            </button>
          )}
        </div>
        <nav className="mm-chips" aria-label={t('Taom kategoriyalari')}>
          <div className="mm-chips-row" ref={chips}>
            <button className={!category ? 'selected' : undefined} onClick={() => pickCategory(0)}>{t('Barchasi')}</button>
            {data?.categories.map(item => (
              <button
                key={item.id}
                className={category === item.id ? 'selected' : undefined}
                onClick={() => pickCategory(item.id)}
              >
                {item.name}
              </button>
            ))}
          </div>
        </nav>
        {error && (
          <p className="alert error">{error} <button className="text-link" onClick={load}>{t('Qayta urinish')}</button></p>
        )}
        <div className="mm-list" ref={list}>
          {!data && !error && (
            <div className="mm-grid" aria-label={t('Menyu tayyorlanmoqda…')} aria-busy="true">
              {Array.from({ length: SKELETON_CARDS }, (_, index) => (
                <div key={index} className="mm-card mm-skeleton" aria-hidden="true">
                  <span className="mm-media" />
                  <span className="mm-body"><i /><i /><i /></span>
                </div>
              ))}
            </div>
          )}
          {sections.map(section => (
            <section key={section.id} className="mm-section">
              <header className="mm-section-head">
                <h2>{section.title}</h2>
                <span>{tn('{count} ta tanlov', section.dishes.length)}</span>
              </header>
              <div className="mm-grid">
                {section.dishes.map((dish, index) => {
                  const position = section.start + index
                  const later = canReveal && position >= FIRST_SCREEN_CARDS
                  return (
                    <button
                      key={dish.id}
                      type="button"
                      className={`mm-card${dish.available ? '' : ' off'}`}
                      style={{ '--n': Math.min(position, FIRST_SCREEN_CARDS) } as CSSProperties}
                      data-reveal={later ? '' : undefined}
                      onClick={() => setOpened(dish)}
                    >
                      <span className="mm-media">
                        <DishArt name={dish.name} category={dish.category_name} image={dish.image} />
                        {!dish.available && <span className="dish-state unavailable">{t('Hozir mavjud emas')}</span>}
                      </span>
                      <span className="mm-body">
                        <span className="mm-name">{dish.name}</span>
                        {dish.description && <span className="mm-desc">{dish.description}</span>}
                        <span className="mm-foot">
                          <strong>{money(dish.price)} <small>{t('so‘m')}</small></strong>
                          {dish.portion && <span>{dish.portion}</span>}
                        </span>
                      </span>
                    </button>
                  )
                })}
              </div>
            </section>
          ))}
        </div>
        {data && !visible.length && (
          <div className="mm-empty">
            <Search size={26} strokeWidth={1.5} />
            <p>{t('Qidiruv bo‘yicha taom topilmadi.')}</p>
          </div>
        )}
      </main>
      <footer className="public-footer">
        <div className="footer-mark">x<span>•</span></div>
        <strong>xonim.</strong>
        <p><MapPin size={14} /> {t('Buyurtma berish uchun ofitsiantga murojaat qiling.')}</p>
        <Link to="/login">{t('Xodimlar uchun kirish')} <ArrowUpRight size={14} /></Link>
      </footer>
      {opened && <DishSheet dish={opened} onClose={closeDish} />}
      {introOn && <MenuIntro images={plateImages} onExit={startEntering} onDone={finishIntro} />}
    </div>
  )
}
