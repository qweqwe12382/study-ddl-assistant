<template>
  <a class="skip-link" href="#main-content" @click="focusMain">跳到主要内容</a>
  <div class="sr-only" aria-live="polite" aria-atomic="true">{{ viewModeAnnouncement }}</div>
  <el-container class="app-shell">
    <el-aside width="220px" class="app-sidebar">
      <router-link to="/app" class="brand" aria-label="学伴管家，返回学习总览">
        <BrandMark />
        <div>
          <div class="brand-title">学伴管家</div>
          <div class="brand-subtitle">把学习安排好</div>
        </div>
      </router-link>

      <button type="button" class="workspace-search" aria-haspopup="dialog" :aria-expanded="commandMenuOpen" aria-keyshortcuts="Control+k Meta+k" @click="openCommandMenu">
        <el-icon aria-hidden="true"><Search /></el-icon><span>快捷入口</span><kbd>Ctrl K</kbd>
      </button>

      <nav class="app-menu" aria-label="学习功能导航">
        <section v-for="group in navigationGroups" :key="group.label" class="nav-group" :aria-label="group.label">
          <h2 class="nav-group-label">{{ group.label }}</h2>
          <router-link v-for="item in group.items" :key="item.path" :to="item.path" class="desktop-nav-link" :title="item.description">
            <el-icon aria-hidden="true"><component :is="item.icon" /></el-icon>
            <span class="nav-label">{{ item.label }}</span>
          </router-link>
        </section>
      </nav>

      <div class="sidebar-footer">
        <span class="sidebar-footer-label">学习安排，由你决定</span>
      </div>
    </el-aside>

    <el-container>
      <el-header class="app-header" :class="{ 'has-view-modes': hasViewModes }">
        <div class="header-identity">
          <div class="desktop-context"><span>学习空间</span><span aria-hidden="true">/</span><strong>{{ currentPageLabel }}</strong></div>
          <span class="mobile-brand" aria-label="学伴管家">
            <BrandMark class="compact-brand-mark" />
            <span>学伴管家</span>
          </span>
          <button type="button" class="mobile-command-trigger" aria-label="搜索页面和快捷操作" aria-haspopup="dialog" @click="openCommandMenu"><el-icon aria-hidden="true"><Search /></el-icon></button>
        </div>
          <div v-if="hasViewModes" class="view-mode-switch" :class="{ 'is-detailed': isDetailedView }" role="group" aria-label="页面内容视图">
            <button
              type="button"
              :class="{ 'is-active': isConciseView }"
              :aria-pressed="isConciseView"
              title="突出当前任务，详细选项按需展开"
              @click="setViewMode('concise')"
            >
              简洁视图
            </button>
            <button
              type="button"
              :class="{ 'is-active': isDetailedView }"
              :aria-pressed="isDetailedView"
              title="显示完整筛选、统计与学习记录"
              @click="setViewMode('detailed')"
            >
              完整视图
            </button>
          </div>
          <span v-else class="header-page-name">{{ currentPageLabel }}</span>
          <button
            type="button"
            class="connection-status"
            :class="`is-${connectionState}`"
            :disabled="connectionState === 'checking'"
            :aria-label="`${connectionLabel}，重新检查服务连接`"
            :title="`${connectionLabel}，点击重新检查`"
            @click="checkConnection"
          >
            <span class="connection-dot" aria-hidden="true"></span>
            <span aria-live="polite" aria-atomic="true">{{ connectionState === 'offline' ? '未连接 · 重试' : connectionState === 'online' ? '已连接' : '连接中' }}</span>
          </button>
          <el-dropdown class="account-dropdown" trigger="click" @command="handleAccountCommand">
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
      </el-header>

      <el-main id="main-content" class="app-main" tabindex="-1">
        <slot />
      </el-main>
    </el-container>
  </el-container>

  <nav ref="mobileNav" class="mobile-nav" aria-label="移动端主导航">
    <router-link v-for="item in mobileNavigation" :key="item.path" :to="item.path">
      <el-icon aria-hidden="true"><component :is="item.icon" /></el-icon>
      <span>{{ item.shortLabel }}</span>
    </router-link>
    <button
      ref="mobileMenuTrigger"
      type="button"
      aria-haspopup="dialog"
      :aria-expanded="mobileMenuOpen"
      :class="{ 'is-active': isAdditionalPage || mobileMenuOpen }"
      @click="mobileMenuOpen = true"
    >
      <el-icon aria-hidden="true"><Grid /></el-icon>
      <span>全部功能</span>
    </button>
  </nav>

  <el-dialog
    v-model="mobileMenuOpen"
    title="全部功能"
    class="all-features-dialog"
    width="560px"
    append-to-body
    :close-on-click-modal="true"
    :close-on-press-escape="true"
    @closed="restoreMobileMenuFocus"
  >
    <nav class="all-features-nav" aria-label="全部学习功能">
      <section v-for="group in navigationGroups" :key="group.label" :aria-label="group.label">
        <h2 class="nav-group-label">{{ group.label }}</h2>
        <div class="all-features-group">
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            @click="closeMobileMenu(item.path)"
          >
            <el-icon aria-hidden="true"><component :is="item.icon" /></el-icon>
            <span><strong>{{ item.label }}</strong><small>{{ item.description }}</small></span>
          </router-link>
        </div>
      </section>
    </nav>
    <template #footer>
      <el-button @click="mobileMenuOpen = false">关闭</el-button>
    </template>
  </el-dialog>

  <WorkspaceCommandMenu v-if="commandMenuMounted" v-model:open="commandMenuOpen" :navigation="navigationGroups.flatMap(group => group.items)" @closed="restoreCommandFocus" />
</template>

<script setup>
import { computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElDialog } from 'element-plus'
import { Aim, ArrowDown, Calendar, Clock, Collection, Grid, House, List, Search, Setting, Timer } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

import { healthApi } from '../api'
import { authSession, logout } from '../auth/session'
import { useViewMode } from '../composables/useViewMode'
import { isCommandShortcut } from '../utils/workspaceCommands'
import BrandMark from './BrandMark.vue'

const WorkspaceCommandMenu = defineAsyncComponent(() => import('./WorkspaceCommandMenu.vue'))
const commandMenuMounted = ref(false)
const commandMenuOpen = ref(false)
let commandTrigger = null

function openCommandMenu() {
  commandTrigger = document.activeElement
  commandMenuMounted.value = true
  commandMenuOpen.value = true
}
function restoreCommandFocus(navigating) {
  if (!navigating && commandTrigger?.isConnected) commandTrigger.focus({ preventScroll: true })
}
function handleWorkspaceKey(event) {
  if (!isCommandShortcut(event)) return
  if (commandMenuOpen.value) { event.preventDefault(); commandMenuOpen.value = false; return }
  // Never cover an in-progress confirmation or form with a second dialog.
  if ([...document.querySelectorAll('[role="dialog"]')].some(dialog => dialog.getClientRects().length)) return
  event.preventDefault()
  openCommandMenu()
}

const route = useRoute()
const router = useRouter()
const mobileNav = ref(null)
const mobileMenuTrigger = ref(null)
const mobileMenuOpen = ref(false)
const menuNavigationPending = ref(false)
const navigationGroups = [
  {
    label: '日常学习',
    items: [
      { path: '/app', label: '学习总览', shortLabel: '总览', icon: House, description: '看看今天要做什么' },
      { path: '/tasks', label: '截止任务', shortLabel: '任务', icon: List, description: '安排作业与截止时间' },
      { path: '/focus', label: '专注计时', shortLabel: '专注', icon: Timer, description: '留出一段专心的时间' },
      { path: '/schedule', label: '课表与考试', shortLabel: '日程', icon: Clock, description: '查看课程与考试安排' },
    ],
  },
  {
    label: '学习管理',
    items: [
      { path: '/materials', label: '资料库', icon: Collection, description: '整理资料与课程通知' },
      { path: '/study-plans', label: '复习计划', icon: Calendar, description: '把复习分配到每一天' },
      { path: '/deadline-radar', label: 'DDL 应变台', icon: Aim, description: '截止有变，重新安排' },
      { path: '/settings', label: '设置', icon: Setting, description: '管理账号与学习偏好' },
    ],
  },
]
const mobileNavigation = navigationGroups[0].items
const isAdditionalPage = computed(() => !mobileNavigation.some((item) => item.path === route.path))
const hasViewModes = computed(() => ['/app', '/materials', '/tasks', '/study-plans', '/settings'].includes(route.path))
const currentPageLabel = computed(() => navigationGroups.flatMap((group) => group.items).find((item) => item.path === route.path)?.label || '学习空间')
const { isConciseView, isDetailedView, setViewMode, viewModeAnnouncement } = useViewMode()
const connectionState = ref('checking')
const connectionLabel = computed(() => ({ checking: '检查连接中', online: '服务已连接', offline: '服务未连接' })[connectionState.value])
const userInitial = computed(() => authSession.user?.display_name?.trim()?.slice(0, 1)?.toUpperCase() || '学')

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
  document.getElementById('main-content')?.focus({ preventScroll: true })
}

function closeMobileMenu(path) {
  menuNavigationPending.value = path !== route.path
  mobileMenuOpen.value = false
}

function restoreMobileMenuFocus() {
  if (menuNavigationPending.value) {
    focusMain()
  } else {
    mobileMenuTrigger.value?.focus({ preventScroll: true })
  }
  menuNavigationPending.value = false
}

let mobileNavResizeObserver
let mobileNavResizeHandler

function syncMobileNavHeight() {
  const height = mobileNav.value?.getBoundingClientRect().height ?? 0
  document.documentElement.style.setProperty('--mobile-nav-height', `${Math.ceil(height)}px`)
}

watch(() => route.path, async () => {
  const wasMenuOpen = mobileMenuOpen.value
  mobileMenuOpen.value = false
  await nextTick()
  if (!wasMenuOpen) window.requestAnimationFrame(focusMain)
})

onMounted(() => {
  window.addEventListener('keydown', handleWorkspaceKey)
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
  window.removeEventListener('keydown', handleWorkspaceKey)
  mobileNavResizeObserver?.disconnect()
  if (mobileNavResizeHandler) window.removeEventListener('resize', mobileNavResizeHandler)
  document.documentElement.style.removeProperty('--mobile-nav-height')
})
</script>

<style scoped>
.compact-brand-mark { width: 30px; height: 30px; border-radius: 6px; }
.workspace-search { display: flex; align-items: center; gap: 9px; min-height: 42px; margin: -10px 20px 22px; padding: 8px 10px; border: 1px solid var(--ledger-line); border-radius: 8px; color: var(--ledger-muted); background: var(--ledger-canvas); text-align: left; cursor: pointer; }
.workspace-search span { flex: 1; font-size: 12px; }
.workspace-search kbd { font: inherit; font-size: 10px; color: var(--ledger-muted); }
.workspace-search:hover { border-color: #9ebfac; color: var(--ledger-link); }
.mobile-command-trigger { display: none; }
@media (max-width: 900px) { .header-identity { display: flex; align-items: center; gap: 12px; } .mobile-command-trigger { display: grid; place-items: center; flex-shrink: 0; width: 44px; height: 44px; padding: 0; color: var(--ledger-link); border: 0; border-radius: 8px; background: transparent; font-size: 19px; cursor: pointer; } }
.account-button { min-height: 44px; max-width: 230px; display: inline-flex; align-items: center; gap: 9px; padding: 5px 9px 5px 6px; border: 1px solid var(--ledger-line); border-radius: 10px; background: #fff; color: var(--ledger-ink); cursor: pointer; text-align: left; }
.account-button:hover { border-color: #b4cfc1; background: var(--ledger-canvas); }
.account-button:focus-visible { outline: 3px solid rgba(50, 120, 100, .35); outline-offset: 2px; }
.account-avatar { width: 30px; height: 30px; flex: 0 0 auto; display: grid; place-items: center; border-radius: 50%; background: #e7f0ea; color: var(--ledger-link); font-weight: 700; }
.account-copy { min-width: 0; display: grid; line-height: 1.15; }
.account-copy strong, .account-copy small { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.account-copy strong { font-size: 13px; }
.account-copy small { margin-top: 3px; color: var(--ledger-muted); font-size: 11px; }
@media (max-width: 1180px) { .account-copy { display: none; } .account-button { max-width: none; } }
@media (max-width: 900px) { .account-button { padding: 4px; min-width: 44px; justify-content: center; border-color: transparent; } .account-button > .el-icon { display: none; } }
</style>
