import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import { ensureSession, session } from './api'
import '@fontsource/dm-sans/400.css'
import '@fontsource/dm-sans/500.css'
import '@fontsource/dm-sans/600.css'
import '@fontsource/dm-sans/700.css'
import '@fontsource/manrope/400.css'
import '@fontsource/manrope/600.css'
import '@fontsource/manrope/700.css'
import '@fontsource/manrope/800.css'
import './style.css'
const router = createRouter({history: createWebHistory(), routes: [
  { path: '/login', component: () => import('./pages/LoginPage.vue'), meta: {public: true} },
  { path: '/menu', component: () => import('./pages/PublicMenu.vue'), meta: {public: true} },
  { path: '/', component: () => import('./pages/DashboardPage.vue'), meta: {owner: true} },
  { path: '/catalog', component: () => import('./pages/CatalogPage.vue'), meta: {manager: true} },
  { path: '/pos', component: () => import('./pages/PosPage.vue') },
  { path: '/orders', component: () => import('./pages/OrdersPage.vue') },
  { path: '/reports', component: () => import('./pages/ReportsPage.vue'), meta: {manager: true} },
  { path: '/assistant', component: () => import('./pages/AssistantPage.vue'), meta: {owner: true} },
  { path: '/kitchen', component: () => import('./pages/KitchenPage.vue'), meta: {kitchen: true} },
  { path: '/expenses', component: () => import('./pages/ExpensesPage.vue'), meta: {manager: true} },
  { path: '/inventory', component: () => import('./pages/InventoryPage.vue'), meta: {manager: true} },
  { path: '/recipes', component: () => import('./pages/RecipesPage.vue'), meta: {manager: true} },
  { path: '/staff', component: () => import('./pages/StaffPage.vue'), meta: {owner: true} },
  { path: '/settings', component: () => import('./pages/SettingsPage.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]})
router.beforeEach(async to => {
  if (to.meta.public) return true
  try { await ensureSession() } catch { return '/login' }
  if (!session.user) return '/login'
  const role=session.user.role
  const fallback=role==='owner'?'/' : role==='kitchen'?'/kitchen':'/pos'
  if ((to.meta.owner && role!=='owner') || (to.meta.manager && !['owner','admin'].includes(role)) || (to.meta.kitchen && !['owner','admin','kitchen'].includes(role)) || (['/pos','/orders'].includes(to.path) && !['owner','admin','cashier'].includes(role)) || (to.path==='/settings' && role==='kitchen')) return fallback
})
createApp(App).use(router).mount('#app')
