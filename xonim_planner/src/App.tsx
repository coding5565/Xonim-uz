import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  ArrowLeft,
  Building2,
  ChefHat,
  FlaskConical,
  Gauge,
  GitCompareArrows,
  LayoutDashboard,
  Menu as MenuIcon,
  Moon,
  Percent,
  ReceiptText,
  Settings as SettingsIcon,
  ShoppingBasket,
  Sun,
  Target,
  TrendingUp,
  Trophy,
  Users,
  X,
} from 'lucide-react'
import { Segmented, Select } from './components/ui'
import { cx } from './components/cx'
import { PERIODS } from './core/period'
import type { Period } from './core/types'
import type { TKey } from './i18n'
import { PERIOD_LABEL_KEY } from './i18n/keys'
import { LOCALES, LOCALE_SHORT, LOCALE_TAGS, type Locale } from './i18n/locales'
import { useActiveScenario, useAppStore } from './store/useAppStore'
import { useScenarioLabel, useT } from './store/useT'
import DashboardPage from './pages/DashboardPage'
import SalesPage from './pages/SalesPage'
import MenuPage from './pages/MenuPage'
import IngredientsPage from './pages/IngredientsPage'
import StaffPage from './pages/StaffPage'
import FixedExpensesPage from './pages/FixedExpensesPage'
import VariableExpensesPage from './pages/VariableExpensesPage'
import PnLPage from './pages/PnLPage'
import BreakEvenPage from './pages/BreakEvenPage'
import TargetPage from './pages/TargetPage'
import SimulatorPage from './pages/SimulatorPage'
import ScenariosPage from './pages/ScenariosPage'
import SettingsPage from './pages/SettingsPage'
import { XONIM, XONIM_HOME } from './xonim/config'
import { XonimBanner } from './xonim/XonimBanner'

type NavGroup = 'overview' | 'model' | 'analysis' | 'settings'

interface NavItem {
  id: string
  labelKey: TKey
  icon: ReactNode
  group: NavGroup
  render: () => ReactNode
}

const NAV: NavItem[] = [
  { id: 'dashboard', labelKey: 'nav.dashboard', group: 'overview', icon: <LayoutDashboard size={18} />, render: () => <DashboardPage /> },
  { id: 'pnl', labelKey: 'nav.pnl', group: 'overview', icon: <ReceiptText size={18} />, render: () => <PnLPage /> },
  { id: 'sales', labelKey: 'nav.sales', group: 'model', icon: <TrendingUp size={18} />, render: () => <SalesPage /> },
  { id: 'menu', labelKey: 'nav.menu', group: 'model', icon: <ChefHat size={18} />, render: () => <MenuPage /> },
  { id: 'ingredients', labelKey: 'nav.ingredients', group: 'model', icon: <ShoppingBasket size={18} />, render: () => <IngredientsPage /> },
  { id: 'staff', labelKey: 'nav.staff', group: 'model', icon: <Users size={18} />, render: () => <StaffPage /> },
  { id: 'fixed', labelKey: 'nav.fixed', group: 'model', icon: <Building2 size={18} />, render: () => <FixedExpensesPage /> },
  { id: 'variable', labelKey: 'nav.variable', group: 'model', icon: <Percent size={18} />, render: () => <VariableExpensesPage /> },
  { id: 'breakeven', labelKey: 'nav.breakeven', group: 'analysis', icon: <Target size={18} />, render: () => <BreakEvenPage /> },
  { id: 'target', labelKey: 'nav.target', group: 'analysis', icon: <Trophy size={18} />, render: () => <TargetPage /> },
  { id: 'simulator', labelKey: 'nav.simulator', group: 'analysis', icon: <FlaskConical size={18} />, render: () => <SimulatorPage /> },
  { id: 'scenarios', labelKey: 'nav.scenarios', group: 'analysis', icon: <GitCompareArrows size={18} />, render: () => <ScenariosPage /> },
  { id: 'settings', labelKey: 'nav.settings', group: 'settings', icon: <SettingsIcon size={18} />, render: () => <SettingsPage /> },
]

const GROUPS: Array<{ id: NavGroup; labelKey: TKey }> = [
  { id: 'overview', labelKey: 'nav.group.overview' },
  { id: 'model', labelKey: 'nav.group.model' },
  { id: 'analysis', labelKey: 'nav.group.analysis' },
  { id: 'settings', labelKey: 'nav.group.settings' },
]

function useHashRoute(): [string, (id: string) => void] {
  const [page, setPage] = useState(() => window.location.hash.replace('#', '') || 'dashboard')
  useEffect(() => {
    const onHash = () => setPage(window.location.hash.replace('#', '') || 'dashboard')
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])
  const go = (id: string) => {
    window.location.hash = id
    setPage(id)
  }
  return [page, go]
}

export default function App() {
  const [page, go] = useHashRoute()
  const [navOpen, setNavOpen] = useState(false)
  const t = useT()
  const theme = useAppStore((s) => s.theme)
  const toggleTheme = useAppStore((s) => s.toggleTheme)
  const locale = useAppStore((s) => s.locale)
  const setLocale = useAppStore((s) => s.setLocale)
  const businessName = useAppStore((s) => s.model.business.name)
  const period = useAppStore((s) => s.period)
  const setPeriod = useAppStore((s) => s.setPeriod)
  const scenarios = useAppStore((s) => s.scenarios)
  const setActiveScenario = useAppStore((s) => s.setActiveScenario)
  const active = useActiveScenario()
  const scenarioLabel = useScenarioLabel()

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
  }, [theme])

  // Язык страницы важен для скринридеров и переносов слов.
  useEffect(() => {
    document.documentElement.lang = LOCALE_TAGS[locale]
  }, [locale])

  const current = useMemo(() => NAV.find((n) => n.id === page) ?? NAV[0], [page])

  return (
    <div className="min-h-screen lg:flex">
      {/* Боковое меню */}
      <aside
        className={cx(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-slate-200 bg-white transition-transform dark:border-slate-800 dark:bg-slate-900 lg:translate-x-0',
          navOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center justify-between gap-2 border-b border-slate-200 px-4 py-4 dark:border-slate-800">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="rounded-lg bg-brand-600 p-1.5 text-white">
              <Gauge size={18} />
            </div>
            <div className="min-w-0 leading-tight">
              <div className="truncate text-sm font-semibold">{t('app.brand')}</div>
              <div className="truncate text-xs text-slate-500 dark:text-slate-400">
                {businessName || t('app.cafe')}
              </div>
            </div>
          </div>
          <button
            className="btn btn-ghost px-2 py-1 lg:hidden"
            onClick={() => setNavOpen(false)}
            aria-label={t('app.menuClose')}
          >
            <X size={16} />
          </button>
        </div>

        {XONIM && (
          <a
            href={XONIM_HOME}
            className="flex items-center gap-2 border-b border-slate-200 px-5 py-2.5 text-sm text-slate-600 transition hover:bg-slate-50 hover:text-slate-900 dark:border-slate-800 dark:text-slate-300 dark:hover:bg-slate-800/60 dark:hover:text-slate-50"
          >
            <ArrowLeft size={16} />
            {t('xonim.back')}
          </a>
        )}

        <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-4">
          {GROUPS.map((group) => (
            <div key={group.id}>
              <div className="mb-1 px-2 text-[10px] font-semibold tracking-wider text-slate-400 uppercase">
                {t(group.labelKey)}
              </div>
              <div className="space-y-0.5">
                {NAV.filter((n) => n.group === group.id).map((item) => (
                  <button
                    key={item.id}
                    onClick={() => {
                      go(item.id)
                      setNavOpen(false)
                    }}
                    className={cx(
                      'flex w-full cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition',
                      item.id === current.id
                        ? 'bg-brand-50 font-medium text-brand-700 dark:bg-brand-900/30 dark:text-brand-300'
                        : 'text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800',
                    )}
                  >
                    {item.icon}
                    <span className="truncate">{t(item.labelKey)}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-slate-200 px-4 py-3 text-[11px] text-slate-400 dark:border-slate-800">
          {XONIM ? t('xonim.dataSource') : t('app.dataLocal')}
        </div>
      </aside>

      {navOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden"
          onClick={() => setNavOpen(false)}
        />
      )}

      {/* Контент */}
      <div className="flex min-w-0 flex-1 flex-col lg:ml-64">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/85 backdrop-blur dark:border-slate-800 dark:bg-slate-900/85">
          <div className="flex flex-wrap items-center gap-3 px-4 py-3 sm:px-6">
            <button
              className="btn btn-ghost px-2 py-1.5 lg:hidden"
              onClick={() => setNavOpen(true)}
              aria-label={t('app.menuOpen')}
            >
              <MenuIcon size={18} />
            </button>
            <h1 className="mr-auto truncate text-base font-semibold sm:text-lg">
              {t(current.labelKey)}
            </h1>

            <div className="flex items-center gap-2">
              <span className="hidden text-xs text-slate-500 sm:inline dark:text-slate-400">
                {t('app.periodLabel')}
              </span>
              <Segmented<Period>
                size="sm"
                value={period}
                onChange={setPeriod}
                options={PERIODS.map((p) => ({ value: p, label: t(PERIOD_LABEL_KEY[p]) }))}
              />
            </div>

            <div className="w-44">
              <Select
                value={active.id}
                onChange={setActiveScenario}
                options={scenarios.map((s) => ({ value: s.id, label: scenarioLabel(s) }))}
              />
            </div>

            <Segmented<Locale>
              size="sm"
              value={locale}
              onChange={setLocale}
              options={LOCALES.map((l) => ({ value: l, label: LOCALE_SHORT[l] }))}
              className="shrink-0"
            />

            <button
              className="btn btn-ghost px-2 py-1.5"
              onClick={toggleTheme}
              aria-label={t('app.theme')}
            >
              {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
            </button>
          </div>
          {active.kind !== 'current' && (
            <div className="border-t border-amber-200 bg-amber-50 px-4 py-1.5 text-xs text-amber-800 sm:px-6 dark:border-amber-900/50 dark:bg-amber-950/40 dark:text-amber-200">
              {t('app.scenarioActive', { name: scenarioLabel(active) })}{' '}
              <button
                className="cursor-pointer font-semibold underline"
                onClick={() => setActiveScenario('sc_current')}
              >
                {t('app.backToCurrent')}
              </button>
            </div>
          )}
          {XONIM && <XonimBanner />}
        </header>

        <main className="flex-1 px-4 py-5 sm:px-6 sm:py-6">{current.render()}</main>
      </div>
    </div>
  )
}
