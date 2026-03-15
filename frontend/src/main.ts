import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import { useAuthStore } from './stores/useAuthStore'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: () => import('./views/LoginView.vue'),
    },
    {
      path: '/login',
      component: () => import('./views/LoginView.vue'),
    },
  ],
})

const app = createApp(App)
const pinia = createPinia()
app.use(pinia)
app.use(router)

// Initialize Clerk auth
const auth = useAuthStore()
auth.initClerk()

app.mount('#app')
