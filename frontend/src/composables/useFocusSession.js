import { computed, ref, shallowRef, watch } from 'vue'
import { authSession } from '../auth/session'
import { activeElapsedSeconds, formatClock, normalizeCustomMinutes } from '../utils/focusTimer'

const storageKey = 'study-focus-session'
const session = shallowRef(null)
const recording = ref(false)
const now = ref(Date.now())
let ticker

const elapsed = computed(() => {
  const current = session.value
  if (!current) return 0
  return activeElapsedSeconds(
    current.accumulatedSeconds, current.startedAt || now.value, now.value, current.duration * 60,
  )
})
const remaining = computed(() => formatClock((session.value?.duration || 0) * 60 - elapsed.value))

function update(next) {
  session.value = next
  try {
    if (next) window.sessionStorage.setItem(storageKey, JSON.stringify(next))
    else window.sessionStorage.removeItem(storageKey)
  } catch {
    // Keep the timer usable if the browser blocks storage.
  }
}

function tick() {
  now.value = Date.now()
  if (session.value?.startedAt && elapsed.value >= session.value.duration * 60) pause('finished')
}

function pause(phase = 'paused') {
  if (!session.value) return
  now.value = Date.now()
  const duration = session.value.duration * 60
  update({
    ...session.value,
    accumulatedSeconds: elapsed.value,
    startedAt: null,
    phase: elapsed.value >= duration ? 'finished' : phase,
  })
}

function start(task, duration) {
  const user = authSession.user
  if (!user || !task) return
  now.value = Date.now()
  update({
    accountId: user.id,
    taskId: task.id,
    taskKey: task.navigation_key,
    taskName: task.name,
    duration,
    phase: 'running',
    startedAt: now.value,
    accumulatedSeconds: session.value?.accumulatedSeconds || 0,
    attempt: null,
  })
}

function rememberAttempt(attempt) {
  if (session.value) update({ ...session.value, attempt })
}

watch(() => session.value?.phase, (phase) => {
  clearInterval(ticker)
  if (phase === 'running') ticker = setInterval(tick, 250)
}, { flush: 'sync' })

watch(() => authSession.user?.id, (accountId, previousAccountId) => {
  if (previousAccountId !== undefined) {
    update(null)
    recording.value = false
  }
  if (accountId === undefined) return
  try {
    const restored = JSON.parse(window.sessionStorage.getItem(storageKey))
    if (restored?.accountId !== accountId || !restored.taskId || !restored.taskKey) return
    if (normalizeCustomMinutes(restored.duration) !== restored.duration
      || !Number.isFinite(restored.accumulatedSeconds)
      || !['running', 'paused', 'finished'].includes(restored.phase)
      || (restored.phase === 'running' && !Number.isFinite(restored.startedAt))) return
    now.value = Date.now()
    session.value = restored
    tick()
  } catch {
    // A damaged or unavailable snapshot can be ignored.
  }
}, { immediate: true, flush: 'sync' })

export function useFocusSession() {
  return { session, recording, elapsed, remaining, start, pause, reset: () => update(null), rememberAttempt }
}
