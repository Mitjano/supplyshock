import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import { createI18n } from 'vue-i18n'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import 'primeicons/primeicons.css'
import './assets/main.css'
import App from './App.vue'
import { useAuthStore } from './stores/useAuthStore'
import en from './locales/en.json'
import pl from './locales/pl.json'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: () => import('./views/DashboardView.vue'),
    },
    {
      path: '/login',
      component: () => import('./views/LoginView.vue'),
    },
    {
      path: '/map',
      component: () => import('./views/MapView.vue'),
    },
    {
      path: '/commodities',
      component: () => import('./views/CommodityDashboard.vue'),
    },
    {
      path: '/bottlenecks',
      component: () => import('./views/BottleneckMonitor.vue'),
    },
    {
      path: '/alerts',
      component: () => import('./views/AlertsView.vue'),
    },
    {
      path: '/simulations',
      component: () => import('./views/SimulationsView.vue'),
    },
    {
      path: '/reports',
      component: () => import('./views/ReportsView.vue'),
    },
    {
      path: '/settings',
      component: () => import('./views/SettingsView.vue'),
    },
  ],
})

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en, pl }
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
