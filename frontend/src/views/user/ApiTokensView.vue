<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { apiTokenApi, type ApiToken } from '@/api/apiTokens'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Field from '@/components/ui/Field.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'
import { inputClass } from '@/utils/form'

/**
 * SCR-20 API 토큰 — 기계 클라이언트용 자격증명.
 *
 * 브라우저는 쿠키를, 사람이 붙어 있는 CLI는 로그인 토큰을 쓴다. **자동화는 둘 다 못 쓴다** —
 * 액세스 토큰은 30분이고, AD 비밀번호를 스크립트에 박으면 반복 실패로 계정이 잠긴다.
 */
const tokens = ref<ApiToken[]>([])
const error = ref<unknown>(null)
const busy = ref(false)
const form = ref({ name: '', expires_in_days: 90 as number | null })

/** 발급 직후 한 번만 보여 준다. 서버에는 해시만 남아 다시 못 본다. */
const issued = ref<string | null>(null)
const copied = ref(false)

async function load() {
  try {
    tokens.value = await apiTokenApi.list()
  } catch (e) {
    error.value = e
  }
}
onMounted(load)

async function create() {
  if (!form.value.name.trim()) return
  busy.value = true
  error.value = null
  copied.value = false
  try {
    const created = await apiTokenApi.create(form.value.name.trim(), form.value.expires_in_days)
    issued.value = created.token
    form.value.name = ''
    await load()
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}

async function revoke(t: ApiToken) {
  if (!confirm(`'${t.name}' 토큰을 폐기합니다. 이 토큰을 쓰는 스크립트는 즉시 멈춥니다.`)) return
  try {
    await apiTokenApi.revoke(t.id)
    await load()
  } catch (e) {
    error.value = e
  }
}

async function copy() {
  if (!issued.value) return
  await navigator.clipboard.writeText(issued.value)
  copied.value = true
}

const fmt = (v: string | null) => (v ? new Date(v).toLocaleString('ko-KR') : '—')

/** 만료·폐기는 서버가 판정한다. 여기서는 목록 표시용으로만 나눈다. */
function phase(t: ApiToken): { label: string; tone: 'idle' | 'down' | 'mixed' } {
  if (t.revoked_at) return { label: '폐기됨', tone: 'down' }
  if (t.expires_at && new Date(t.expires_at).getTime() < Date.now()) {
    return { label: '만료됨', tone: 'down' }
  }
  return { label: '사용 중', tone: 'idle' }
}

</script>

<template>
  <PageHead
    title="API 토큰"
    :crumbs="['HPC Portal', '내 정보', 'API 토큰']"
    sub="CLI·자동화에서 이 포털 API를 부를 때 쓰는 자격증명"
  />

  <ErrorNote :error="error" />

  <!-- 이 화면을 벗어나면 다시 볼 수 없다. 그 사실을 눈에 띄게 알린다. -->
  <div v-if="issued" class="px-4 py-3 rounded-lg bg-ok-bg text-ok text-[14.5px] mb-4">
    <b>토큰이 발급되었습니다. 지금 복사하세요 — 이 화면을 벗어나면 다시 볼 수 없습니다.</b>
    <div class="flex items-center gap-2 mt-2">
      <code class="flex-1 min-w-0 truncate mono text-[13px] bg-surface text-ink px-3 py-2 rounded-lg border border-line">
        {{ issued }}
      </code>
      <Btn size="sm" @click="copy">{{ copied ? '복사됨' : '복사' }}</Btn>
      <Btn size="sm" @click="issued = null">닫기</Btn>
    </div>
  </div>

  <div class="grid lg:grid-cols-[1fr_420px] gap-5 items-start">
    <Card title="발급된 토큰" flush>
      <Empty v-if="!tokens.length" text="발급된 토큰이 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'name', label: '이름' },
          { key: 'prefix', label: '토큰' },
          { key: 'state', label: '상태' },
          { key: 'last', label: '마지막 사용' },
          { key: 'exp', label: '만료' },
          { key: 'act', label: '', width: '80px' },
        ]"
      >
        <tr v-for="t in tokens" :key="t.id" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5"><b>{{ t.name }}</b></td>
          <td class="px-3.5 py-2.5 mono text-[13px]">{{ t.prefix }}…</td>
          <td class="px-3.5 py-2.5">
            <Badge :state="phase(t).tone">{{ phase(t).label }}</Badge>
          </td>
          <td class="px-3.5 py-2.5 text-[13px] text-ink-2">{{ fmt(t.last_used_at) }}</td>
          <td class="px-3.5 py-2.5 text-[13px] text-ink-2">
            {{ t.expires_at ? fmt(t.expires_at) : '없음' }}
          </td>
          <td class="px-3.5 py-2.5">
            <Btn v-if="!t.revoked_at" size="sm" variant="danger" @click="revoke(t)">폐기</Btn>
          </td>
        </tr>
      </Table>
      <template #foot>
        폐기는 <b>즉시</b> 적용됩니다 — 만료를 기다리지 않습니다.
        토큰의 권한은 <b>내 역할을 그대로 따릅니다</b>.
      </template>
    </Card>

    <div class="space-y-5">
      <Card title="새 토큰 발급">
        <div class="space-y-4">
          <Field label="이름" full hint="어디에 쓰는 토큰인지 나중에 알아볼 수 있게">
            <input v-model="form.name" :class="inputClass" placeholder="예: 렌더 파이프라인" />
          </Field>
          <Field label="만료" full hint="만료를 두는 편이 안전합니다">
            <select v-model.number="form.expires_in_days" :class="inputClass">
              <option :value="30">30일</option>
              <option :value="90">90일</option>
              <option :value="365">365일</option>
              <option :value="null">만료 없음</option>
            </select>
          </Field>
          <Btn variant="primary" class="w-full" :disabled="busy || !form.name.trim()" @click="create">
            {{ busy ? '발급 중…' : '토큰 발급' }}
          </Btn>
        </div>
      </Card>

      <Card title="사용법">
        <pre class="mono text-[12.5px] leading-relaxed bg-side-bg text-side-act rounded-lg p-3.5 overflow-x-auto whitespace-pre-wrap">curl -H "Authorization: Bearer $TOKEN" \
  https://www.dt-hpc.net:9443/api/v1/clusters</pre>
        <template #foot>
          토큰은 <b>내 계정으로</b> 동작합니다 — 대상 사용자는 서버가 본인으로 강제하며
          요청으로 지정할 수 없습니다.
        </template>
      </Card>
    </div>
  </div>
</template>
