import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '@/utils/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const accessToken = ref(localStorage.getItem('access_token') || '')
  const refreshToken = ref(localStorage.getItem('refresh_token') || '')

  const isAuthenticated = computed(() => !!accessToken.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  function setTokens (access, refresh) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
  }

  function clearTokens () {
    accessToken.value = ''
    refreshToken.value = ''
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }

  async function login (username, password) {
    const res = await api.post('/auth/login', { username, password })
    if (res.data.access_token) {
      setTokens(res.data.access_token, res.data.refresh_token)
      user.value = res.data.user
      return res.data
    }
    throw new Error('Login failed')
  }

  async function logout () {
    try {
      await api.post('/auth/logout')
    } finally {
      clearTokens()
      user.value = null
    }
  }

  async function fetchCurrentUser () {
    try {
      const res = await api.get('/auth/me')
      user.value = res.data.user
      return res.data.user
    } catch (error) {
      clearTokens()
      user.value = null
      throw error
    }
  }

  async function refreshTokenIfNeeded () {
    if (!refreshToken.value) return false

    try {
      const res = await api.post('/auth/refresh', {}, {
        headers: {
          Authorization: `Bearer ${refreshToken.value}`
        }
      })
      if (res.data.access_token) {
        setTokens(res.data.access_token, refreshToken.value)
        return true
      }
    } catch {
      clearTokens()
      user.value = null
    }
    return false
  }

  return {
    user,
    accessToken,
    refreshToken,
    isAuthenticated,
    isAdmin,
    login,
    logout,
    fetchCurrentUser,
    refreshTokenIfNeeded
  }
})
