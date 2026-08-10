<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { adApi, userApi } from '@/api/users'
import type { AdConnection, AdSyncResult, User } from '@/types/api'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Field from '@/components/ui/Field.vue'
import Fid from '@/components/ui/Fid.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'
import { inputClass } from '@/utils/form'

/**
 * SCR-13 — 사용자 목록(C-02)과 AD 연결(A-US-01)을 한 화면에 둔다.
 *
 * 나뉘어 있을 때는 "동기화했는데 사용자가 왜 안 늘지?"를 두 페이지를 오가며 확인해야
 * 했다. 원인(연결·동기화)과 결과(사용자 목록)는 같은 화면에 있어야 읽힌다.
 */
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
onMounted(() => Promise.all([load(), loadAd()]))

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

/* --- AD 연결 · 동기화 (A-US-01) --- */
const conn = ref<AdConnection | null>(null)
const lastSync = ref<AdSyncResult | null>(null)
const notice = ref("")
const busy = ref(false)
const showAdForm = ref(false)
const adForm = reactive({
  ldaps_url: "", base_dn: "", bind_account: "", bind_password: "",
  allowed_group: "", id_attribute: "sAMAccountName", sync_interval: "1h",
})

async function loadAd() {
  try {
    conn.value = await adApi.connection()
    Object.assign(adForm, {
      ldaps_url: conn.value.ldaps_url ?? "", base_dn: conn.value.base_dn ?? "",
      bind_account: conn.value.bind_account ?? "", bind_password: "",
      allowed_group: conn.value.allowed_group ?? "",
      id_attribute: conn.value.id_attribute ?? "sAMAccountName",
      sync_interval: conn.value.sync_interval ?? "1h",
    })
  } catch (e) {
    error.value = e
  }
}

async function saveAd() {
  busy.value = true
  error.value = null
  try {
    // 비밀번호는 입력했을 때만 보낸다 — 빈 값으로 덮어쓰면 안 된다.
    const payload: Record<string, unknown> = { ...adForm, allowed_group: adForm.allowed_group || null }
    if (!adForm.bind_password) delete payload.bind_password
    conn.value = (await adApi.updateConnection(payload)) as AdConnection
    showAdForm.value = false
    notice.value = "AD 연결 설정을 저장했습니다."
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}

async function testAd() {
  busy.value = true; error.value = null; notice.value = ""
  try {
    const res = await adApi.test()
    notice.value = res.ok ? "AD 연결 성공 (bind OK)" : "AD 연결 실패"
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}

/** 동기화 뒤에는 **사용자 목록도 다시 읽는다** — 결과가 같은 화면에 있으므로. */
async function sync() {
  busy.value = true; error.value = null; notice.value = ""
  try {
    lastSync.value = await adApi.sync()
    await Promise.all([loadAd(), load()])
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
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
      <Btn :disabled="busy" @click="testAd">🔌 연결 테스트</Btn>
      <Btn variant="primary" :disabled="busy" @click="sync">↻ 지금 동기화</Btn>
      <Btn :disabled="busy" @click="load">목록 새로고침</Btn>
    </template>
  </PageHead>

  <ErrorNote :error="error" />
  <div v-if="notice" class="px-3.5 py-2.5 rounded-lg bg-ok-bg text-ok text-[14px] mb-4">
    {{ notice }}
  </div>

  <div class="px-3.5 py-2.5 rounded-lg bg-info-bg text-info text-[14px] mb-4">
    <b>AD 자동 프로비저닝</b> — 허용 그룹 조건에 맞는 AD 사용자는 로그인·동기화 시 자동으로
    활성 사용자가 됩니다. 별도 가입 승인 절차는 없습니다. <Fid id="A-US-01" />
  </div>

  <!-- Billing·Job 제출과 같은 배치 — 넓은 본문(사용자 목록) + 좁은 설정 열 -->
  <div class="grid lg:grid-cols-[1fr_420px] gap-5 items-start">
    <Card flush>
    <template #head>
      <div class="flex flex-wrap items-center gap-2">
        <input
          v-model="q" placeholder="사용자 검색"
          class="px-2.5 py-1.5 rounded-lg border border-line-dark text-[14px]"
          @keyup.enter="load"
        />
        <select v-model="roleFilter" class="px-2.5 py-1.5 rounded-lg border border-line-dark text-[14px]" @change="load">
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
          <p class="text-[13px] text-ink-3">{{ u.display_name ?? '—' }}</p>
          <code class="text-[11.5px] text-ink-3 mono" :title="u.ad_object_guid">
            {{ u.ad_object_guid.slice(0, 8) }}…
          </code>
        </td>
        <td class="px-3.5 py-2.5 mono text-[13.5px]">{{ u.email ?? '—' }}</td>
        <td class="px-3.5 py-2.5">
          <Chip :tone="u.role === 'ADMIN' ? 'brand' : 'gray'">{{ u.role ?? '—' }}</Chip>
        </td>
        <td class="px-3.5 py-2.5">
          <Badge :state="u.is_active ? 'idle' : 'cancelled'">{{ u.is_active ? '활성' : '비활성' }}</Badge>
        </td>
        <td class="px-3.5 py-2.5 mono text-[13px]">{{ u.last_login_at?.slice(0, 16).replace('T', ' ') ?? '—' }}</td>
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

    <div class="space-y-5">
      <Card title="현재 AD 연결">
        <template #title-extra><Fid id="A-US-01" /></template>
        <dl v-if="conn" class="grid grid-cols-[96px_minmax(0,1fr)] gap-y-2.5 text-[14.5px]">
          <dt class="text-ink-3">LDAP URL</dt><dd class="mono break-all">{{ conn.ldaps_url ?? '—' }}</dd>
          <dt class="text-ink-3">사용자 DN</dt><dd class="mono break-all">{{ conn.base_dn ?? '—' }}</dd>
          <dt class="text-ink-3">Bind 계정</dt><dd class="mono break-all">{{ conn.bind_account ?? '—' }}</dd>
          <dt class="text-ink-3">Bind 암호</dt>
          <dd>
            <Chip :tone="conn.bind_secret_configured ? 'brand' : 'gray'">
              {{ conn.bind_secret_configured ? '••••• Secret 저장소' : '미설정' }}
            </Chip>
          </dd>
          <dt class="text-ink-3">허용 그룹</dt>
          <dd class="mono break-all">
            {{ conn.allowed_group ?? '—' }}
            <span v-if="!conn.allowed_group" class="text-warn text-[13px] block mt-0.5">
              미설정 — 전 AD 사용자가 포털 사용자가 됩니다
            </span>
          </dd>
          <dt class="text-ink-3">식별 속성</dt><dd class="mono">{{ conn.id_attribute ?? '—' }}</dd>
          <dt class="text-ink-3">부트스트랩</dt>
          <dd>
            <Chip :tone="conn.bootstrap_completed ? 'brand' : 'gray'">
              {{ conn.bootstrap_completed ? '완료 (seed ADMIN 지정됨)' : '미완료' }}
            </Chip>
          </dd>
        </dl>
        <template #foot>
          <div class="flex justify-between items-center gap-3">
            <span>Bind 암호는 Secret 저장소에만 보관되며 화면에 다시 표시되지 않습니다.</span>
            <Btn size="sm" @click="showAdForm = true">수정</Btn>
          </div>
        </template>
      </Card>

      <Card title="동기화 상태">
        <dl class="grid grid-cols-[96px_minmax(0,1fr)] gap-y-2.5 text-[14.5px] mb-4">
          <dt class="text-ink-3">주기</dt><dd class="mono">{{ conn?.sync_interval ?? '—' }}</dd>
          <dt class="text-ink-3">최근 실행</dt>
          <dd class="mono">{{ conn?.last_sync_at?.slice(0, 19).replace('T', ' ') ?? '—' }}</dd>
          <dt class="text-ink-3">최근 결과</dt><dd class="break-all">{{ conn?.last_sync_result ?? '—' }}</dd>
        </dl>

        <div v-if="lastSync" class="p-3.5 rounded-lg bg-bg text-[14px]">
          <b class="block mb-1.5">방금 실행한 동기화</b>
          <div class="grid grid-cols-3 gap-2 text-center">
            <div><span class="block text-[19px] font-bold text-ok mono">{{ lastSync.created }}</span>신규</div>
            <div><span class="block text-[19px] font-bold text-info mono">{{ lastSync.updated }}</span>갱신</div>
            <div><span class="block text-[19px] font-bold text-warn mono">{{ lastSync.deactivated }}</span>비활성</div>
          </div>
        </div>

        <template #foot>
          AD 조회가 <b>실패하면 아무도 비활성화하지 않습니다</b> — 네트워크 장애를 퇴사로
          오인하지 않기 위해서입니다. AD에서 사라진 사용자는 soft delete로 이력을 보존합니다.
        </template>
      </Card>
    </div>
  </div>

  <Modal v-if="editing" :title="`역할 변경 — ${editing.username}`" @close="editing = null">
    <template #title-extra><Fid id="C-02" /></template>
    <p class="text-[14px] text-ink-3 mb-4">
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
          <b class="text-[14.5px]">{{ r }}</b>
          <span class="block text-[13.5px] text-ink-3">
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

  <Modal v-if="showAdForm" title="AD 연결 설정" wide @close="showAdForm = false">
    <template #title-extra><Fid id="A-US-01" /></template>
    <div class="grid sm:grid-cols-2 gap-4">
      <Field label="LDAP(S) URL" required full hint="인증서가 있으면 ldaps:// 권장 — 평문은 비밀번호가 노출됩니다">
        <input v-model="adForm.ldaps_url" :class="[inputClass, 'mono']" />
      </Field>
      <Field label="사용자 DN (Users DN)" required hint="이 지점 아래에서만 사용자를 찾습니다">
        <input v-model="adForm.base_dn" :class="[inputClass, 'mono']" placeholder="OU=people,DC=corp,DC=com" />
      </Field>
      <Field label="Bind 계정" required>
        <input v-model="adForm.bind_account" :class="[inputClass, 'mono']" />
      </Field>
      <Field label="Bind 암호" full hint="비워 두면 기존 값을 유지합니다">
        <input v-model="adForm.bind_password" type="password" :class="inputClass" placeholder="재입력 시에만 변경" />
      </Field>
      <Field label="허용 그룹" full hint="그룹 DN만 유효(OU 불가) — 비우면 사용자 DN 아래 전원 허용">
        <input v-model="adForm.allowed_group" :class="[inputClass, 'mono']" placeholder="CN=HPC-Users,OU=groups,DC=corp,DC=com" />
      </Field>
      <Field label="식별 속성">
        <select v-model="adForm.id_attribute" :class="inputClass">
          <option>sAMAccountName</option><option>uid</option>
        </select>
      </Field>
      <Field label="동기화 주기">
        <input v-model="adForm.sync_interval" :class="[inputClass, 'mono']" />
      </Field>
    </div>
    <template #foot>
      <Btn @click="showAdForm = false">취소</Btn>
      <Btn variant="primary" :disabled="busy" @click="saveAd">저장</Btn>
    </template>
  </Modal>
</template>
