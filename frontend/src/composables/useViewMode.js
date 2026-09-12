import { computed, ref } from 'vue'

const VIEW_MODE_STORAGE_KEY = 'study-ledger:view-mode'
const viewMode = ref(readStoredViewMode())
const viewModeAnnouncement = ref('')

function readStoredViewMode() {
  try {
    if (typeof window !== 'undefined' && window.localStorage.getItem(VIEW_MODE_STORAGE_KEY) === 'detailed') {
      return 'detailed'
    }
  } catch {
    // Storage can be unavailable in private browsing or restrictive web views.
  }
  return 'concise'
}

export function useViewMode() {
  const isConciseView = computed(() => viewMode.value === 'concise')
  const isDetailedView = computed(() => viewMode.value === 'detailed')

  function setViewMode(mode) {
    const nextMode = mode === 'detailed' ? 'detailed' : 'concise'
    viewMode.value = nextMode
    viewModeAnnouncement.value = nextMode === 'detailed'
      ? '已切换为完整视图。'
      : '已切换为简洁视图。'
    try {
      if (typeof window !== 'undefined') window.localStorage.setItem(VIEW_MODE_STORAGE_KEY, nextMode)
    } catch {
      // The active view remains usable even when the preference cannot be saved.
    }
  }

  return { viewMode, isConciseView, isDetailedView, viewModeAnnouncement, setViewMode }
}
