import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { getToken } from '@/api/http'

// 视图一律懒加载：既减小首屏体积，也避免 router -> view -> store -> api -> http -> router
// 形成模块求值期的循环依赖。
const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'home',
    component: () => import('@/views/HomeView.vue'),
    meta: { requiresAuth: true, title: '智能客服' },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '注册', mode: 'register' },
  },
  {
    path: '/ecommerce',
    name: 'ecommerce',
    component: () => import('@/views/EcommerceView.vue'),
    meta: { requiresAuth: true, title: '电商智能体' },
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory('/'),
  routes,
})

router.beforeEach((to) => {
  // 守卫只读 localStorage，不引入 store，保持依赖单向
  const token = getToken()
  if ((to.path === '/login' || to.path === '/register') && token) return '/'
  if (to.meta.requiresAuth && !token) return '/login'
  return true
})

router.afterEach((to) => {
  const title = (to.meta.title as string) || ''
  document.title = title ? `${title} · AssistGen` : 'AssistGen 智能客服'
})

export default router
