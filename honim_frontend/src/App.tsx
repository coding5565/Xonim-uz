import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  ArrowUpRight, BarChart3, Banknote, Bot, ChefHat, ChevronRight, Command, History, LayoutDashboard, LogOut, Menu, PiggyBank,
  LayoutGrid, Moon, Package, PanelLeftClose, ReceiptText, Settings2, ShoppingBag, Store, Sun, Users, UtensilsCrossed, Wallet,
} from 'lucide-react'
import { api } from './api'
import { SHOW_KITCHEN_SCREEN } from './config'
import { session, useSession } from './session'
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
  { path: '/sales', name: 'Sotuv', icon: Store, roles: ['owner', 'admin', 'cashier'] },
  { path: '/pos', name: 'Kassa', icon: ShoppingBag, roles: ['owner', 'admin', 'cashier'], badge: 'POS' },
  { path: '/orders', name: 'Buyurtmalar', icon: ReceiptText, roles: ['owner', 'admin', 'cashier'] },
  { path: '/reports', name: 'Savdo hisobotlari', icon: BarChart3, roles: ['owner', 'admin'] },
  { path: '/assistant', name: 'AI yordamchi', icon: Bot, roles: ['owner'] },
  { path: '/kitchen', name: 'Oshxona', icon: ChefHat, roles: ['owner', 'admin', 'kitchen'], badge: 'KDS' },
  { path: '/tables', name: 'Stollar', icon: LayoutGrid, roles: ['owner', 'admin'] },
  { path: '/catalog', name: 'Menyu boshqaruvi', icon: UtensilsCrossed, roles: ['owner', 'admin'] },
  { path: '/expenses', name: 'Xarajatlar', icon: Wallet, roles: ['owner', 'admin'] },
  { path: '/inventory', name: 'Ombor va sarf', icon: Package, roles: ['owner', 'admin'] },
  { path: '/recipes', name: 'Retsept va foyda', icon: BarChart3, roles: ['owner', 'admin'] },
  { path: '/staff', name: 'Xodimlar', icon: Users, roles: ['owner'] },
  { path: '/payroll', name: 'Oyliklar', icon: Banknote, roles: ['owner'] },
  { path: '/activity', name: 'Harakatlar', icon: History, roles: ['owner'] },
]

function roleName(role: Role | undefined) {
  if (role === 'owner') return 'Superadmin'
  if (role === 'admin') return 'Admin'
  if (role === 'kitchen') return 'Oshxona'
  return 'Kassir'
}

export default function App() {
  const { user } = useSession()
  const location = useLocation()
  const navigate = useNavigate()
  const [collapsed, setCollapsed] = useState(false)
  const [error, setError] = useState('')
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('honim-theme') === 'dark')

  useEffect(() => {
    document.documentElement.classList.toggle('theme-dark', darkMode)
    localStorage.setItem('honim-theme', darkMode ? 'dark' : 'light')
  }, [darkMode])

  const nav = navItems.filter(item =>
    user && item.roles.includes(user.role) && (SHOW_KITCHEN_SCREEN || item.path !== '/kitchen'))
  // Kassa ichki marshrutlari (/pos/stol/4) ham "Kassa" bandiga tegishli.
  const isCurrent = (path: string) =>
    location.pathname === path || (path !== '/' && location.pathname.startsWith(`${path}/`))
  const title = nav.find(item => isCurrent(item.path))?.name || 'Sozlamalar'

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
      {collapsed && <button className="sidebar-backdrop" aria-label="Menyuni yopish" onClick={closeMobileNav} />}
      <aside className="sidebar">
        <Link to="/" className="brand">
          <span className="brand-mark">h<span>•</span></span>
          <span className="brand-text">honim<span>RESTAURANT WORKSPACE</span></span>
        </Link>
        <div className="workspace">
          <span className="workspace-avatar">H</span>
          <div><strong>Honim Restaurant</strong><small>Asosiy restoran</small></div>
          <ChevronRight size={14} />
        </div>
        <p className="nav-caption">ISH MAYDONI</p>
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
                <span>{item.name}</span>
                {item.badge && <span className="nav-badge">{item.badge}</span>}
              </Link>
            )
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="menu-promo">
            <span className="promo-icon"><UtensilsCrossed size={20} /></span>
            <strong>Mehmonlar uchun menyu</strong>
            <p>Taomlaringiz bir skan masofada.</p>
            <Link to="/menu" target="_blank" onClick={closeMobileNav}>Menyuni ochish <ArrowUpRight size={16} /></Link>
          </div>
          {user?.role !== 'kitchen' && (
            <Link to="/settings" className="settings-link" onClick={closeMobileNav}>
              <Settings2 size={19} />Sozlamalar va QR
            </Link>
          )}
          <button className="profile" onClick={logout} title="Tizimdan chiqish">
            <span className="avatar">{user?.name.charAt(0)}</span>
            <span><strong>{user?.name}</strong><small>{roleName(user?.role)}</small></span>
            <LogOut size={17} />
          </button>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button className="icon-button" aria-label="Menyuni ochish/yopish" onClick={() => setCollapsed(value => !value)}>
              {collapsed ? <Menu size={19} /> : <PanelLeftClose size={19} />}
            </button>
            <span className="breadcrumb-home">Ish maydoni</span>
            <ChevronRight size={14} />
            <strong>{title}</strong>
          </div>
          <div className="topbar-right">
            <span className="local-badge"><span />Localhost · Sinov versiyasi</span>
            <span className="top-date">
              {new Intl.DateTimeFormat('uz-UZ', { day: 'numeric', month: 'long' }).format(new Date())}
            </span>
            <button
              className="theme-toggle"
              aria-label={darkMode ? 'Yorug‘ rejimga o‘tish' : 'Tungi rejimga o‘tish'}
              title={darkMode ? 'Yorug‘ rejim' : 'Tungi rejim'}
              onClick={() => setDarkMode(value => !value)}
            >
              {darkMode ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <span className="top-avatar"><Command size={18} /></span>
          </div>
        </header>
        {error && <p className="alert error">{error}</p>}
        <main className="main-content"><Outlet /></main>
        <footer className="app-footer">
          HONIM WORKSPACE <span>Mahalliy sinov • ma’lumotlar ushbu kompyuterda saqlanadi</span>
        </footer>
      </div>
    </div>
  )
}
