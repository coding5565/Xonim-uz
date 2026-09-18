import { StrictMode, Suspense, lazy, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Outlet, Route, Routes } from 'react-router-dom'
import App from './App'
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
const SettingsPage = lazy(() => import('./pages/SettingsPage'))

/** Resolves the session before any protected page renders. */
function RequireAuth() {
  const { user, ready } = useSession()
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    ensureSession().catch(() => setFailed(true))
  }, [])

  if (failed) return <Navigate to="/login" replace />
  if (!ready) return null
  if (!user) return <Navigate to="/login" replace />
  return <Outlet />
}

function Allow({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { user } = useSession()
  if (!user) return null
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />
  return <>{children}</>
}

const managers: Role[] = ['owner', 'admin']
const sales: Role[] = ['owner', 'admin', 'cashier']
const kitchen: Role[] = ['owner', 'admin', 'kitchen']
const staffed: Role[] = ['owner', 'admin', 'cashier']

createRoot(document.getElementById('app')!).render(
  <StrictMode>
    <BrowserRouter>
      <Suspense fallback={null}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/menu" element={<PublicMenu />} />
          <Route element={<RequireAuth />}>
            <Route element={<App />}>
              <Route path="/" element={<Allow roles={['owner']}><DashboardPage /></Allow>} />
              <Route path="/catalog" element={<Allow roles={managers}><CatalogPage /></Allow>} />
              <Route path="/sales" element={<Allow roles={sales}><SalesPage /></Allow>} />
              <Route path="/pos" element={<Allow roles={sales}><TablesPage /></Allow>} />
              <Route path="/pos/tezkor" element={<Allow roles={sales}><PosPage /></Allow>} />
              <Route path="/pos/stol/:tableId" element={<Allow roles={sales}><PosPage /></Allow>} />
              <Route path="/pos/hisob/:orderId" element={<Allow roles={sales}><PosPage /></Allow>} />
              <Route path="/tables" element={<Allow roles={managers}><TablesAdminPage /></Allow>} />
              <Route path="/orders" element={<Allow roles={sales}><OrdersPage /></Allow>} />
              <Route path="/reports" element={<Allow roles={managers}><ReportsPage /></Allow>} />
              <Route path="/assistant" element={<Allow roles={['owner']}><AssistantPage /></Allow>} />
              <Route path="/kitchen" element={<Allow roles={kitchen}><KitchenPage /></Allow>} />
              <Route path="/expenses" element={<Allow roles={managers}><ExpensesPage /></Allow>} />
              <Route path="/inventory" element={<Allow roles={managers}><InventoryPage /></Allow>} />
              <Route path="/recipes" element={<Allow roles={managers}><RecipesPage /></Allow>} />
              <Route path="/staff" element={<Allow roles={['owner']}><StaffPage /></Allow>} />
              <Route path="/activity" element={<Allow roles={['owner']}><ActivityPage /></Allow>} />
              <Route path="/payroll" element={<Allow roles={['owner']}><PayrollPage /></Allow>} />
              <Route path="/finance" element={<Allow roles={['owner']}><FinancePage /></Allow>} />
              <Route path="/settings" element={<Allow roles={staffed}><SettingsPage /></Allow>} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  </StrictMode>,
)
