import { createRouter, createWebHistory } from 'vue-router'

import { authSession, restoreSession } from '../auth/session'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, top: 16 }
    if (to.path !== from.path) return { top: 0 }
  },
  routes: [
    {
      path: '/',
      name: 'home',
      component: () => import('../views/LandingView.vue'),
      meta: { title: '把课程资料变成下一步', publicLayout: true },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/AuthView.vue'),
      props: { mode: 'login' },
      meta: { title: '登录', publicLayout: true, guestOnly: true },
    },
    {
      path: '/register',
      name: 'register',
      component: () => import('../views/AuthView.vue'),
      props: { mode: 'register' },
      meta: { title: '注册', publicLayout: true, guestOnly: true },
    },
    { path: '/app', name: 'dashboard', component: () => import('../views/DashboardView.vue'), meta: { title: '学习总览' } },
    { path: '/materials', name: 'materials', component: () => import('../views/MaterialsView.vue'), meta: { title: '资料库' } },
    { path: '/tasks', name: 'tasks', component: () => import('../views/TasksView.vue'), meta: { title: '截止任务' } },
    { path: '/deadline-radar', name: 'deadline-radar', component: () => import('../views/DeadlineRadarView.vue'), meta: { title: 'DDL 应变台' } },
    { path: '/focus', name: 'focus', component: () => import('../views/FocusView.vue'), meta: { title: '专注计时' } },
    { path: '/schedule', name: 'schedule', component: () => import('../views/AcademicCalendarView.vue'), meta: { title: '课表与考试' } },
    { path: '/study-plans', name: 'study-plans', component: () => import('../views/StudyPlansView.vue'), meta: { title: '复习计划' } },
    { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue'), meta: { title: '设置' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  try {
    await restoreSession()
  } catch {
    if (!to.meta.publicLayout) return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (!to.meta.publicLayout && !authSession.user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && authSession.user) return { name: 'dashboard' }
  return true
})

router.afterEach((to) => {
  document.title = `${to.meta.title || '学伴管家'} · 学伴管家`
})

export default router
