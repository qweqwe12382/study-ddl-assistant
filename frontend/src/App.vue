<template>
  <ElConfigProvider :locale="zhCn">
    <router-view v-if="$route.meta.publicLayout" />
    <WorkspaceShell v-else>
      <router-view v-slot="{ Component }">
        <Transition name="workspace-page" mode="out-in" appear>
          <div :key="$route.path" class="workspace-page"><component :is="Component" /></div>
        </Transition>
      </router-view>
    </WorkspaceShell>
  </ElConfigProvider>
</template>

<script setup>
import { watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElConfigProvider } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import 'dayjs/locale/zh-cn'

import { authSession } from './auth/session'
import WorkspaceShell from './components/WorkspaceShell.vue'

const route = useRoute()
const router = useRouter()

watch(() => authSession.user, (user) => {
  if (!user && authSession.status === 'ready' && !route.meta.publicLayout) {
    void router.replace({ name: 'login', query: { redirect: route.fullPath } })
  }
})
</script>
