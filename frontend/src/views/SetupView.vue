<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import type { AdCandidate } from '@/types/api'
import Btn from '@/components/ui/Btn.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Field from '@/components/ui/Field.vue'
import Fid from '@/components/ui/Fid.vue'

/**
 * 최초 실행 부트스트랩 (C-02) — 2단계.
 *
 *   1) AD 연결 정보 입력 → bind 검증 → **실제 조회된 계정 목록**을 받는다
 *   2) 그 목록에서 첫 관리자를 고른다
 *
 * 관리자 계정명을 손으로 받아치면 오타 하나로 실패하고, 그 계정이 허용 그룹 안에서
 * 실제로 보이는지 확인할 방법이 없다. 연결을 먼저 증명하고 목록에서 고르게 한다.
 *
 * 이 화면은 관리자가 아직 없어 미인증 상태로 열리므로 1회용 setup 토큰으로 보호한다.
 * 성공 후 서버가 재실행을 하드 거부하므로 다시 열리지 않는다.
 */
const router = useRouter()
const step = ref<1 | 2 | 3>(1)
const busy = ref(false)
const error = ref<unknown>(null)
const candidates = ref<AdCandidate[]>([])
const selected = ref<string>('')
const seeded = ref('')

const form = reactive({
  setup_token: '',
  ldaps_url: '',
  base_dn: '',
  bind_account: '',
  bind_password: '',
  allowed_group: '',
  id_attribute: 'sAMAccountName',
})

onMounted(async () => {
  const { bootstrap_required } = await authApi.setupStatus()
  if (!bootstrap_required) router.replace({ name: 'login' })
})

const canProbe = computed(
  () =>
    Boolean(form.setup_token && form.ldaps_url && form.base_dn && form.bind_account && form.bind_password),
)

async function probe() {
  busy.value = true
  error.value = null
  try {
    const res = await authApi.setupProbe({ ...form, allowed_group: form.allowed_group || null })
    candidates.value = res.users
    selected.value = res.users[0]?.username ?? ''
    step.value = 2
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}

async function confirm() {
  busy.value = true
  error.value = null
  try {
    await authApi.setup({
      ...form,
      allowed_group: form.allowed_group || null,
      seed_admin_username: selected.value,
    })
    seeded.value = selected.value
    step.value = 3
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}

const inputClass =
  'w-full px-3 py-2 rounded-lg border border-line-dark text-[13.5px] outline-none focus:border-brand-500'
</script>

<template>
  <div class="min-h-screen bg-bg flex items-center justify-center p-6">
    <div class="w-full max-w-2xl bg-surface border border-line rounded-card shadow-card p-8">
      <div class="flex items-center gap-2.5 mb-6">
        <span class="w-9 h-9 rounded-lg bg-brand-700 text-white grid place-items-center font-bold">H</span>
        <div class="flex-1">
          <b class="block text-ink">최초 실행 설정</b>
          <small class="text-ink-3 text-[12px]">AD 연결 후 첫 관리자를 지정합니다</small>
        </div>
        <Fid id="C-02" />
      </div>

      <!-- 단계 표시 -->
      <ol class="flex items-center gap-2 mb-6 text-[12.5px]">
        <li
          v-for="(label, i) in ['AD 연결', '관리자 지정', '완료']"
          :key="label"
          class="flex items-center gap-2"
        >
          <span
            class="w-6 h-6 rounded-full grid place-items-center font-bold text-[11px]"
            :class="step > i + 1 ? 'bg-ok text-white' : step === i + 1 ? 'bg-brand-700 text-white' : 'bg-idle-bg text-ink-3'"
          >{{ step > i + 1 ? '✓' : i + 1 }}</span>
          <span :class="step === i + 1 ? 'font-semibold text-ink' : 'text-ink-3'">{{ label }}</span>
          <span v-if="i < 2" class="w-6 h-px bg-line-dark" />
        </li>
      </ol>

      <ErrorNote :error="error" />

      <!-- 1단계: AD 연결 -->
      <form v-if="step === 1" @submit.prevent="probe">
        <div class="px-3.5 py-2.5 rounded-lg bg-warn-bg text-warn text-[13px] mb-5">
          <b>1회용 설정입니다.</b> 완료되면 서버가 재실행을 거부합니다. setup 토큰은 설치 시
          서버 로그에 출력된 값입니다.
        </div>

        <div class="grid sm:grid-cols-2 gap-4">
          <Field label="Setup 토큰" required full hint="설치 시 발급된 1회용 토큰">
            <input v-model="form.setup_token" required type="password" :class="inputClass" />
          </Field>
          <Field label="LDAP(S) URL" required full hint="인증서가 있으면 ldaps:// 권장 — 평문은 비밀번호가 노출됩니다">
            <input v-model="form.ldaps_url" required :class="[inputClass, 'mono']" placeholder="ldaps://ad.corp.com:636" />
          </Field>
          <Field label="Base DN" required>
            <input v-model="form.base_dn" required :class="[inputClass, 'mono']" placeholder="DC=corp,DC=com" />
          </Field>
          <Field label="Bind 계정" required hint="사용자 조회용 서비스 계정">
            <input v-model="form.bind_account" required :class="[inputClass, 'mono']" placeholder="svc-portal@corp.com" />
          </Field>
          <Field label="Bind 암호" required hint="Secret 저장소에만 보관되며 다시 표시되지 않습니다">
            <input v-model="form.bind_password" required type="password" :class="inputClass" />
          </Field>
          <Field label="식별 속성" hint="SSSD 기본값과 맞춥니다">
            <select v-model="form.id_attribute" :class="inputClass">
              <option>sAMAccountName</option><option>uid</option>
            </select>
          </Field>
          <Field label="허용 그룹" full hint="비우면 전 AD 사용자가 포털 사용자가 됩니다">
            <input v-model="form.allowed_group" :class="[inputClass, 'mono']" placeholder="cn=HPC-Users,dc=corp,dc=com" />
          </Field>
        </div>

        <div class="mt-6 flex justify-end">
          <Btn type="submit" variant="primary" :disabled="busy || !canProbe">
            {{ busy ? 'AD 연결 확인 중…' : 'AD 연결하고 계정 조회' }}
          </Btn>
        </div>
      </form>

      <!-- 2단계: 관리자 지정 -->
      <div v-else-if="step === 2">
        <div class="px-3.5 py-2.5 rounded-lg bg-ok-bg text-ok text-[13px] mb-5">
          AD 연결 성공 — <b>{{ candidates.length }}개</b> 계정이 조회됐습니다.
          이 중 한 명을 <b>첫 관리자</b>로 지정합니다.
        </div>

        <div v-if="!candidates.length" class="px-3.5 py-2.5 rounded-lg bg-warn-bg text-warn text-[13px] mb-5">
          조회된 계정이 없습니다. 허용 그룹 조건이 너무 좁거나 Base DN이 맞지 않을 수 있습니다.
        </div>

        <div v-else class="max-h-72 overflow-y-auto border border-line rounded-lg divide-y divide-line">
          <label
            v-for="u in candidates"
            :key="u.object_guid"
            class="flex items-start gap-3 p-3 cursor-pointer"
            :class="selected === u.username ? 'bg-brand-50' : 'hover:bg-bg'"
          >
            <input v-model="selected" type="radio" :value="u.username" class="mt-1 accent-brand-700" />
            <span class="min-w-0 flex-1">
              <b class="block text-[13.5px] mono">{{ u.username }}</b>
              <span class="block text-[12.5px] text-ink-3">
                {{ u.display_name || '—' }}<span v-if="u.email"> · {{ u.email }}</span>
              </span>
              <code class="text-[10.5px] text-ink-3 mono">{{ u.object_guid }}</code>
            </span>
          </label>
        </div>

        <p class="mt-3 text-[12px] text-ink-3 leading-relaxed">
          지정된 계정만 관리자가 되고, 나머지는 로그인 시 일반 사용자로 자동 등록됩니다.
          역할은 포털이 관리하며 AD 그룹은 변경되지 않습니다.
        </p>

        <div class="mt-6 flex justify-between">
          <Btn :disabled="busy" @click="step = 1">← 연결 정보 수정</Btn>
          <Btn variant="primary" :disabled="busy || !selected" @click="confirm">
            {{ busy ? '지정 중…' : `${selected} 을(를) 관리자로 지정` }}
          </Btn>
        </div>
      </div>

      <!-- 3단계: 완료 -->
      <div v-else>
        <div class="px-4 py-3 rounded-lg bg-ok-bg text-ok text-[13.5px] mb-5">
          설정이 완료됐습니다. <b class="mono">{{ seeded }}</b> 계정이 첫 관리자로 지정됐습니다.
          이 화면은 다시 열리지 않습니다.
        </div>
        <Btn variant="primary" @click="router.replace({ name: 'login' })">로그인 화면으로</Btn>
      </div>
    </div>
  </div>
</template>
