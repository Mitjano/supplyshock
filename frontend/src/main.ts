import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import 'primeicons/primeicons.css'
import './assets/main.css'
import './styles/responsive.css'
import App from './App.vue'
import { useAuthStore } from './stores/useAuthStore'
import en from './locales/en.json'
import pl from './locales/pl.json'

// Supported locales: 'pl' (default, no prefix), 'en' (/en prefix)
const SUPPORTED_LOCALES = ['pl', 'en'] as const
const DEFAULT_LOCALE = 'pl'

// Define page routes once, then generate with and without /en prefix
const pageRoutes: RouteRecordRaw[] = [
  { path: '', component: () => import('./views/HomeDashboard.vue') },
  { path: 'dashboard', component: () => import('./views/DashboardView.vue') },
  { path: 'login', component: () => import('./views/LoginView.vue') },
  { path: 'map', component: () => import('./views/MapView.vue') },
  { path: 'commodities', component: () => import('./views/CommodityDashboard.vue') },
  { path: 'bottlenecks', component: () => import('./views/BottleneckMonitor.vue') },
  { path: 'alerts', component: () => import('./views/AlertCenter.vue') },
  { path: 'alerts-legacy', component: () => import('./views/AlertsView.vue') },
  { path: 'simulations', component: () => import('./views/SimulationsView.vue') },
  { path: 'reports', component: () => import('./views/ReportsView.vue') },
  { path: 'settings', component: () => import('./views/SettingsView.vue') },
  { path: 'compliance', component: () => import('./views/ComplianceDashboard.vue') },
  { path: 'analytics', component: () => import('./views/AnalyticsDashboard.vue') },
  { path: 'fleet', component: () => import('./views/FleetAnalytics.vue') },
  { path: 'macro', component: () => import('./views/MacroDashboard.vue') },
  { path: 'emissions', component: () => import('./views/EmissionsDashboard.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // /en/* routes → English
    {
      path: '/en',
      children: pageRoutes.map(r => ({ ...r })),
    },
    // /* routes → Polish (default, no prefix)
    ...pageRoutes.map(r => ({
      ...r,
      path: r.path === '' ? '/' : `/${r.path}`,
    })),
  ],
})

const i18n = createI18n({
  legacy: false,
  locale: DEFAULT_LOCALE,
  fallbackLocale: DEFAULT_LOCALE,
  messages: { en, pl }
})

// Router guard: detect locale from URL prefix and set i18n locale
router.beforeEach((to) => {
  const locale = to.path.startsWith('/en') ? 'en' : 'pl'
  const i18nGlobal = i18n.global as unknown as { locale: { value: string } }
  if (i18nGlobal.locale.value !== locale) {
    i18nGlobal.locale.value = locale
  }
})

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)
app.use(i18n)
app.use(PrimeVue, {
  theme: {
    preset: Aura,
    options: {
      darkModeSelector: '.dark-mode',
      cssLayer: false
    }
  }
})

// Initialize Clerk auth
const auth = useAuthStore()
auth.initClerk()

app.mount('#app')
