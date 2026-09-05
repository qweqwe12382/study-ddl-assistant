<template>
  <a class="skip-link" href="#main-content" @click="focusMain">跳到主要内容</a>
  <div class="sr-only" aria-live="polite" aria-atomic="true">{{ viewModeAnnouncement }}</div>
  <el-container class="app-shell">
    <el-aside width="240px" class="app-sidebar">
      <div class="brand">
        <div>
          <div class="brand-kicker">STUDY SPACE / 学习空间</div>
          <div class="brand-title">学伴管家</div>
          <div class="brand-subtitle">课程资料与学习任务助手</div>
        </div>
      </div>

      <div class="ledger-spine" aria-label="学习安排工作闭环">
        <span>资料</span><i aria-hidden="true"></i><span>确认</span><i aria-hidden="true"></i><span>行动</span>
      </div>

      <el-menu :default-active="$route.path" router class="app-menu">
        <el-menu-item index="/app">
          <el-icon><House /></el-icon>
          <span class="nav-label">学习总览</span>
        </el-menu-item>
        <el-menu-item index="/materials">
          <el-icon><Collection /></el-icon>
          <span class="nav-label">资料库</span>
        </el-menu-item>
        <el-menu-item index="/tasks">
          <el-icon><List /></el-icon>
          <span class="nav-label">截止任务</span>
        </el-menu-item>
        <el-menu-item index="/focus">
          <el-icon><Timer /></el-icon>
          <span class="nav-label">专注计时</span>
        </el-menu-item>
        <el-menu-item index="/schedule">
          <el-icon><Clock /></el-icon>
          <span class="nav-label">课表与考试</span>
        </el-menu-item>
        <el-menu-item index="/study-plans">
          <el-icon><Calendar /></el-icon>
          <span class="nav-label">复习计划</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span class="nav-label">设置</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <span class="sidebar-footer-label">使用边界</span>
        <span>资料确认后才会创建正式任务；复习计划仍由用户生成。</span>
      </div>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div class="header-context">
          <div class="header-kicker">学习空间 / {{ routeContext }}</div>
          <div class="header-title">{{ $route.meta.title || '学习总览' }}</div>
        </div>
        <div class="mobile-brand" aria-label="学伴管家">
          <span class="mobile-brand-kicker">学</span>
          <span>学伴管家</span>
        </div>
        <div class="header-actions">
          <div class="view-mode-switch" role="group" aria-label="页面内容视图">
            <button
              type="button"
              :class="{ 'is-active': isConciseView }"
              :aria-pressed="isConciseView"
              @click="setViewMode('concise')"
            >
              专注视图
            </button>
            <button
              type="button"
              :class="{ 'is-active': isDetailedView }"
              :aria-pressed="isDetailedView"
              @click="setViewMode('detailed')"
            >
              完整视图
            </button>
          </div>
          <el-tag :type="connectionType" effect="plain" aria-live="polite">{{ connectionLabel }}</el-tag>
          <el-button
            link
            class="connection-retry"
            :loading="connectionState === 'checking'"
            :disabled="connectionState === 'checking'"
            aria-label="重新检查服务连接"
            @click="checkConnection"
          >
            <el-icon><Refresh /></el-icon>
            重试
          </el-button>
          <el-dropdown trigger="click" @command="handleAccountCommand">
            <button class="account-button" type="button" aria-label="打开账号菜单">
              <span class="account-avatar" aria-hidden="true">{{ userInitial }}</span>
              <span class="account-copy">
                <strong>{{ authSession.user?.display_name }}</strong>
                <small>{{ authSession.user?.email }}</small>
              </span>
              <el-icon aria-hidden="true"><ArrowDown /></el-icon>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
            <el-dropdown-item command="settings">账号设置</el-dropdown-item>
                <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>

      <el-main id="main-content" class="app-main" tabindex="-1">
        <slot />
      </el-main>
    </el-container>
  </el-container>

  <nav ref="mobileNav" class="mobile-nav" aria-label="移动端主导航">
    <router-link to="/app">
      <el-icon aria-hidden="true"><House /></el-icon>
      <span>总览</span>
    </router-link>
    <router-link to="/materials">
      <el-icon aria-hidden="true"><Collection /></el-icon>
      <span>资料</span>
    </router-link>
    <router-link to="/tasks">
      <el-icon aria-hidden="true"><List /></el-icon>
      <span>任务</span>
    </router-link>
    <router-link to="/schedule">
      <el-icon aria-hidden="true"><Clock /></el-icon>
      <span>日程</span>
    </router-link>
    <router-link to="/study-plans">
      <el-icon aria-hidden="true"><Calendar /></el-icon>
      <span>计划</span>
    </router-link>
    <router-link to="/settings">
      <el-icon aria-hidden="true"><Setting /></el-icon>
      <span>设置</span>
    </router-link>
  </nav>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ArrowDown, Calendar, Clock, Collection, House, List, Refresh, Setting, Timer } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

import { healthApi } from '../api'
import { authSession, logout } from '../auth/session'
import { useViewMode } from '../composables/useViewMode'

const route = useRoute()
const router = useRouter()
const mobileNav = ref(null)
const { isConciseView, isDetailedView, setViewMode, viewModeAnnouncement } = useViewMode()
const connectionState = ref('checking')
const connectionLabel = computed(() => ({ checking: '正在检查连接', online: '服务已连接', offline: '服务未连接' })[connectionState.value])
const connectionType = computed(() => ({ checking: 'info', online: 'success', offline: 'danger' })[connectionState.value])
const userInitial = computed(() => authSession.user?.display_name?.trim()?.slice(0, 1)?.toUpperCase() || '学')
const routeContext = computed(() => ({
  '/app': '今日行动',
  '/materials': '资料处理',
  '/tasks': '截止任务',
  '/schedule': '课表与考试',
  '/study-plans': '复习计划',
  '/settings': '学习设置',
}[route.path] || '今日行动'))

async function checkConnection() {
  connectionState.value = 'checking'
  try {
    await healthApi.check()
    connectionState.value = 'online'
  } catch {
    connectionState.value = 'offline'
  }
}

async function handleAccountCommand(command) {
  if (command === 'settings') {
    await router.push('/settings')
    return
  }
  if (command === 'logout') {
    await logout()
    await router.replace('/')
  }
}

function focusMain() {
  document.getElementById('main-content')?.focus()
}

let mobileNavResizeObserver
let mobileNavResizeHandler

function syncMobileNavHeight() {
  const height = mobileNav.value?.getBoundingClientRect().height ?? 0
  document.documentElement.style.setProperty('--mobile-nav-height', `${Math.ceil(height)}px`)
}

watch(() => route.path, async () => {
  await nextTick()
  window.requestAnimationFrame(focusMain)
})

onMounted(() => {
  checkConnection()
  syncMobileNavHeight()
  if ('ResizeObserver' in window && mobileNav.value) {
    mobileNavResizeObserver = new ResizeObserver(syncMobileNavHeight)
    mobileNavResizeObserver.observe(mobileNav.value)
    return
  }
  mobileNavResizeHandler = syncMobileNavHeight
  window.addEventListener('resize', mobileNavResizeHandler)
})

onBeforeUnmount(() => {
  mobileNavResizeObserver?.disconnect()
  if (mobileNavResizeHandler) window.removeEventListener('resize', mobileNavResizeHandler)
  document.documentElement.style.removeProperty('--mobile-nav-height')
})
</script>

<style scoped>
.account-button { min-height: 44px; max-width: 230px; display: inline-flex; align-items: center; gap: 9px; padding: 5px 9px 5px 6px; border: 1px solid var(--ledger-border); border-radius: 13px; background: #fff; color: var(--ledger-ink); cursor: pointer; text-align: left; }
.account-button:hover { border-color: #b7c5e8; background: #f8faff; }
.account-button:focus-visible { outline: 3px solid rgba(49, 87, 230, 0.24); outline-offset: 2px; }
.account-avatar { width: 32px; height: 32px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 10px; background: #3157e6; color: #fff; font-weight: 800; }
.account-copy { min-width: 0; display: grid; line-height: 1.15; }
.account-copy strong, .account-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.account-copy strong { font-size: 13px; }
.account-copy small { margin-top: 3px; color: var(--ledger-muted); font-size: 11px; }
@media (max-width: 1180px) { .account-copy { display: none; } .account-button { max-width: none; } }
@media (max-width: 760px) { .account-button { display: none; } }
</style>
