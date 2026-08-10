<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { clusterApi, type AppAccess, type SlurmAccount, type SlurmQos } from '@/api/clusters'
import { useClusterStore } from '@/stores/cluster'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'
import { inputClass } from '@/utils/form'

/** SCR-13 계정 — slurmdbd의 account와 association(사용자 연결)을 보여준다 (A-US-02). */
const clusters = useClusterStore()
const accounts = ref<SlurmAccount[]>([])
const loading = ref(false)
const error = ref<unknown>(null)

/** QOS 목록은 편집 선택지로 쓴다 — 없는 QOS를 지정하면 Slurm이 거부한다. */
const qosCatalog = ref<SlurmQos[]>([])
/**
 * 앱별 허용 계정. 카탈로그 전체가 오고, `accounts`가 빈 앱은 **전원 허용**이다.
 * 계정 관리 화면에 두는 이유는 배정 대상이 계정이기 때문이다(A-US-02).
 */
const appAccess = ref<AppAccess[]>([])
/** 편집 중인 대상: 'account:<name>' · 'user:<account>/<user>' · 'app:<kind>/<id>' */
const editing = ref<string | null>(null)
const draft = ref<string[]>([])

async function load() {
  const cid = clusters.selectedId
  if (!cid) return
  loading.value = true
  error.value = null
  try {
    const [list, qos, apps] = await Promise.all([
      clusterApi.accounts(cid),
      clusterApi.qos(cid),
      clusterApi.appAccess(cid),
    ])
    accounts.value = list
    qosCatalog.value = qos
    appAccess.value = apps
    editing.value = null
  } catch (e) {
    error.value = e
    accounts.value = []
  } finally {
    loading.value = false
  }
}
watch(() => clusters.selectedId, load, { immediate: true })

const totalUsers = computed(() => accounts.value.reduce((sum, a) => sum + a.users.length, 0))

const form = ref({ name: '', description: '', organization: '' })
const link = ref({ account: '', username: '' })
const busy = ref(false)

async function run(action: () => Promise<unknown>) {
  busy.value = true
  error.value = null
  try {
    await action()
    await load()
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}

function createAccount() {
  const cid = clusters.selectedId
  if (!cid || !form.value.name) return
  run(async () => {
    await clusterApi.createAccount(cid, { ...form.value })
    form.value = { name: '', description: '', organization: '' }
  })
}

function removeAccount(name: string) {
  const cid = clusters.selectedId
  if (!cid) return
  // 계정을 지우면 그 계정에 달린 연결과 accounting 소속이 함께 사라진다.
  if (!confirm(`계정 '${name}'을(를) 삭제할까요? 소속 사용자 연결도 함께 삭제됩니다.`)) return
  run(() => clusterApi.deleteAccount(cid, name))
}

function addUser() {
  const cid = clusters.selectedId
  if (!cid || !link.value.account || !link.value.username) return
  run(async () => {
    await clusterApi.addAccountUser(cid, link.value.account, link.value.username)
    link.value = { account: link.value.account, username: '' }
  })
}

function removeUser(account: string, username: string) {
  const cid = clusters.selectedId
  if (!cid || !confirm(`'${username}'을(를) 계정 '${account}'에서 해제할까요?`)) return
  run(() => clusterApi.removeAccountUser(cid, account, username))
}

function startEdit(key: string, current: string[]) {
  editing.value = key
  draft.value = [...current]
}

function toggle(name: string) {
  draft.value = draft.value.includes(name)
    ? draft.value.filter((q) => q !== name)
    : [...draft.value, name]
}

function saveAppAccess(app: AppAccess) {
  const cid = clusters.selectedId
  if (!cid) return
  // QOS와 같은 규칙 — 덮어쓰기라 현재 선택 전체를 보낸다.
  run(() => clusterApi.setAppAccess(cid, app.kind, app.app_id, draft.value))
}

function saveQos(account: string, username: string | null) {
  const cid = clusters.selectedId
  if (!cid) return
  // 덮어쓰기라 현재 선택 전체를 보낸다.
  run(() =>
    username
      ? clusterApi.setUserQos(cid, account, username, draft.value)
      : clusterApi.setAccountQos(cid, account, draft.value),
  )
}

</script>

<template>
  <PageHead
    title="계정 (Account)"
    :crumbs="['HPC Portal Admin', '사용자 / 정책']"
    :sub="`Slurm 계정과 사용자 매핑 · ${clusters.selectedName}`"
  >
    <template #actions><Btn @click="load">↻ 새로고침</Btn></template>
  </PageHead>

  <ErrorNote :error="error" />
  <div v-if="loading" class="py-12 text-center text-ink-3">불러오는 중…</div>

  <div v-else class="space-y-5">
    <Card title="계정 목록" flush>
      <template #title-extra><Fid id="A-US-02" /></template>
      <template #head>
        <Chip tone="gray">계정 {{ accounts.length }} · 연결 {{ totalUsers }}</Chip>
      </template>
      <form class="px-4 py-3 border-b border-line flex flex-wrap gap-2 items-end" @submit.prevent="createAccount">
        <label class="flex-1 min-w-[160px] text-[13px] text-ink-3">
          계정명*
          <input v-model="form.name" required pattern="[A-Za-z0-9._-]+" :class="[inputClass, 'mono mt-1']" placeholder="hpc-team" />
        </label>
        <label class="flex-1 min-w-[160px] text-[13px] text-ink-3">
          조직
          <input v-model="form.organization" :class="[inputClass, 'mt-1']" placeholder="dt-hpc" />
        </label>
        <label class="flex-[2] min-w-[200px] text-[13px] text-ink-3">
          설명
          <input v-model="form.description" :class="[inputClass, 'mt-1']" />
        </label>
        <Btn type="submit" variant="primary" :disabled="busy">계정 추가</Btn>
      </form>
      <Empty v-if="!accounts.length" text="등록된 계정이 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'name', label: '계정', width: '180px' },
          { key: 'org', label: '조직' },
          { key: 'desc', label: '설명' },
          { key: 'qos', label: '계정 QOS', width: '280px' },
          { key: 'users', label: '소속 사용자', num: true, width: '110px' },
          { key: 'act', label: '', width: '90px' },
        ]"
      >
        <tr v-for="a in accounts" :key="a.name" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5 mono font-semibold">{{ a.name }}</td>
          <td class="px-3.5 py-2.5">{{ a.organization || '—' }}</td>
          <td class="px-3.5 py-2.5 text-ink-3">{{ a.description || '—' }}</td>
          <td class="px-3.5 py-2.5">
            <div v-if="editing === `account:${a.name}`" class="flex flex-wrap items-center gap-1">
              <Chip
                v-for="q in qosCatalog"
                :key="q.name"
                :tone="draft.includes(q.name) ? 'brand' : 'gray'"
                class="cursor-pointer"
                @click="toggle(q.name)"
              >{{ q.name }}</Chip>
              <Btn size="sm" variant="primary" :disabled="busy" @click="saveQos(a.name, null)">저장</Btn>
              <Btn size="sm" :disabled="busy" @click="editing = null">취소</Btn>
            </div>
            <div v-else class="flex flex-wrap items-center gap-1">
              <Chip v-for="q in a.qos" :key="q" tone="brand">{{ q }}</Chip>
              <span v-if="!a.qos.length" class="text-ink-3">—</span>
              <Btn size="sm" @click="startEdit(`account:${a.name}`, a.qos)">편집</Btn>
            </div>
          </td>
          <td class="px-3.5 py-2.5 mono text-right">{{ a.users.length }}</td>
          <td class="px-3.5 py-2.5">
            <!-- root는 Slurm이 만드는 최상위 계정이라 삭제할 수 없다 -->
            <Btn
              v-if="a.name !== 'root'"
              size="sm"
              variant="danger"
              :disabled="busy"
              @click="removeAccount(a.name)"
            >삭제</Btn>
            <span v-else class="text-ink-3 text-[13px]">기본</span>
          </td>
        </tr>
      </Table>
    </Card>

    <!--
      앱 사용 허용. 배정 대상이 계정이라 계정 화면에 둔다.
      **기본은 열려 있다** — 배정하지 않은 앱은 지금까지처럼 전원이 쓴다.
    -->
    <Card title="앱 사용 허용" flush>
      <template #title-extra><Fid id="A-US-02" /></template>
      <Empty v-if="!appAccess.length" text="앱 카탈로그를 불러오지 못했습니다." />
      <Table
        v-else
        :columns="[
          { key: 'app', label: '앱', width: '220px' },
          { key: 'kind', label: '종류', width: '120px' },
          { key: 'accounts', label: '허용 계정' },
        ]"
      >
        <tr v-for="a in appAccess" :key="`${a.kind}/${a.app_id}`" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5">
            <b>{{ a.name }}</b>
            <span class="ml-1.5 mono text-[12.5px] text-ink-3">{{ a.app_id }}</span>
          </td>
          <td class="px-3.5 py-2.5 text-[13.5px] text-ink-2">
            {{ a.kind === 'interactive' ? '인터랙티브' : 'Batch' }}
          </td>
          <td class="px-3.5 py-2.5">
            <div v-if="editing === `app:${a.kind}/${a.app_id}`" class="flex flex-wrap items-center gap-1">
              <Chip
                v-for="acc in accounts"
                :key="acc.name"
                :tone="draft.includes(acc.name) ? 'brand' : 'gray'"
                class="cursor-pointer"
                @click="toggle(acc.name)"
              >{{ acc.name }}</Chip>
              <Btn size="sm" variant="primary" :disabled="busy" @click="saveAppAccess(a)">저장</Btn>
              <Btn size="sm" :disabled="busy" @click="editing = null">취소</Btn>
            </div>
            <div v-else class="flex flex-wrap items-center gap-1">
              <Chip v-for="acc in a.accounts" :key="acc" tone="brand">{{ acc }}</Chip>
              <!-- 빈 값을 '—'로 두면 "아무도 못 쓴다"로 읽힌다. 반대이므로 말로 적는다. -->
              <span v-if="!a.accounts.length" class="text-[13px] text-ink-3">전원 허용</span>
              <Btn size="sm" @click="startEdit(`app:${a.kind}/${a.app_id}`, a.accounts)">편집</Btn>
            </div>
          </td>
        </tr>
      </Table>
      <template #foot>
        계정을 하나도 고르지 않으면 그 앱은 <b>전원이 사용</b>합니다. 배정된 앱은
        그 계정에 연결된 사용자에게만 보이고, 제출된 Job도 <b>그 계정으로</b> 실행됩니다.
        웹 터미널·SSH에서 직접 <span class="mono">sbatch</span>를 실행하는 것은 막지 않습니다 —
        그 경계는 Slurm의 파티션 <span class="mono">AllowAccounts</span>가 맡습니다.
      </template>
    </Card>

    <!-- 사용자↔계정 연결은 association이 정본이다. 계정 응답의 associations는 비어 온다(실측). -->
    <Card title="사용자 매핑 (association)" flush>
      <template #title-extra><Fid id="A-US-02" /></template>
      <form class="px-4 py-3 border-b border-line flex flex-wrap gap-2 items-end" @submit.prevent="addUser">
        <label class="flex-1 min-w-[160px] text-[13px] text-ink-3">
          계정
          <select v-model="link.account" :class="[inputClass, 'mono mt-1']">
            <option value="">선택</option>
            <option v-for="a in accounts" :key="a.name" :value="a.name">{{ a.name }}</option>
          </select>
        </label>
        <label class="flex-1 min-w-[160px] text-[13px] text-ink-3">
          사용자
          <input v-model="link.username" :class="[inputClass, 'mono mt-1']" placeholder="jungryul0515.park" />
        </label>
        <Btn type="submit" variant="primary" :disabled="busy">연결 추가</Btn>
      </form>
      <Empty v-if="!totalUsers" text="계정에 연결된 사용자가 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'user', label: '사용자' },
          { key: 'account', label: '계정' },
          { key: 'partition', label: '파티션' },
          { key: 'qos', label: 'QOS' },
          { key: 'default', label: '기본' },
          { key: 'shares', label: 'Shares', num: true },
          { key: 'act', label: '', width: '90px' },
        ]"
      >
        <template v-for="a in accounts" :key="a.name">
          <tr
            v-for="u in a.users"
            :key="`${a.name}/${u.user}`"
            class="border-b border-line last:border-0"
          >
            <td class="px-3.5 py-2.5 mono font-semibold">{{ u.user }}</td>
            <td class="px-3.5 py-2.5 mono">{{ a.name }}</td>
            <td class="px-3.5 py-2.5 mono text-[13px]">{{ u.partition || '전체' }}</td>
            <td class="px-3.5 py-2.5">
              <div v-if="editing === `user:${a.name}/${u.user}`" class="flex flex-wrap items-center gap-1">
                <Chip
                  v-for="q in qosCatalog"
                  :key="q.name"
                  :tone="draft.includes(q.name) ? 'brand' : 'gray'"
                  class="cursor-pointer"
                  @click="toggle(q.name)"
                >{{ q.name }}</Chip>
                <Btn size="sm" variant="primary" :disabled="busy" @click="saveQos(a.name, u.user)">저장</Btn>
                <Btn size="sm" :disabled="busy" @click="editing = null">취소</Btn>
              </div>
              <div v-else class="flex flex-wrap items-center gap-1">
                <Chip v-for="q in u.qos" :key="q" tone="brand">{{ q }}</Chip>
                <span v-if="!u.qos.length" class="text-ink-3">—</span>
                <Btn size="sm" @click="startEdit(`user:${a.name}/${u.user}`, u.qos)">편집</Btn>
              </div>
            </td>
            <td class="px-3.5 py-2.5">
              <Badge v-if="u.is_default" state="idle">기본</Badge>
              <span v-else class="text-ink-3">—</span>
            </td>
            <td class="px-3.5 py-2.5 mono text-right">{{ u.shares_raw ?? '—' }}</td>
            <td class="px-3.5 py-2.5">
              <Btn size="sm" variant="danger" :disabled="busy" @click="removeUser(a.name, u.user)">
                해제
              </Btn>
            </td>
          </tr>
        </template>
      </Table>
      <template #foot>
        계정·연결 변경은 <b>감사 로그에 기록</b>됩니다. 클러스터의
        <span class="mono">sacctmgr</span>와 같은 대상을 다룹니다.
      </template>
    </Card>
  </div>
</template>
