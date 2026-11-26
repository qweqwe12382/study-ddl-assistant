<template>
  <div class="turnstile-challenge">
    <div ref="container"></div>
    <p v-if="failed" role="alert">
      人机验证暂不可用。
      <button type="button" @click="retry">重试</button>
    </p>
  </div>
</template>

<script>
let turnstileLoad

function loadTurnstile() {
  if (turnstileLoad) return turnstileLoad
  if (window.turnstile?.render) return Promise.resolve(window.turnstile)
  turnstileLoad = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=studyAgentTurnstileLoaded'
    script.async = true
    const cleanup = () => {
      clearTimeout(timer)
      delete window.studyAgentTurnstileLoaded
    }
    const fail = () => {
      cleanup()
      script.remove()
      reject(new Error('Unable to load Turnstile'))
    }
    const timer = setTimeout(fail, 15000)
    script.onerror = fail
    window.studyAgentTurnstileLoaded = () => {
      if (!window.turnstile?.render) {
        fail()
        return
      }
      cleanup()
      resolve(window.turnstile)
    }
    document.head.appendChild(script)
  }).catch((error) => {
    turnstileLoad = undefined
    throw error
  })
  return turnstileLoad
}
</script>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  siteKey: { type: String, required: true },
  action: { type: String, required: true },
})
const emit = defineEmits(['update:token'])
const container = ref(null)
const failed = ref(false)
let widget
let turnstile
let disposed = false

function reset() {
  emit('update:token', '')
  if (widget !== undefined) turnstile.reset(widget)
}

async function render() {
  try {
    turnstile = await loadTurnstile()
    if (disposed) return
    widget = turnstile.render(container.value, {
      sitekey: props.siteKey,
      action: props.action,
      size: container.value.clientWidth >= 300 ? 'flexible' : 'compact',
      'response-field': false,
      callback: (token) => {
        failed.value = false
        emit('update:token', token)
      },
      'expired-callback': () => emit('update:token', ''),
      'timeout-callback': () => emit('update:token', ''),
      'error-callback': () => {
        emit('update:token', '')
        failed.value = true
      },
    })
  } catch {
    if (!disposed) failed.value = true
  }
}

function retry() {
  failed.value = false
  if (widget === undefined) render()
  else reset()
}

defineExpose({ reset })
onMounted(render)
onBeforeUnmount(() => {
  disposed = true
  if (widget !== undefined) turnstile.remove(widget)
})
</script>

<style scoped>
.turnstile-challenge { min-width: 0; }
.turnstile-challenge p { margin: 4px 0; font-size: 13px; color: var(--auth-ink); }
.turnstile-challenge button { color: var(--auth-green); background: none; border: 0; font: inherit; text-decoration: underline; cursor: pointer; }
</style>
