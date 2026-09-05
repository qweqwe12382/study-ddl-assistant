import { reactive } from 'vue'

import { authApi } from '../api'

export const authSession = reactive({
  status: 'unknown',
  user: null,
})

let restorePromise = null

export async function restoreSession() {
  if (authSession.status === 'ready') return authSession.user
  if (restorePromise) return restorePromise
  authSession.status = 'loading'
  restorePromise = authApi.me()
    .then((user) => {
      authSession.user = user
      return user
    })
    .catch((error) => {
      if (error?.status !== 401) throw error
      authSession.user = null
      return null
    })
    .finally(() => {
      authSession.status = 'ready'
      restorePromise = null
    })
  return restorePromise
}

export async function login(payload) {
  const user = await authApi.login(payload)
  authSession.user = user
  authSession.status = 'ready'
  return user
}

export async function register(payload) {
  const user = await authApi.register(payload)
  authSession.user = user
  authSession.status = 'ready'
  return user
}

export async function logout() {
  try {
    await authApi.logout()
  } finally {
    authSession.user = null
    authSession.status = 'ready'
  }
}

if (typeof window !== 'undefined') {
  window.addEventListener('study-auth-expired', () => {
    authSession.user = null
    authSession.status = 'ready'
  })
}
