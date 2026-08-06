<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { clusterApi } from '@/api/clusters'
import { useClusterStore } from '@/stores/cluster'
import type { Cluster, ClusterCreate } from '@/types/api'
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

const store = useClusterStore()
const rows = ref<Cluster[]>([])
const loading = ref(false)
const error = ref<unknown>(null)
const notice = ref('')

const showForm = ref(false)
const editing = ref<Cluster | null>(null)
const form = reactive<ClusterCreate>({
  name: '', description: '', slurmrestd_url: '', api_version: 'v0.0.41',
  auth_method: 'jwt', login_node: '', ssh_port: 22, ssh_account: 'svc-portal',
  group_path_tpl: '/group/{group}', scratch_path_tpl: '/scratch/{user}',
  desktop_image_ref: '', is_default: false,
})

const credTarget = ref<Cluster | null>(null)
const cred = reactive({ kind: 'SLURM_JWT' as 'SLURM_JWT' | 'SSH_KEY', value: '' })

// 신규 등록 폼에서만 쓰는 자격증명 입력값. 저장 직후 자격증명 API로 넘기고 비운다.
const newJwt = ref('')
const newSshKey = ref('')

async function load() {
  loading.value = true
  error.value = null
  try {
    const summaries = await clusterApi.list(true)
    // 목록 API는 요약만 준다 — 관리 화면은 상세가 필요하다.
    rows.value = await Promise.all(summaries.map((s) => clusterApi.get(s.id)))
  } catch (e) {
    error.value = e
  } finally {
    loading.value = false
  }
}
onMounted(load)

function openCreate() {
  editing.value = null
  Object.assign(form, {
    name: '', description: '', slurmrestd_url: '', api_version: 'v0.0.41',
    auth_method: 'jwt', login_node: '', ssh_port: 22, ssh_account: 'svc-portal',
    group_path_tpl: '/group/{group}', scratch_path_tpl: '/scratch/{user}',
  desktop_image_ref: '', is_default: false,
  })
  resetFormNotes()
  showForm.value = true
}

function resetFormNotes() {
  newJwt.value = ''
  newSshKey.value = ''
}

function openEdit(c: Cluster) {
  editing.value = c
  Object.assign(form, {
    name: c.name, description: c.description ?? '', slurmrestd_url: c.slurmrestd_url ?? '',
    api_version: c.api_version ?? 'v0.0.41', auth_method: c.auth_method ?? 'jwt',
    login_node: c.login_node ?? '', ssh_port: c.ssh_port ?? 22, ssh_account: c.ssh_account ?? '',
    group_path_tpl: c.group_path_tpl ?? '', scratch_path_tpl: c.scratch_path_tpl ?? '',
    desktop_image_ref: c.desktop_image_ref ?? '',
    is_default: c.is_default,
  })
  resetFormNotes()
  showForm.value = true
}

async function save() {
  error.value = null
  notice.value = ''
  try {
    if (editing.value) {
      const { name: _ignored, ...patch } = form
      await clusterApi.update(editing.value.id, patch)
      showForm.value = false
      await load()
      await store.load()
      return
    }
    await createCluster()
  } catch (e) {
    error.value = e
  }
}

/**
 * 등록은 id 발급 → 자격증명 저장 → 연결 확인 순서로 이어진다.
 * REST 테스트가 Secret 저장소의 자격증명을 꺼내 쓰므로 "인증 먼저"는 성립하지 않는다.
 */
async function createCluster() {
  const jwt = newJwt.value.trim()
  const sshKey = newSshKey.value.trim()
  const created = await clusterApi.create(form)
  showForm.value = false
  resetFormNotes()

  let jwtSaved = false
  const failed: string[] = []
  for (const [kind, value] of [['SLURM_JWT', jwt], ['SSH_KEY', sshKey]] as const) {
    if (!value) continue
    try {
      await clusterApi.putCredential(created.id, kind, value)
      if (kind === 'SLURM_JWT') jwtSaved = true
    } catch (e) {
      // 클러스터 행은 이미 남았다 — 무엇이 끝났고 무엇이 남았는지 분명히 알린다.
      error.value = e
      failed.push(kind)
    }
  }
  if (failed.length) {
    notice.value =
      `${created.name}: 클러스터는 등록됐지만 ${failed.join('·')} 저장에 실패했습니다 — [수정]에서 다시 등록하세요.`
  }

  await load()
  await store.load()
  // JWT까지 들어갔으면 바로 연결을 확인해 이름을 slurm.conf ClusterName으로 정정한다(A-CL-02).
  if (jwtSaved) await testRest(created)
}

async function testRest(c: Cluster) {
  notice.value = ''
  error.value = null
  try {
    const res = await clusterApi.testRest(c.id)
    // 이름은 손 입력이 아니라 slurmrestd가 알려준 값이 정본이다(A-CL-02).
    notice.value = `${c.name}: 연결 성공 — ClusterName=${res.cluster_name}, API=${res.api_version}`
    await load()
  } catch (e) {
    error.value = e
  }
}

/** 완전 삭제 — 비활성 상태이고 참조 이력이 없을 때만 서버가 허용한다. */
async function purge(c: Cluster) {
  if (!confirm(`${c.name} 을(를) 완전히 삭제할까요?\n등록 정보와 자격증명이 되돌릴 수 없이 사라집니다.`)) return
  error.value = null
  notice.value = ''
  try {
    await clusterApi.purge(c.id)
    notice.value = `${c.name}: 삭제했습니다.`
    await load()
    await store.load()
  } catch (e) {
    error.value = e
  }
}

async function remove(c: Cluster) {
  if (!confirm(`${c.name} 을(를) 비활성화할까요? (행은 남습니다)`)) return
  try {
    await clusterApi.remove(c.id)
    await load()
    await store.load()
  } catch (e) {
    error.value = e
  }
}

// 등록/수정 폼에서 바로 자격증명 모달을 연다. 저장 전에는 cluster id가 없어 등록할 수 없다.
function openCred(kind: 'SLURM_JWT' | 'SSH_KEY') {
  if (!editing.value) return
  cred.kind = kind
  cred.value = ''
  credTarget.value = editing.value
}

async function saveCredential() {
  if (!credTarget.value) return
  error.value = null
  try {
    await clusterApi.putCredential(credTarget.value.id, cred.kind, cred.value)
    notice.value = `${credTarget.value.name}: ${cred.kind} 등록 완료 (값은 Secret 저장소에만 보관)`
    const cid = credTarget.value.id
    credTarget.value = null
    cred.value = ''
    await load()
    // 폼이 열린 채라면 구역 헤더의 자격증명 현황도 새 값으로 바꿔 준다.
    if (editing.value?.id === cid) editing.value = rows.value.find((r) => r.id === cid) ?? editing.value
  } catch (e) {
    error.value = e
  }
}

const inputClass =
  'w-full px-3 py-2 rounded-lg border border-line-dark text-[14.5px] outline-none focus:border-brand-500'

const sectionClass =
  'sm:col-span-2 mt-2 pt-4 border-t border-line flex items-center gap-3 text-[13px] font-bold text-ink-3'

/** "5분 전" 형태의 상대 시각 — 마지막 헬스체크가 언제였는지가 핵심이라 절대시각보다 읽기 쉽다. */
function ago(iso?: string | null): string {
  if (!iso) return ''
  const mins = Math.floor((Date.now() - new Date(iso).getTime()) / 60000)
  if (mins < 1) return '방금'
  if (mins < 60) return `${mins}분 전`
  if (mins < 1440) return `${Math.floor(mins / 60)}시간 전`
  return `${Math.floor(mins / 1440)}일 전`
}

/**
 * 상태 배지는 등록 상태(활성/비활성)가 아니라 **연결 상태**를 말한다.
 * 비활성이 우선 — 꺼 둔 클러스터의 헬스는 의미가 없다.
 */
function healthState(c: Cluster): string {
  if (!c.is_active) return 'cancelled'
  if (c.last_health_ok === true) return 'ok'
  if (c.last_health_ok === false) return 'failed'
  return 'pending'
}
function healthLabel(c: Cluster): string {
  if (!c.is_active) return '비활성'
  if (c.last_health_ok === true) return '정상'
  if (c.last_health_ok === false) return '연결 실패'
  return '미확인'
}

/** 폼 구역 헤더에 띄우는 자격증명 현황 — 값이 아니라 등록 여부·만료만 보여준다. */
function credentialStatus(kind: 'SLURM_JWT' | 'SSH_KEY'): string {
  const found = (editing.value?.credentials ?? []).filter((c) => c.kind === kind).at(-1)
  if (!found) return '미등록'
  if (!found.expires_at) return `등록됨 · ${ago(found.created_at)}`
  const expired = new Date(found.expires_at).getTime() < Date.now()
  const day = found.expires_at.slice(0, 10)
  return expired ? `만료됨 (${day})` : `${day} 만료`
}
</script>

<template>
  <PageHead
    title="클러스터 관리"
    :crumbs="['HPC Portal Admin', '자원 관리', '클러스터']"
    sub="Slurm 클러스터 등록 · 연결 상태 · 자격증명 (클러스터별 독립 slurmdbd)"
  >
    <template #actions>
      <Btn @click="load">↻ 새로고침</Btn>
      <Btn variant="primary" @click="openCreate">＋ 클러스터 등록</Btn>
    </template>
  </PageHead>

  <ErrorNote :error="error" />
  <div v-if="notice" class="px-3.5 py-2.5 rounded-lg bg-ok-bg text-ok text-[14px] mb-4">{{ notice }}</div>

  <Card flush>
    <template #head><Fid id="A-CL-01" /></template>
    <div v-if="loading" class="py-12 text-center text-ink-3">불러오는 중…</div>
    <Empty v-else-if="!rows.length" text="등록된 클러스터가 없습니다." />
    <Table
      v-else
      :columns="[
        { key: 'n', label: '클러스터' },
        { key: 'e', label: 'slurmrestd 엔드포인트' },
        { key: 'v', label: 'API' , width: '90px' },
        { key: 'l', label: '로그인 노드' },
        { key: 's', label: '상태', width: '90px' },
        { key: 'a', label: '액션', width: '150px' },
      ]"
    >
      <tr v-for="c in rows" :key="c.id" class="border-b border-line last:border-0 hover:bg-bg">
        <td class="px-3.5 py-2.5">
          <b class="mono">{{ c.name }}</b>
          <Chip v-if="c.is_default" tone="brand" class="ml-1.5">기본</Chip>
          <p class="text-[13px] text-ink-3">{{ c.description }}</p>
        </td>
        <td class="px-3.5 py-2.5 mono text-[13.5px]">{{ c.slurmrestd_url ?? '—' }}</td>
        <td class="px-3.5 py-2.5 mono">{{ c.api_version ?? '—' }}</td>
        <td class="px-3.5 py-2.5 mono text-[13.5px]">{{ c.login_node ?? '—' }}</td>
        <!-- 상태 = "지금 살아 있나" — 마지막 헬스체크와 재확인 수단을 같은 자리에 둔다(A-CL-01) -->
        <td class="px-3.5 py-2.5">
          <Badge :state="healthState(c)">{{ healthLabel(c) }}</Badge>
          <p class="mt-1 text-[12.5px] text-ink-3">
            <template v-if="c.last_health_at">{{ ago(c.last_health_at) }} 확인 · </template>
            <button class="text-brand-700 hover:underline" @click="testRest(c)">테스트</button>
          </p>
        </td>
        <td class="px-3.5 py-2.5">
          <div class="flex gap-1.5">
            <Btn size="sm" @click="openEdit(c)">수정</Btn>
            <!-- 삭제는 비활성 이후에만 — 참조 이력이 있으면 서버가 거부한다 -->
            <Btn v-if="c.is_active" size="sm" variant="danger" @click="remove(c)">비활성</Btn>
            <Btn v-else size="sm" variant="danger" @click="purge(c)">삭제</Btn>
          </div>
        </td>
      </tr>
    </Table>
    <template #foot>
      운영 중 제거는 <b>비활성화</b>로 처리됩니다 — 감사 로그의 FK를 살려 두기 위해서입니다.
      비활성 클러스터는 <b>삭제</b>할 수 있지만, 감사 로그·세션·공지가 참조 중이면 거부됩니다.
      자격증명(JWT·SSH 키)은 Secret 저장소에만 보관되고 DB에는 참조만 남습니다.
      <Fid id="A-CL-02" /> <Fid id="A-CL-03" />
    </template>
  </Card>

  <Modal v-if="showForm" :title="editing ? '클러스터 수정' : '클러스터 등록'" wide @close="showForm = false">
    <template #title-extra><Fid id="A-CL-02" /></template>
    <div class="grid sm:grid-cols-2 gap-4">
      <Field
        label="클러스터 이름" required
        :hint="editing ? '이름은 수정할 수 없습니다' : 'REST 연결 테스트 시 slurm.conf ClusterName으로 자동 정정됩니다'"
      >
        <input v-model="form.name" :disabled="!!editing" :class="[inputClass, 'mono', editing ? 'bg-bg' : '']" />
      </Field>
      <Field label="설명"><input v-model="form.description" :class="inputClass" /></Field>

      <!-- REST 제어 계열과 SSH 계열은 연동 대상이 다르므로 구분선으로 나눈다 -->
      <div :class="sectionClass">
        <span class="flex-1">slurmrestd 연동</span>
        <!-- 연결 확인은 목록의 상태 컬럼이 맡는다. 여기 남는 건 설정 변경뿐이다. -->
        <template v-if="editing">
          <span class="font-normal normal-case">JWT {{ credentialStatus('SLURM_JWT') }}</span>
          <Btn size="sm" @click="openCred('SLURM_JWT')">교체</Btn>
        </template>
      </div>
      <Field label="slurmrestd URL" full required hint="포털 백엔드만 접근 — 네트워크 직접 노출 금지">
        <input v-model="form.slurmrestd_url" :class="[inputClass, 'mono']" placeholder="http://slurmrestd:6820" />
      </Field>
      <Field label="API 버전"><input v-model="form.api_version" :class="[inputClass, 'mono']" /></Field>
      <Field label="인증 방식">
        <select v-model="form.auth_method" :class="inputClass"><option>jwt</option><option>munge</option></select>
      </Field>
      <Field
        v-if="!editing" label="SLURM JWT" full
        hint="scontrol token 으로 발급한 JWT — 저장 시 Secret 저장소로 들어가고 화면에 다시 표시되지 않습니다. 비워 두면 나중에 등록할 수 있습니다."
      >
        <textarea v-model="newJwt" rows="3" :class="[inputClass, 'mono resize-y']" placeholder="eyJhbGciOi…" />
      </Field>

      <div :class="sectionClass">
        <span class="flex-1">로그인 노드 · 파일시스템</span>
        <template v-if="editing">
          <span class="font-normal normal-case">SSH 개인키 {{ credentialStatus('SSH_KEY') }}</span>
          <Btn size="sm" @click="openCred('SSH_KEY')">교체</Btn>
        </template>
      </div>
      <Field label="로그인 노드" hint="웹 터미널·SFTP 공용">
        <input v-model="form.login_node" :class="[inputClass, 'mono']" />
      </Field>
      <Field label="SSH 포트"><input v-model.number="form.ssh_port" type="number" :class="[inputClass, 'mono']" /></Field>
      <Field label="SSH 서비스 계정" hint="전체 root sudo 지양 · 제한적 sudo 권장">
        <input v-model="form.ssh_account" :class="[inputClass, 'mono']" />
      </Field>
      <Field
        v-if="!editing" label="SSH 개인키" full
        hint="OpenSSH 개인키 전문 — 저장 시 Secret 저장소로 들어가고 화면에 다시 표시되지 않습니다. 비워 두면 나중에 등록할 수 있습니다."
      >
        <textarea
          v-model="newSshKey" rows="4" :class="[inputClass, 'mono resize-y']"
          placeholder="-----BEGIN OPENSSH PRIVATE KEY-----"
        />
      </Field>
      <Field label="그룹 경로 템플릿" hint="{group} 세션 치환">
        <input v-model="form.group_path_tpl" :class="[inputClass, 'mono']" />
      </Field>
      <Field label="스크래치 경로 템플릿" full hint="{user} 세션 치환 · 홈은 SSSD/NSS로 자동 인식">
        <input v-model="form.scratch_path_tpl" :class="[inputClass, 'mono']" />
      </Field>
      <Field
        label="데스크톱 이미지 (U-IA-02)" full
        hint="SIF 경로 / oras:// / docker:// — 이 값만 바꾸면 레지스트리로 전환된다"
      >
        <input
          v-model="form.desktop_image_ref" :class="[inputClass, 'mono']"
          placeholder="/home/portal/images/rocky9-mate-1.0.sif"
        />
      </Field>
      <p v-if="!editing" class="sm:col-span-2 text-[13.5px] text-ink-3">
        저장하면 <b>클러스터 등록 → 자격증명 저장 → REST 연결 확인</b>이 이어서 실행됩니다.
        자격증명 값은 Secret 저장소에만 보관되고 DB·응답·감사 로그 어디에도 남지 않습니다.
      </p>
      <label class="sm:col-span-2 flex items-center gap-2 text-[14.5px] text-ink-2">
        <input v-model="form.is_default" type="checkbox" class="w-4 h-4 accent-brand-700" />
        기본 클러스터로 지정
      </label>
    </div>
    <template #foot>
      <Btn @click="showForm = false">취소</Btn>
      <Btn variant="primary" @click="save">저장</Btn>
    </template>
  </Modal>

  <Modal v-if="credTarget" :title="`자격증명 등록 — ${credTarget.name}`" @close="credTarget = null">
    <div class="px-3.5 py-2.5 rounded-lg bg-warn-bg text-warn text-[14px] mb-4">
      값은 <b>Secret 저장소에만</b> 저장되고 DB·응답·감사 로그 어디에도 남지 않습니다.
      화면에 다시 표시되지 않습니다.
    </div>
    <div class="space-y-4">
      <Field label="종류">
        <select v-model="cred.kind" :class="inputClass">
          <option value="SLURM_JWT">SLURM_JWT — slurmrestd 호출용</option>
          <option value="SSH_KEY">SSH_KEY — 로그인 노드 접속용</option>
        </select>
      </Field>
      <Field label="값" required :hint="cred.kind === 'SLURM_JWT' ? 'scontrol token 으로 발급한 JWT' : 'OpenSSH 개인키 전문'">
        <textarea v-model="cred.value" rows="6" :class="[inputClass, 'mono resize-y']" />
      </Field>
    </div>
    <template #foot>
      <Btn @click="credTarget = null">취소</Btn>
      <Btn variant="primary" :disabled="!cred.value" @click="saveCredential">등록</Btn>
    </template>
  </Modal>
</template>
