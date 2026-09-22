import { StrictMode, Suspense, lazy, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import App from './App'
import { I18nProvider } from './i18n'
import { ensureSession, homeFor, useSession, type Role } from './session'
import '@fontsource/dm-sans/400.css'
import '@fontsource/dm-sans/500.css'
import '@fontsource/dm-sans/600.css'
import '@fontsource/dm-sans/700.css'
import '@fontsource/manrope/400.css'
import '@fontsource/manrope/600.css'
import '@fontsource/manrope/700.css'
import '@fontsource/manrope/800.css'
import './style.css'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const PublicMenu = lazy(() => import('./pages/PublicMenu'))
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const CatalogPage = lazy(() => import('./pages/CatalogPage'))
const SalesPage = lazy(() => import('./pages/SalesPage'))
const PosPage = lazy(() => import('./pages/PosPage'))
const TablesPage = lazy(() => import('./pages/TablesPage'))
const TablesAdminPage = lazy(() => import('./pages/TablesAdminPage'))
const OrdersPage = lazy(() => import('./pages/OrdersPage'))
const ReportsPage = lazy(() => import('./pages/ReportsPage'))
const AssistantPage = lazy(() => import('./pages/AssistantPage'))
const KitchenPage = lazy(() => import('./pages/KitchenPage'))
const ExpensesPage = lazy(() => import('./pages/ExpensesPage'))
const InventoryPage = lazy(() => import('./pages/InventoryPage'))
const RecipesPage = lazy(() => import('./pages/RecipesPage'))
const StaffPage = lazy(() => import('./pages/StaffPage'))
const ActivityPage = lazy(() => import('./pages/ActivityPage'))
const PayrollPage = lazy(() => import('./pages/PayrollPage'))
const FinancePage = lazy(() => import('./pages/FinancePage'))
const WaitersPage = lazy(() => import('./pages/WaitersPage'))
const PrepPage = lazy(() => import('./pages/PrepPage'))
const PartnersPage = lazy(() => import('./pages/PartnersPage'))
const PartnerPage = lazy(() => import('./pages/PartnerPage'))
const BonusesPage = lazy(() => import('./pages/BonusesPage'))
const StaffMealsPage = lazy(() => import('./pages/StaffMealsPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))

/** Resolves the session before any protected page renders. */
/** Sahifa yuklanguncha ko'rinadigan belgi. Oq ekran «osilib qoldi»ga o'xshaydi. */
function Loading() {
  return (
    <div className="route-loading" role="status" aria-live="polite">
      <span className="route-spinner" />
    </div>
  )
}

function RequireAuth() {
  const { user, ready } = useSession()
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    ensureSession().catch(() => setFailed(true))
  }, [])

  if (failed) return <Navigate to="/login" replace />
  if (!ready) return <Loading />
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}

function Allow({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { user } = useSession()
  if (!user) return null
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />
  return <>{children}</>
}

const owners: Role[] = ['owner']
const sales: Role[] = ['owner', 'cashier']
const kitchen: Role[] = ['owner', 'kitchen']
// Sozlamalar hamma rolga ochiq: parolni almashtirish shu yerda.
const staffed: Role[] = ['owner', 'cashier', 'kitchen']

createRoot(document.getElementById('app')!).render(
  <StrictMode>
    <I18nProvider>
      <BrowserRouter>
      <Suspense fallback={<Loading />}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/menu" element={<PublicMenu />} />
          {/* Har bir filialning o'z manzili bor: /menu/<slug>. */}
          <Route path="/menu/:slug" element={<PublicMenu />} />
          <Route element={<RequireAuth />}>
            <Route element={<App />}>
              <Route path="/" element={<Allow roles={['owner']}><DashboardPage /></Allow>} />
              <Route path="/catalog" element={<Allow roles={owners}><CatalogPage /></Allow>} />
              <Route path="/sales" element={<Allow roles={sales}><SalesPage /></Allow>} />
              <Route path="/pos" element={<Allow roles={sales}><TablesPage /></Allow>} />
              <Route path="/pos/tezkor" element={<Allow roles={sales}><PosPage /></Allow>} />
              {/* Uzum va Yandex savdosi alohida kiriladi — kanal marshrutdan
                  aniqlanadi, ya'ni kassir uni tanlashni unuta olmaydi. */}
              <Route path="/pos/uzum" element={<Allow roles={sales}><PosPage /></Allow>} />
              <Route path="/pos/yandex" element={<Allow roles={sales}><PosPage /></Allow>} />
              <Route path="/pos/stol/:tableId" element={<Allow roles={sales}><PosPage /></Allow>} />
              <Route path="/pos/hisob/:orderId" element={<Allow roles={sales}><PosPage /></Allow>} />
              <Route path="/tables" element={<Allow roles={sales}><TablesAdminPage /></Allow>} />
              <Route path="/orders" element={<Allow roles={sales}><OrdersPage /></Allow>} />
              <Route path="/reports" element={<Allow roles={owners}><ReportsPage /></Allow>} />
              <Route path="/assistant" element={<Allow roles={['owner']}><AssistantPage /></Allow>} />
              <Route path="/kitchen" element={<Allow roles={kitchen}><KitchenPage /></Allow>} />
              <Route path="/expenses" element={<Allow roles={sales}><ExpensesPage /></Allow>} />
              <Route path="/inventory" element={<Allow roles={sales}><InventoryPage /></Allow>} />
              <Route path="/recipes" element={<Allow roles={owners}><RecipesPage /></Allow>} />
              <Route path="/staff" element={<Allow roles={['owner']}><StaffPage /></Allow>} />
              <Route path="/activity" element={<Allow roles={['owner']}><ActivityPage /></Allow>} />
              {/* Davomat va ish haqi kassirga ham ochiq: davomatni u belgilaydi
                  va pulni ko'pincha u beradi. */}
              <Route path="/payroll" element={<Allow roles={sales}><PayrollPage /></Allow>} />
              <Route path="/finance" element={<Allow roles={['owner']}><FinancePage /></Allow>} />
              <Route path="/waiters" element={<Allow roles={['owner']}><WaitersPage /></Allow>} />
              <Route path="/tayyor" element={<Allow roles={sales}><PrepPage /></Allow>} />
              {/* Hamkorlar: ro'yxat va har birining o'z sahifasi — jo'natish,
                  hisobot va pul o'sha yerda individual qilinadi. */}
              <Route path="/hamkorlar" element={<Allow roles={sales}><PartnersPage /></Allow>} />
              <Route path="/hamkorlar/:partnerId" element={<Allow roles={sales}><PartnerPage /></Allow>} />
              {/* Bonuslar va hodimlar ovqati — ikkalasida ham ovqat chiqadi,
                  pul kelmaydi. Kassir ham ko'radi: yozuvni u kiritadi. */}
              <Route path="/bonuslar" element={<Allow roles={sales}><BonusesPage /></Allow>} />
              <Route path="/hodimlar-ovqati" element={<Allow roles={sales}><StaffMealsPage /></Allow>} />
              <Route path="/settings" element={<Allow roles={staffed}><SettingsPage /></Allow>} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
      </BrowserRouter>
    </I18nProvider>
  </StrictMode>,
)
