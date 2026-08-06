<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  billingApi,
  type BillingConfig,
  type BillingRule,
  type BillingTrend,
} from '@/api/billing'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Chip from '@/components/ui/Chip.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'
import Table from '@/components/ui/Table.vue'

/** SCR-19 — SCP costexplorer 실 데이터. 키는 Secret 저장소에만 있고 화면에 오지 않는다. */
const config = ref<BillingConfig | null>(null)
const trend = ref<BillingTrend | null>(null)
const rules = ref<BillingRule[]>([])
const days = ref(30)
/** 태그 필터 — 비용 응답에 태그가 없어 서버가 태그 API로 자원을 추려 걸러낸다. */
const tag = ref('')
const loading = ref(false)
const errors = ref<{ trend: unknown; rules: unknown; config: unknown }>({
  trend: null,
  rules: null,
  config: null,
})
/** 규칙은 태그 전용이다. condition에는 서버·필터가 쓰는 `key=value` 형식으로 합쳐 보낸다. */
const form = ref({ key: '', value: '', mapping_label: '' })

function tagParts(condition: string) {
  const i = condition.indexOf('=')
  return i < 0
    ? { key: condition, value: '' }
    : { key: condition.slice(0, i), value: condition.slice(i + 1) }
}

/** A-BL-01 자격증명 입력. 저장 후에는 화면에 남기지 않는다. */
const editing = ref(false)
const saving = ref(false)
const creds = ref({ access_key: '', secret_key: '', monthly_alert_krw: null as number | null })

async function saveCredentials() {
  saving.value = true
  errors.value.config = null
  try {
    config.value = await billingApi.putConfig({ ...creds.value })
    // 입력값은 즉시 지운다 — 브라우저 메모리에 남길 이유가 없다
    creds.value = { access_key: '', secret_key: '', monthly_alert_krw: null }
    editing.value = false
    await load()
  } catch (e) {
    errors.value.config = e
  } finally {
    saving.value = false
  }
}

/** 등록된 태그 규칙을 그대로 필터 선택지로 쓴다 — 두 번 입력할 이유가 없다. */
const tagRules = computed(() => rules.value.filter((r) => r.kind === 'tag' && r.is_active))

async function load() {
  loading.value = true
  const [c, t, r] = await Promise.allSettled([
    billingApi.config(),
    billingApi.trend(days.value, tag.value || undefined),
    billingApi.rules(),
  ])
  config.value = c.status === 'fulfilled' ? c.value : null
  trend.value = t.status === 'fulfilled' ? t.value : null
  rules.value = r.status === 'fulfilled' ? r.value : []
  errors.value = {
    config: c.status === 'rejected' ? c.reason : null,
    trend: t.status === 'rejected' ? t.reason : null,
    rules: r.status === 'rejected' ? r.reason : null,
  }
  loading.value = false
}
onMounted(load)

async function addRule() {
  const key = form.value.key.trim()
  const value = form.value.value.trim()
  if (!key || !value) return
  try {
    await billingApi.addRule({
      kind: 'tag',
      condition: `${key}=${value}`,
      mapping_label: form.value.mapping_label,
    })
    form.value = { key: '', value: '', mapping_label: '' }
    rules.value = await billingApi.rules()
  } catch (e) {
    errors.value.rules = e
  }
}

async function removeRule(id: number) {
  await billingApi.removeRule(id)
  rules.value = await billingApi.rules()
}

const krw = (v: number) => v.toLocaleString('ko-KR') + '원'
/** 막대 길이는 최대값 기준 상대치 — 절대 금액은 옆에 숫자로 읽는다. */
const peak = computed(() => Math.max(1, ...(trend.value?.daily ?? []).map((d) => d.krw)))
const inputClass =
  'w-full px-3 py-2 border border-line rounded-lg text-[14.5px] outline-none focus:border-brand-500'
</script>

<template>
  <PageHead
    title="비용 / Billing"
    :crumbs="['HPC Portal Admin', '운영']"
    sub="SCP 클라우드 청구 비용"
  >
    <template #actions>
      <select v-model="tag" :class="[inputClass, 'w-auto']" @change="load">
        <option value="">전체 자원</option>
        <option v-for="r in tagRules" :key="r.id" :value="r.condition">
          {{ r.condition }}{{ r.mapping_label ? ` · ${r.mapping_label}` : '' }}
        </option>
      </select>
      <select v-model.number="days" :class="[inputClass, 'w-auto']" @change="load">
        <option :value="7">최근 7일</option>
        <option :value="30">최근 30일</option>
        <option :value="90">최근 90일</option>
      </select>
      <Btn @click="load">↻ 새로고침</Btn>
    </template>
  </PageHead>

  <div v-if="loading" class="py-12 text-center text-ink-3">불러오는 중…</div>

  <div v-else class="space-y-5">
    <Card title="비용 추이" flush>
      <template #title-extra><Fid id="A-BL-03" /></template>
      <ErrorNote :error="errors.trend" class="m-4" />
      <Empty v-if="!trend && !errors.trend" text="비용 데이터가 없습니다." />
      <template v-else-if="trend">
        <div class="px-4 py-3 border-b border-line flex flex-wrap items-center gap-4">
          <span class="text-[13px] text-ink-3">{{ trend.start }} ~ {{ trend.end }}</span>
          <b class="text-[21px] text-ink mono">{{ krw(trend.total_krw) }}</b>
          <Chip tone="gray">{{ trend.record_count }}건</Chip>
          <Chip v-if="trend.tag" tone="brand">
            {{ trend.tag }} · 자원 {{ trend.tagged_resource_count }}개
          </Chip>
        </div>
        <div class="p-4 space-y-1.5">
          <div v-for="d in trend.daily" :key="d.date" class="flex items-center gap-3">
            <span class="w-24 shrink-0 mono text-[13px] text-ink-3">{{ d.date }}</span>
            <div class="flex-1 h-3 rounded bg-idle-bg overflow-hidden">
              <div class="h-full rounded bg-brand-700" :style="{ width: (d.krw / peak) * 100 + '%' }" />
            </div>
            <span class="w-28 shrink-0 mono text-[13px] text-right">{{ krw(d.krw) }}</span>
          </div>
        </div>
        <div class="grid sm:grid-cols-2 gap-5 p-4 border-t border-line">
          <div>
            <p class="text-[13px] font-bold text-ink-3 mb-2">서비스 분류별</p>
            <div v-for="c in trend.by_category" :key="c.label" class="flex justify-between text-[14px] py-1">
              <span class="mono">{{ c.label }}</span><b class="mono">{{ krw(c.krw) }}</b>
            </div>
          </div>
          <div>
            <p class="text-[13px] font-bold text-ink-3 mb-2">청구 항목별</p>
            <div v-for="i in trend.by_item" :key="i.label" class="flex justify-between text-[14px] py-1">
              <span class="mono truncate">{{ i.label }}</span><b class="mono">{{ krw(i.krw) }}</b>
            </div>
          </div>
        </div>
      </template>
    </Card>

    <Card title="자원 식별 규칙" flush>
      <template #title-extra><Fid id="A-BL-02" /></template>
      <ErrorNote :error="errors.rules" class="m-4" />
      <!-- SCP 응답에 Tag가 없어 resource_id 등 조건식으로 클러스터를 식별한다 -->
      <div class="px-4 py-3 border-b border-line flex flex-wrap gap-2 items-end">
        <label class="flex-1 min-w-[160px] text-[13px] text-ink-3">
          태그 키
          <input v-model="form.key" :class="[inputClass, 'mono mt-1']" placeholder="purpose" />
        </label>
        <label class="flex-1 min-w-[160px] text-[13px] text-ink-3">
          태그 값
          <input v-model="form.value" :class="[inputClass, 'mono mt-1']" placeholder="hpc" />
        </label>
        <label class="flex-1 min-w-[160px] text-[13px] text-ink-3">
          매핑 대상
          <input v-model="form.mapping_label" :class="[inputClass, 'mt-1']" placeholder="slurm-cluster-1" />
        </label>
        <Btn variant="primary" @click="addRule">추가</Btn>
      </div>
      <Empty v-if="!rules.length" text="등록된 규칙이 없습니다." />
      <Table
        v-else
        :columns="[
          { key: 'tagkey', label: '태그 키' },
          { key: 'tagval', label: '태그 값' },
          { key: 'map', label: '매핑 대상' },
          { key: 'state', label: '상태' },
          { key: 'act', label: '', width: '80px' },
        ]"
      >
        <tr v-for="r in rules" :key="r.id" class="border-b border-line last:border-0">
          <td class="px-3.5 py-2.5 mono">{{ tagParts(r.condition).key }}</td>
          <td class="px-3.5 py-2.5 mono">{{ tagParts(r.condition).value || '—' }}</td>
          <td class="px-3.5 py-2.5">{{ r.mapping_label ?? '—' }}</td>
          <td class="px-3.5 py-2.5">
            <Badge :state="r.is_active ? 'idle' : 'down'">{{ r.is_active ? '사용' : '중지' }}</Badge>
          </td>
          <td class="px-3.5 py-2.5"><Btn size="sm" variant="danger" @click="removeRule(r.id)">삭제</Btn></td>
        </tr>
      </Table>
    </Card>

    <Card title="SCP Billing API 연동">
      <template #title-extra><Fid id="A-BL-01" /></template>
      <template #head>
        <Btn v-if="!editing" @click="editing = true">
          {{ config?.configured ? '키 변경' : '키 등록' }}
        </Btn>
      </template>
      <ErrorNote :error="errors.config" />

      <form v-if="editing" class="grid sm:grid-cols-2 gap-4 mb-5" @submit.prevent="saveCredentials">
        <label class="text-[13px] text-ink-3">
          Access Key
          <input v-model="creds.access_key" required :class="[inputClass, 'mono mt-1']"
                 placeholder="SCP 콘솔에서 발급한 Access Key" />
        </label>
        <label class="text-[13px] text-ink-3">
          Secret Key
          <input v-model="creds.secret_key" required type="password" :class="[inputClass, 'mt-1']"
                 placeholder="다시 표시되지 않습니다" />
        </label>
        <label class="text-[13px] text-ink-3">
          월 예산 경보 (원)
          <input v-model.number="creds.monthly_alert_krw" type="number" min="0"
                 :class="[inputClass, 'mono mt-1']" placeholder="비우면 유지" />
        </label>
        <div class="flex items-end gap-2">
          <Btn type="submit" variant="primary" :disabled="saving">
            {{ saving ? '검증 중…' : '저장 (연결 확인)' }}
          </Btn>
          <Btn type="button" @click="editing = false">취소</Btn>
        </div>
        <p class="sm:col-span-2 text-[13px] text-ink-3">
          저장 전에 실제로 SCP에 조회해 키가 유효한지 확인합니다. 실패하면 저장하지 않습니다.
        </p>
      </form>
      <dl v-if="config" class="grid grid-cols-[160px_1fr] gap-y-2.5 text-[14.5px]">
        <dt class="text-ink-3">자격증명</dt>
        <dd>
          <Chip :tone="config.configured ? 'brand' : 'gray'">
            {{ config.configured ? '••••• Secret 저장소' : '미설정' }}
          </Chip>
        </dd>
        <dt class="text-ink-3">SCP 계정</dt>
        <dd class="mono">{{ config.scp_account_id ?? '—' }}</dd>
        <dt class="text-ink-3">마지막 조회</dt>
        <dd class="mono">
          {{ config.last_verified_at ? new Date(config.last_verified_at).toLocaleString('ko-KR') : '—' }}
        </dd>
        <dt class="text-ink-3">월 예산 경보</dt>
        <dd class="mono">{{ config.monthly_alert_krw ? krw(config.monthly_alert_krw) : '미설정' }}</dd>
      </dl>
      <p class="mt-3 text-[13px] text-ink-3">
        Access/Secret Key는 Secret 저장소에만 보관되며 화면·API 응답에 표시되지 않습니다.
      </p>
    </Card>
  </div>
</template>
