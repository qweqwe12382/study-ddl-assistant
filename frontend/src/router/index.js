import { createRouter, createWebHistory } from 'vue-router'

import DashboardView from '../views/DashboardView.vue'
import MaterialsView from '../views/MaterialsView.vue'
import TasksView from '../views/TasksView.vue'
import StudyPlansView from '../views/StudyPlansView.vue'
import SettingsView from '../views/SettingsView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardView, meta: { title: '学习总览' } },
    { path: '/materials', name: 'materials', component: MaterialsView, meta: { title: '资料库' } },
    { path: '/tasks', name: 'tasks', component: TasksView, meta: { title: 'DDL 任务' } },
    { path: '/study-plans', name: 'study-plans', component: StudyPlansView, meta: { title: '复习计划' } },
    { path: '/settings', name: 'settings', component: SettingsView, meta: { title: '设置' } },
  ],
})

router.afterEach((to) => {
  document.title = `${to.meta.title || '学伴管家'} · 学伴管家`
})

export default router
