<template>
  <a class="skip-link" href="#main-content">跳到主要内容</a>
  <el-container class="app-shell">
    <el-aside width="240px" class="app-sidebar">
      <div class="brand">
        <div class="brand-mark">学</div>
        <div>
          <div class="brand-title">学伴管家</div>
          <div class="brand-subtitle">学习资料与 DDL 管理</div>
        </div>
      </div>

      <el-menu :default-active="$route.path" router class="app-menu">
        <el-menu-item index="/">
          <el-icon><House /></el-icon>
          <span>学习总览</span>
        </el-menu-item>
        <el-menu-item index="/materials">
          <el-icon><Collection /></el-icon>
          <span>资料库</span>
        </el-menu-item>
        <el-menu-item index="/tasks">
          <el-icon><List /></el-icon>
          <span>DDL 任务</span>
        </el-menu-item>
        <el-menu-item index="/study-plans">
          <el-icon><Calendar /></el-icon>
          <span>复习计划</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>设置</span>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <el-tag type="success" effect="light" round>本地演示模式</el-tag>
        <span>数据保存在本机 SQLite</span>
      </div>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div class="header-context">
          <div class="header-kicker">PERSONAL STUDY SPACE</div>
          <div class="header-title">{{ $route.meta.title || '学习总览' }}</div>
        </div>
        <div class="mobile-brand" aria-label="学伴管家">
          <span class="mobile-brand-mark">学</span>
          <span>学伴管家</span>
        </div>
        <div class="header-actions">
          <el-tag :type="connectionType" effect="plain" aria-live="polite">{{ connectionLabel }}</el-tag>
          <el-button
            link
            class="connection-retry"
            :loading="connectionState === 'checking'"
            :disabled="connectionState === 'checking'"
            aria-label="重新检查 API 连接"
            @click="checkConnection"
          >
            <el-icon><Refresh /></el-icon>
            重试
          </el-button>
          <el-avatar :size="36" class="user-avatar">我</el-avatar>
        </div>
      </el-header>

      <el-main id="main-content" class="app-main" tabindex="-1">
        <router-view />
      </el-main>
    </el-container>
  </el-container>

  <nav class="mobile-nav" aria-label="移动端主导航">
    <router-link to="/">
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
import { computed, onMounted, ref } from 'vue'
import { Calendar, Collection, House, List, Refresh, Setting } from '@element-plus/icons-vue'

import { healthApi } from './api'

const connectionState = ref('checking')
const connectionLabel = computed(() => ({
  checking: '检查连接中',
  online: 'API 已连接',
  offline: 'API 未连接',
}[connectionState.value]))
const connectionType = computed(() => ({
  checking: 'info',
  online: 'success',
  offline: 'danger',
}[connectionState.value]))

async function checkConnection() {
  connectionState.value = 'checking'
  try {
    await healthApi.check()
    connectionState.value = 'online'
  } catch {
    connectionState.value = 'offline'
  }
}

onMounted(checkConnection)
</script>
