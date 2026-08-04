<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { adApi } from '@/api/users'
import type { AdConnection, AdSyncResult } from '@/types/api'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Field from '@/components/ui/Field.vue'
import Fid from '@/components/ui/Fid.vue'
import Modal from '@/components/ui/Modal.vue'
import PageHead from '@/components/ui/PageHead.vue'

const conn = ref<AdConnection | null>(null)
const error = ref<unknown>(null)
const notice = ref('')
const busy = ref(false)
const showForm = ref(false)
const lastSync = ref<AdSyncResult | null>(null)

const form = reactive({
  ldaps_url: '', base_dn: '', bind_account: '', bind_password: '',
  allowed_group: '', id_attribute: 'sAMAccountName', sync_interval: '1h',
})

async function load() {
  error.value = null
  try {
    conn.value = await adApi.connection()
    Object.assign(form, {
      ldaps_url: conn.value.ldaps_url ?? '', base_dn: conn.value.base_dn ?? '',
      bind_account: conn.value.bind_account ?? '', bind_password: '',
      allowed_group: conn.value.allowed_group ?? '',
      id_attribute: conn.value.id_attribute ?? 'sAMAccountName',
      sync_interval: conn.value.sync_interval ?? '1h',
    })
  } catch (e) {
    error.value = e
  }
}
onMounted(load)

async function save() {
  busy.value = true
  error.value = null
  try {
    // 비밀번호는 입력했을 때만 보낸다 — 빈 값으로 덮어쓰면 안 된다.
    const payload: Record<string, unknown> = { ...form, allowed_group: form.allowed_group || null }
    if (!form.bind_password) delete payload.bind_password
    conn.value = (await adApi.updateConnection(payload)) as AdConnection
    showForm.value = false
    notice.value = 'AD 연결 설정을 저장했습니다.'
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}

async function test() {
  busy.value = true; error.value = null; notice.value = ''
  try {
    const res = await adApi.test()
    notice.value = res.ok ? 'AD 연결 성공 (bind OK)' : 'AD 연결 실패'
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}

async function sync() {
  busy.value = true; error.value = null; notice.value = ''
  try {
    lastSync.value = await adApi.sync()
    await load()
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
  <PageHead
    title="AD 연결"
    :crumbs="['HPC Portal Admin', '사용자 / 정책', 'AD 연결']"
    sub="단일 Active Directory 연동 · 인증은 AD, 역할은 포털"
  >
    <template #actions>
      <RouterLink to="/admin/users"><Btn>👥 사용자 목록</Btn></RouterLink>
      <Btn :disabled="busy" @click="test">🔌 연결 테스트</Btn>
      <Btn variant="primary" :disabled="busy" @click="sync">↻ 지금 동기화</Btn>
    </template>
  </PageHead>

  <ErrorNote :error="error" />
  <div v-if="notice" class="px-3.5 py-2.5 rounded-lg bg-ok-bg text-ok text-[13px] mb-4">{{ notice }}</div>

  <div class="grid lg:grid-cols-2 gap-5 items-start">
    <Card title="현재 AD 연결">
      <template #title-extra><Fid id="A-US-01" /></template>
      <dl v-if="conn" class="grid grid-cols-[130px_1fr] gap-y-2.5 text-[13.5px]">
        <dt class="text-ink-3">LDAP URL</dt><dd class="mono">{{ conn.ldaps_url ?? '—' }}</dd>
        <dt class="text-ink-3">Base DN</dt><dd class="mono">{{ conn.base_dn ?? '—' }}</dd>
        <dt class="text-ink-3">Bind 계정</dt><dd class="mono">{{ conn.bind_account ?? '—' }}</dd>
        <dt class="text-ink-3">Bind 암호</dt>
        <dd>
          <Chip :tone="conn.bind_secret_configured ? 'brand' : 'gray'">
            {{ conn.bind_secret_configured ? '••••• Secret 저장소' : '미설정' }}
          </Chip>
        </dd>
        <dt class="text-ink-3">허용 그룹</dt>
        <dd class="mono">
          {{ conn.allowed_group ?? '—' }}
          <span v-if="!conn.allowed_group" class="text-warn text-[12px] block mt-0.5">
            미설정 — 전 AD 사용자가 포털 사용자가 됩니다
          </span>
        </dd>
        <dt class="text-ink-3">식별 속성</dt><dd class="mono">{{ conn.id_attribute ?? '—' }}</dd>
        <dt class="text-ink-3">부트스트랩</dt>
        <dd><Chip :tone="conn.bootstrap_completed ? 'brand' : 'gray'">
          {{ conn.bootstrap_completed ? '완료 (seed ADMIN 지정됨)' : '미완료' }}
        </Chip></dd>
      </dl>
      <template #foot>
        <div class="flex justify-between items-center">
          <span>Bind 암호는 Secret 저장소에만 보관되며 화면에 다시 표시되지 않습니다.</span>
          <Btn size="sm" @click="showForm = true">수정</Btn>
        </div>
      </template>
    </Card>

    <Card title="동기화 상태">
      <dl class="grid grid-cols-[130px_1fr] gap-y-2.5 text-[13.5px] mb-4">
        <dt class="text-ink-3">주기</dt><dd class="mono">{{ conn?.sync_interval ?? '—' }}</dd>
        <dt class="text-ink-3">최근 실행</dt>
        <dd class="mono">{{ conn?.last_sync_at?.slice(0, 19).replace('T', ' ') ?? '—' }}</dd>
        <dt class="text-ink-3">최근 결과</dt><dd>{{ conn?.last_sync_result ?? '—' }}</dd>
      </dl>

      <div v-if="lastSync" class="p-3.5 rounded-lg bg-bg text-[13px]">
        <b class="block mb-1.5">방금 실행한 동기화</b>
        <div class="grid grid-cols-3 gap-2 text-center">
          <div><span class="block text-lg font-bold text-ok mono">{{ lastSync.created }}</span>신규</div>
          <div><span class="block text-lg font-bold text-info mono">{{ lastSync.updated }}</span>갱신</div>
          <div><span class="block text-lg font-bold text-warn mono">{{ lastSync.deactivated }}</span>비활성</div>
        </div>
      </div>

      <template #foot>
        AD 조회가 <b>실패하면 아무도 비활성화하지 않습니다</b> — 네트워크 장애를 퇴사로 오인하지
        않기 위해서입니다. AD에서 사라진 사용자는 soft delete로 이력을 보존합니다.
      </template>
    </Card>
  </div>

  <Modal v-if="showForm" title="AD 연결 설정" wide @close="showForm = false">
    <template #title-extra><Fid id="A-US-01" /></template>
    <div class="grid sm:grid-cols-2 gap-4">
      <Field label="LDAP(S) URL" required full hint="인증서가 있으면 ldaps:// 권장 — 평문은 비밀번호가 노출됩니다">
        <input v-model="form.ldaps_url" :class="[inputClass, 'mono']" />
      </Field>
      <Field label="Base DN" required><input v-model="form.base_dn" :class="[inputClass, 'mono']" /></Field>
      <Field label="Bind 계정" required><input v-model="form.bind_account" :class="[inputClass, 'mono']" /></Field>
      <Field label="Bind 암호" full hint="비워 두면 기존 값을 유지합니다">
        <input v-model="form.bind_password" type="password" :class="inputClass" placeholder="재입력 시에만 변경" />
      </Field>
      <Field label="허용 그룹" full hint="비우면 전 AD 사용자 허용">
        <input v-model="form.allowed_group" :class="[inputClass, 'mono']" placeholder="cn=HPC-Users,dc=corp,dc=com" />
      </Field>
      <Field label="식별 속성">
        <select v-model="form.id_attribute" :class="inputClass"><option>sAMAccountName</option><option>uid</option></select>
      </Field>
      <Field label="동기화 주기"><input v-model="form.sync_interval" :class="[inputClass, 'mono']" /></Field>
    </div>
    <template #foot>
      <Btn @click="showForm = false">취소</Btn>
      <Btn variant="primary" :disabled="busy" @click="save">저장</Btn>
    </template>
  </Modal>
</template>
