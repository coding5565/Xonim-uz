import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  ArrowUpRight, BarChart3, Banknote, Bot, ChefHat, ChevronRight, Command, ConciergeBell, CookingPot, History, LayoutDashboard, LogOut, Menu, PiggyBank,
  LayoutGrid, Moon, Package, PanelLeftClose, ReceiptText, Settings2, ShoppingBag, Store, Sun, Users, UtensilsCrossed, Wallet,
} from 'lucide-react'
import { api } from './api'
import { SHOW_KITCHEN_SCREEN } from './config'
import { session, useSession } from './session'
import { LANGUAGES, useI18n, type Lang } from './i18n'
import type { User } from './types'

type Role = User['role']

interface NavItem {
  path: string
  name: string
  icon: typeof Menu
  roles: Role[]
  badge?: string
}

const navItems: NavItem[] = [
  { path: '/', name: 'Umumiy holat', icon: LayoutDashboard, roles: ['owner'] },
  { path: '/finance', name: 'Umumiy moliya', icon: PiggyBank, roles: ['owner'] },
  { path: '/sales', name: 'Sotuv', icon: Store, roles: ['owner', 'cashier'] },
  { path: '/pos', name: 'Kassa', icon: ShoppingBag, roles: ['owner', 'cashier'], badge: 'POS' },
  { path: '/orders', name: 'Buyurtmalar', icon: ReceiptText, roles: ['owner', 'cashier'] },
  { path: '/tayyor', name: 'Tayyor taomlar', icon: CookingPot, roles: ['owner', 'cashier'] },
  { path: '/reports', name: 'Savdo hisobotlari', icon: BarChart3, roles: ['owner'] },
  { path: '/assistant', name: 'AI yordamchi', icon: Bot, roles: ['owner'] },
  { path: '/kitchen', name: 'Oshxona', icon: ChefHat, roles: ['owner', 'kitchen'], badge: 'KDS' },
  { path: '/tables', name: 'Stollar', icon: LayoutGrid, roles: ['owner', 'cashier'] },
  { path: '/catalog', name: 'Menyu boshqaruvi', icon: UtensilsCrossed, roles: ['owner'] },
  { path: '/expenses', name: 'Xarajatlar', icon: Wallet, roles: ['owner', 'cashier'] },
  { path: '/inventory', name: 'Ombor va sarf', icon: Package, roles: ['owner', 'cashier'] },
  { path: '/recipes', name: 'Retsept va foyda', icon: BarChart3, roles: ['owner'] },
  { path: '/staff', name: 'Xodimlar', icon: Users, roles: ['owner'] },
  { path: '/waiters', name: 'Ofitsiantlar', icon: ConciergeBell, roles: ['owner'] },
  // Kassir ham ochadi: davomatni u belgilaydi va pulni ko'pincha u beradi.
  { path: '/payroll', name: 'Ish haqi', icon: Banknote, roles: ['owner', 'cashier'] },
  { path: '/activity', name: 'Harakatlar', icon: History, roles: ['owner'] },
]

function roleName(role: Role | undefined) {
  if (role === 'owner') return 'Superadmin'
  if (role === 'kitchen') return 'Oshxona'
  return 'Kassir'
}

export default function App() {
  const { user } = useSession()
  const { t, lang, setLang, locale } = useI18n()
  const location = useLocation()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [error, setError] = useState('')
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('xonim-theme') === 'dark')

  useEffect(() => {
    document.documentElement.classList.toggle('theme-dark', darkMode)
    localStorage.setItem('xonim-theme', darkMode ? 'dark' : 'light')
  }, [darkMode])

  // Oshxona ekrani qog'oz talon foydasiga o'chirilgan, lekin oshxona rolida
  // boshqa sahifa yo'q: bayroqqa qarab uni ham yashirsak, yon menyu bo'm-bo'sh
  // qoladi va xodim qayerdaligini bilmaydi.
  const nav = navItems.filter(item =>
    user && item.roles.includes(user.role)
    && (SHOW_KITCHEN_SCREEN || item.path !== '/kitchen' || user.role === 'kitchen'))
  // Kassa ichki marshrutlari (/pos/stol/4) ham "Kassa" bandiga tegishli.
  const isCurrent = (path: string) =>
    location.pathname === path || (path !== '/' && location.pathname.startsWith(`${path}/`))
  const title = t(nav.find(item => isCurrent(item.path))?.name || 'Sozlamalar')

  function closeMobileNav() {
    if (window.matchMedia('(max-width: 950px)').matches) setCollapsed(false)
  }

  async function logout() {
    try {
      await api('auth/logout/', { method: 'POST' })
      session.set({ user: null, ready: false })
      navigate('/login')
    } catch (exception) {
      setError((exception as Error).message)
    }
  }

  return (
    <div className={`app-shell${collapsed ? ' collapsed' : ''}`}>
      {collapsed && <button className="sidebar-backdrop" aria-label={t('Menyuni yopish')} onClick={closeMobileNav} />}
      <aside className="sidebar">
        <Link to="/" className="brand">
          <span className="brand-mark">x<span>•</span></span>
          <span className="brand-text">xonim<span>RESTAURANT WORKSPACE</span></span>
        </Link>
        <div className="workspace">
          <span className="workspace-avatar">X</span>
          <div><strong>Xonim Restaurant</strong><small>{t('Asosiy restoran')}</small></div>
          <ChevronRight size={14} />
        </div>
        <p className="nav-caption">{t('ISH MAYDONI')}</p>
        <nav>
          {nav.map(item => {
            const Icon = item.icon
            return (
              <Link
                key={item.path}
                to={item.path}
                className={isCurrent(item.path) ? 'active' : undefined}
                onClick={closeMobileNav}
              >
                <Icon size={20} />
                <span>{t(item.name)}</span>
                {item.badge && <span className="nav-badge">{item.badge}</span>}
              </Link>
            )
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="menu-promo">
            <span className="promo-icon"><UtensilsCrossed size={20} /></span>
            <strong>{t('Mehmonlar uchun menyu')}</strong>
            <p>{t('Taomlaringiz bir skan masofada.')}</p>
            <Link to="/menu" target="_blank" onClick={closeMobileNav}>{t('Menyuni ochish')} <ArrowUpRight size={16} /></Link>
          </div>
          {user?.role !== 'kitchen' && (
            <Link to="/settings" className="settings-link" onClick={closeMobileNav}>
              <Settings2 size={19} />{t('Sozlamalar va QR')}
            </Link>
          )}
          <button className="profile" onClick={logout} title={t('Tizimdan chiqish')}>
            <span className="avatar">{user?.name.charAt(0)}</span>
            <span><strong>{user?.name}</strong><small>{t(roleName(user?.role))}</small></span>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button className="icon-button" aria-label={t('Menyuni ochish/yopish')} onClick={() => setCollapsed(value => !value)}>
              {collapsed ? <Menu size={19} /> : <PanelLeftClose size={19} />}
            </button>
            <span className="breadcrumb-home">{t('Ish maydoni')}</span>
            <ChevronRight size={14} />
            <strong>{title}</strong>
          </div>
          <div className="topbar-right">
            <span className="local-badge"><span />{t('Localhost · Sinov versiyasi')}</span>
            <span className="top-date">
              {new Intl.DateTimeFormat(locale, { day: 'numeric', month: 'long' }).format(new Date())}
            </span>
            <button
              className="theme-toggle"
              aria-label={t(darkMode ? 'Yorug‘ rejimga o‘tish' : 'Tungi rejimga o‘tish')}
              title={t(darkMode ? 'Yorug‘ rejim' : 'Tungi rejim')}
              onClick={() => setDarkMode(value => !value)}
            >
              {darkMode ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <div className="lang-switch" role="group" aria-label={t('Tilni tanlash')}>
              {LANGUAGES.map(item => (
                <button
                  key={item.code}
                  className={lang === item.code ? 'selected' : undefined}
                  title={item.label}
                  onClick={() => setLang(item.code as Lang)}
                >
                  {item.short}
                </button>
              ))}
            </div>
            <span className="top-avatar"><Command size={18} /></span>
          </div>
        </header>
        {error && <p className="alert error">{error}</p>}
        <main className="main-content"><Outlet /></main>
        <footer className="app-footer">
          XONIM WORKSPACE <span>{t('Mahalliy sinov • ma’lumotlar ushbu kompyuterda saqlanadi')}</span>
        </footer>
      </div>
    </div>
  )
}
