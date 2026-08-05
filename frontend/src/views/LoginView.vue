<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useClusterStore } from '@/stores/cluster'
import Btn from '@/components/ui/Btn.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const clusters = useClusterStore()

const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref<unknown>(null)

onMounted(async () => {
  // 부트스트랩 전이면 로그인 자체가 불가능하다 — 최초 설정 화면으로 보낸다(C-02).
  try {
    const { bootstrap_required } = await authApi.setupStatus()
    if (bootstrap_required) router.replace({ name: 'setup' })
  } catch {
    // 상태 조회 실패는 로그인 시도 자체를 막지 않는다.
  }
})

async function submit() {
  busy.value = true
  error.value = null
  try {
    await auth.login(username.value, password.value)
    await clusters.load()
    const target = typeof route.query.redirect === 'string' ? route.query.redirect : null
    router.push(target ?? (auth.isAdmin ? '/admin/dashboard' : '/cluster'))
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="min-h-screen grid lg:grid-cols-2">
    <!-- 좌: 브랜드 히어로 -->
    <div class="hidden lg:flex bg-grad-hero text-white p-12 flex-col justify-center">
      <p class="text-[15px] font-semibold tracking-widest opacity-80">SLURM HPC PORTAL</p>
      <h1 class="mt-4 text-4xl font-bold leading-tight">
        여러 Slurm 클러스터를,<br />브라우저 하나로.
      </h1>
      <p class="mt-5 text-white/75 leading-relaxed max-w-md">
        CLI 없이 Job을 제출하고 자원을 모니터링합니다. 파일 관리, 인터랙티브 앱, 사용량 통계까지
        한 곳에서 처리합니다.
      </p>
      <ul class="mt-8 space-y-2 text-[14.5px] text-white/70">
        <li>· 폼·스크립트·템플릿 기반 Job 제출</li>
        <li>· 클러스터별 자원 현황과 대기 큐</li>
        <li>· 관리자 콘솔에서 노드·정책·사용자 관리</li>
      </ul>
    </div>

    <!-- 우: 로그인 폼 -->
    <div class="flex items-center justify-center p-6 bg-surface">
      <form class="w-full max-w-sm" @submit.prevent="submit">
        <div class="flex items-center gap-2.5 mb-8">
          <span class="w-9 h-9 rounded-lg bg-brand-700 text-white grid place-items-center font-bold">H</span>
          <div>
            <b class="block text-ink">HPC Portal</b>
            <small class="text-ink-3 text-[13px]">Slurm 클러스터 통합 포털</small>
          </div>
        </div>

        <h2 class="text-[21px] font-bold text-ink mb-1 flex items-center gap-2">
          로그인 <Fid id="C-01" />
        </h2>
        <p class="text-[14px] text-ink-3 mb-6">회사 AD 계정으로 로그인 · 접근 문의는 관리자</p>

        <ErrorNote :error="error" />

        <label class="block text-[14px] font-semibold text-ink-2 mb-1.5">사용자 ID</label>
        <input
          v-model="username"
          autocomplete="username"
          required
          class="w-full mb-4 px-3 py-2.5 rounded-lg border border-line-dark bg-surface text-[15px] outline-none focus:border-brand-500"
          placeholder="AD 계정 (sAMAccountName)"
        />

        <label class="block text-[14px] font-semibold text-ink-2 mb-1.5">비밀번호</label>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
          class="w-full mb-6 px-3 py-2.5 rounded-lg border border-line-dark bg-surface text-[15px] outline-none focus:border-brand-500"
          placeholder="••••••••"
        />

        <Btn type="submit" variant="primary" :disabled="busy" class="w-full">
          {{ busy ? '확인 중…' : '로그인' }}
        </Btn>

        <p class="mt-6 text-[13px] text-ink-3 leading-relaxed">
          인증은 Active Directory가 처리하고, 역할(USER/ADMIN)은 포털이 관리합니다.
          비밀번호는 포털에 저장되지 않습니다.
        </p>
      </form>
    </div>
  </div>
</template>
