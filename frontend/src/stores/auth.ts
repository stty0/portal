import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { authApi } from '@/api/auth'
import { setToken } from '@/api/client'
import type { Me } from '@/types/api'

export const useAuthStore = defineStore('auth', () => {
  const me = ref<Me | null>(null)
  const loading = ref(false)

  /** 권한 판정은 서버가 준 permissions만 근거로 한다 — role 문자열로 분기하지 않는다. */
  const isAdmin = computed(() => me.value?.permissions.includes('admin:access') ?? false)
  const isAuthenticated = computed(() => me.value !== null)

  async function login(username: string, password: string): Promise<void> {
    const { access_token } = await authApi.login(username, password)
    setToken(access_token)
    me.value = await authApi.me()
  }

  /** 새로고침 후 복구용. 토큰이 죽었으면 조용히 로그아웃 상태로 둔다. */
  async function restore(): Promise<void> {
    loading.value = true
    try {
      me.value = await authApi.me()
    } catch {
      me.value = null
      setToken(null)
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    try {
      await authApi.logout()
    } catch {
      // 서버 세션이 이미 사라졌어도 로컬 상태는 반드시 비운다.
    }
    setToken(null)
    me.value = null
  }

  function clear(): void {
    me.value = null
    setToken(null)
  }

  return { me, loading, isAdmin, isAuthenticated, login, restore, logout, clear }
})
