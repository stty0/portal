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
  group_path_tpl: '/group/{group}', scratch_path_tpl: '/scratch/{user}', is_default: false,
})

const credTarget = ref<Cluster | null>(null)
const cred = reactive({ kind: 'SLURM_JWT' as 'SLURM_JWT' | 'SSH_KEY', value: '' })

async function load() {
  loading.value = true
  error.value = null
  try {
    const summaries = await clusterApi.list()
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
    group_path_tpl: '/group/{group}', scratch_path_tpl: '/scratch/{user}', is_default: false,
  })
  showForm.value = true
}

function openEdit(c: Cluster) {
  editing.value = c
  Object.assign(form, {
    name: c.name, description: c.description ?? '', slurmrestd_url: c.slurmrestd_url ?? '',
    api_version: c.api_version ?? 'v0.0.41', auth_method: c.auth_method ?? 'jwt',
    login_node: c.login_node ?? '', ssh_port: c.ssh_port ?? 22, ssh_account: c.ssh_account ?? '',
    group_path_tpl: c.group_path_tpl ?? '', scratch_path_tpl: c.scratch_path_tpl ?? '',
    is_default: c.is_default,
  })
  showForm.value = true
}

async function save() {
  error.value = null
  try {
    if (editing.value) {
      const { name: _ignored, ...patch } = form
      await clusterApi.update(editing.value.id, patch)
    } else {
      await clusterApi.create(form)
    }
    showForm.value = false
    await load()
    await store.load()
  } catch (e) {
    error.value = e
  }
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

async function saveCredential() {
  if (!credTarget.value) return
  error.value = null
  try {
    await clusterApi.putCredential(credTarget.value.id, cred.kind, cred.value)
    notice.value = `${credTarget.value.name}: ${cred.kind} 등록 완료 (값은 Secret 저장소에만 보관)`
    credTarget.value = null
    cred.value = ''
  } catch (e) {
    error.value = e
  }
}

const inputClass =
  'w-full px-3 py-2 rounded-lg border border-line-dark text-[13.5px] outline-none focus:border-brand-500'
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
  <div v-if="notice" class="px-3.5 py-2.5 rounded-lg bg-ok-bg text-ok text-[13px] mb-4">{{ notice }}</div>

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
        { key: 'a', label: '액션', width: '260px' },
      ]"
    >
      <tr v-for="c in rows" :key="c.id" class="border-b border-line last:border-0 hover:bg-bg">
        <td class="px-3.5 py-2.5">
          <b class="mono">{{ c.name }}</b>
          <Chip v-if="c.is_default" tone="brand" class="ml-1.5">기본</Chip>
          <p class="text-[12px] text-ink-3">{{ c.description }}</p>
        </td>
        <td class="px-3.5 py-2.5 mono text-[12.5px]">{{ c.slurmrestd_url ?? '—' }}</td>
        <td class="px-3.5 py-2.5 mono">{{ c.api_version ?? '—' }}</td>
        <td class="px-3.5 py-2.5 mono text-[12.5px]">{{ c.login_node ?? '—' }}</td>
        <td class="px-3.5 py-2.5">
          <Badge :state="c.is_active ? 'idle' : 'cancelled'">{{ c.is_active ? '활성' : '비활성' }}</Badge>
        </td>
        <td class="px-3.5 py-2.5">
          <div class="flex flex-wrap gap-1.5">
            <Btn size="sm" @click="testRest(c)">REST 테스트</Btn>
            <Btn size="sm" @click="credTarget = c">자격증명</Btn>
            <Btn size="sm" @click="openEdit(c)">수정</Btn>
            <Btn size="sm" variant="danger" @click="remove(c)">비활성</Btn>
          </div>
        </td>
      </tr>
    </Table>
    <template #foot>
      삭제는 <b>비활성화</b>로 처리됩니다 — 감사 로그의 FK를 살려 두기 위해서입니다.
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
      <Field label="slurmrestd URL" full required hint="포털 백엔드만 접근 — 네트워크 직접 노출 금지">
        <input v-model="form.slurmrestd_url" :class="[inputClass, 'mono']" placeholder="http://slurmrestd:6820" />
      </Field>
      <Field label="API 버전"><input v-model="form.api_version" :class="[inputClass, 'mono']" /></Field>
      <Field label="인증 방식">
        <select v-model="form.auth_method" :class="inputClass"><option>jwt</option><option>munge</option></select>
      </Field>
      <Field label="로그인 노드" hint="웹 터미널·SFTP 공용">
        <input v-model="form.login_node" :class="[inputClass, 'mono']" />
      </Field>
      <Field label="SSH 포트"><input v-model.number="form.ssh_port" type="number" :class="[inputClass, 'mono']" /></Field>
      <Field label="SSH 서비스 계정" hint="전체 root sudo 지양 · 제한적 sudo 권장">
        <input v-model="form.ssh_account" :class="[inputClass, 'mono']" />
      </Field>
      <Field label="그룹 경로 템플릿" hint="{group} 세션 치환">
        <input v-model="form.group_path_tpl" :class="[inputClass, 'mono']" />
      </Field>
      <Field label="스크래치 경로 템플릿" full hint="{user} 세션 치환 · 홈은 SSSD/NSS로 자동 인식">
        <input v-model="form.scratch_path_tpl" :class="[inputClass, 'mono']" />
      </Field>
      <label class="sm:col-span-2 flex items-center gap-2 text-[13.5px] text-ink-2">
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
    <div class="px-3.5 py-2.5 rounded-lg bg-warn-bg text-warn text-[13px] mb-4">
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
