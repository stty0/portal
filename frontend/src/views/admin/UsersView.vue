<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { userApi } from '@/api/users'
import type { User } from '@/types/api'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'

const rows = ref<User[]>([])
const total = ref(0)
const loading = ref(false)
const error = ref<unknown>(null)
const q = ref('')
const roleFilter = ref('')
const editing = ref<User | null>(null)
const draftRole = ref('USER')

async function load() {
  loading.value = true
  error.value = null
  try {
    const page = await userApi.list({ q: q.value || undefined, role: roleFilter.value || undefined, size: 100 })
    rows.value = page.items
    total.value = page.total
  } catch (e) {
    error.value = e
  } finally {
    loading.value = false
  }
}
onMounted(load)

function openRole(u: User) {
  editing.value = u
  draftRole.value = u.role ?? 'USER'
}

async function saveRole() {
  if (!editing.value) return
  try {
    await userApi.update(editing.value.ad_object_guid, { role: draftRole.value })
    editing.value = null
    await load()
  } catch (e) {
    error.value = e
  }
}

async function toggleActive(u: User) {
  const next = !u.is_active
  if (!next && !confirm(`${u.username} 을(를) 비활성화할까요? 기존 세션도 즉시 종료됩니다.`)) return
  try {
    await userApi.update(u.ad_object_guid, { is_active: next })
    await load()
  } catch (e) {
    error.value = e
  }
}
</script>

<template>
  <PageHead
    title="사용자"
    :crumbs="['HPC Portal Admin', '사용자 / 정책', '사용자']"
    :sub="`AD 자동 프로비저닝 · 총 ${total}명 · 역할은 포털이 관리`"
  >
    <template #actions>
      <RouterLink to="/admin/ad"><Btn>🔗 AD 연결</Btn></RouterLink>
      <Btn @click="load">↻ 새로고침</Btn>
    </template>
  </PageHead>

  <ErrorNote :error="error" />

  <div class="px-3.5 py-2.5 rounded-lg bg-info-bg text-info text-[13px] mb-4">
    <b>AD 자동 프로비저닝</b> — 허용 그룹 조건에 맞는 AD 사용자는 로그인·동기화 시 자동으로
    활성 사용자가 됩니다. 별도 가입 승인 절차는 없습니다. <Fid id="A-US-01" />
  </div>

  <Card flush>
    <template #head>
      <div class="flex flex-wrap items-center gap-2">
        <input
          v-model="q" placeholder="사용자 검색"
          class="px-2.5 py-1.5 rounded-lg border border-line-dark text-[13px]"
          @keyup.enter="load"
        />
        <select v-model="roleFilter" class="px-2.5 py-1.5 rounded-lg border border-line-dark text-[13px]" @change="load">
          <option value="">역할 전체</option><option>ADMIN</option><option>USER</option>
        </select>
        <Btn size="sm" @click="load">검색</Btn>
      </div>
    </template>

    <div v-if="loading" class="py-12 text-center text-ink-3">불러오는 중…</div>
    <Empty v-else-if="!rows.length" text="사용자가 없습니다. AD 동기화를 실행해 보세요." />
    <Table
      v-else
      :columns="[
        { key: 'u', label: '사용자' },
        { key: 'e', label: '이메일' },
        { key: 'r', label: '역할', width: '110px' },
        { key: 's', label: '상태', width: '100px' },
        { key: 'l', label: '최근 로그인', width: '160px' },
        { key: 'a', label: '액션', width: '170px' },
      ]"
    >
      <tr v-for="u in rows" :key="u.ad_object_guid" class="border-b border-line last:border-0 hover:bg-bg">
        <td class="px-3.5 py-2.5">
          <b class="mono">{{ u.username }}</b>
          <p class="text-[12px] text-ink-3">{{ u.display_name ?? '—' }}</p>
          <code class="text-[10.5px] text-ink-3 mono" :title="u.ad_object_guid">
            {{ u.ad_object_guid.slice(0, 8) }}…
          </code>
        </td>
        <td class="px-3.5 py-2.5 mono text-[12.5px]">{{ u.email ?? '—' }}</td>
        <td class="px-3.5 py-2.5">
          <Chip :tone="u.role === 'ADMIN' ? 'brand' : 'gray'">{{ u.role ?? '—' }}</Chip>
        </td>
        <td class="px-3.5 py-2.5">
          <Badge :state="u.is_active ? 'idle' : 'cancelled'">{{ u.is_active ? '활성' : '비활성' }}</Badge>
        </td>
        <td class="px-3.5 py-2.5 mono text-[12px]">{{ u.last_login_at?.slice(0, 16).replace('T', ' ') ?? '—' }}</td>
        <td class="px-3.5 py-2.5">
          <div class="flex gap-1.5">
            <Btn size="sm" @click="openRole(u)">역할</Btn>
            <Btn size="sm" :variant="u.is_active ? 'danger' : 'outline'" @click="toggleActive(u)">
              {{ u.is_active ? '비활성' : '활성' }}
            </Btn>
          </div>
        </td>
      </tr>
    </Table>

    <template #foot>
      이름·이메일 등 <b>AD 소유 필드는 포털에서 수정할 수 없습니다</b> — 포털이 관리하는 것은
      역할과 활성 여부뿐입니다. 마지막 관리자의 권한은 해제할 수 없습니다. <Fid id="C-02" />
    </template>
  </Card>

  <Modal v-if="editing" :title="`역할 변경 — ${editing.username}`" @close="editing = null">
    <template #title-extra><Fid id="C-02" /></template>
    <p class="text-[13px] text-ink-3 mb-4">
      인증은 AD가, 역할은 포털이 관리합니다. AD 그룹은 변경되지 않습니다.
    </p>
    <div class="space-y-2">
      <label
        v-for="r in ['USER', 'ADMIN']" :key="r"
        class="flex items-start gap-2.5 p-3 rounded-lg border cursor-pointer"
        :class="draftRole === r ? 'border-brand-500 bg-brand-50' : 'border-line'"
      >
        <input v-model="draftRole" type="radio" :value="r" class="mt-1 accent-brand-700" />
        <span>
          <b class="text-[13.5px]">{{ r }}</b>
          <span class="block text-[12.5px] text-ink-3">
            {{ r === 'ADMIN' ? '관리자 콘솔 접근 (admin:access)' : 'Job 제출·본인 자원 조회' }}
          </span>
        </span>
      </label>
    </div>
    <template #foot>
      <Btn @click="editing = null">취소</Btn>
      <Btn variant="primary" @click="saveRole">저장</Btn>
    </template>
  </Modal>
</template>
