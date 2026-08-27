import { createRouter, createWebHistory } from 'vue-router'
import { useNetworkStore } from '@/stores/network'
import DashboardView from '@/views/DashboardView.vue'
import LoginView from '@/views/LoginView.vue'

const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: DashboardView,
    meta: { requiresAuth: true },
  },
  {
    path: '/login',
    name: 'login',
    component: LoginView,
  },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
})

router.beforeEach(async (to, from) => {
  const store = useNetworkStore()

  if (to.meta.requiresAuth) {
    if (!store.authenticated) {
      await store.checkAuth()
    }

    if (!store.authenticated) {
      return { name: 'login' }
    }
  }

  if (to.name === 'login' && store.authenticated) {
    return { name: 'dashboard' }
  }
})

export default router
