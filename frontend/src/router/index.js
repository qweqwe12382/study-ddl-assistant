import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('../views/DashboardView.vue'), meta: { title: '学习总览' } },
    { path: '/materials', name: 'materials', component: () => import('../views/MaterialsView.vue'), meta: { title: '资料库' } },
    { path: '/tasks', name: 'tasks', component: () => import('../views/TasksView.vue'), meta: { title: 'DDL 任务' } },
    { path: '/study-plans', name: 'study-plans', component: () => import('../views/StudyPlansView.vue'), meta: { title: '复习计划' } },
    { path: '/settings', name: 'settings', component: () => import('../views/SettingsView.vue'), meta: { title: '设置' } },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title || '学伴管家'} · 学伴管家`
})

export default router
