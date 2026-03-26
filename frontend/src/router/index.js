import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue')
  },
  {
    path: '/',
    component: () => import('@/components/Layout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘' }
      },
      {
        path: 'catalog',
        name: 'Catalog',
        component: () => import('@/views/Catalog.vue'),
        meta: { title: '影视目录' }
      },
      {
        path: 'tasks',
        name: 'Tasks',
        component: () => import('@/views/Tasks.vue'),
        meta: { title: '转存任务' }
      },
      {
        path: 'history',
        name: 'History',
        component: () => import('@/views/History.vue'),
        meta: { title: '同步历史' }
      },
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/Settings.vue'),
        meta: { title: '系统设置' }
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/Users.vue'),
        meta: { title: '用户管理', requiresAdmin: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫
router.beforeEach((to, from, next) => {
  // 从 localStorage 直接读取 token 判断是否登录
  const accessToken = localStorage.getItem('access_token')
  const isAuthenticated = !!accessToken

  // 设置页面标题
  if (to.meta.title) {
    document.title = `${to.meta.title} - Film Transfer`
  }

  // 检查是否需要登录
  if (to.path !== '/login') {
    if (!isAuthenticated) {
      next('/login')
      return
    }
  }

  next()
})

export default router
