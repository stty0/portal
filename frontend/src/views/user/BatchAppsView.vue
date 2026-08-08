<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { batchAppApi, type BatchApp } from '@/api/batchApps'
import { fileApi } from '@/api/files'
import { jobApi, type JobOptions } from '@/api/jobs'
import { useClusterStore } from '@/stores/cluster'
import Badge from '@/components/ui/Badge.vue'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import Empty from '@/components/ui/Empty.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Field from '@/components/ui/Field.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'

/**
 * SCR-21 Batch 앱 — 해석 solver를 배치 Job으로 제출한다 (U-JB-13).
 *
 * 인터랙티브 앱과 같은 자리에서 출발하되 **끝이 다르다**. 세션이 아니라 Job이 남고,
 * 결과는 홈 디렉터리에 떨어진다.
 *
 * 파라미터는 **앱마다 다르다.** 화면이 필드를 갖고 있으면 앱을 늘릴 때마다 화면을
 * 고쳐야 하므로, 카탈로그가 내려준 스키마로 그린다.
 */
const clusters = useClusterStore()
const apps = ref<BatchApp[]>([])
const selected = ref<BatchApp | null>(null)
const error = ref<unknown>(null)
const busy = ref(false)
const submitted = ref<string | null>(null)

/** 앱을 바꾸면 파라미터도 통째로 바뀐다 — 이전 값이 남으면 엉뚱하게 제출된다. */
const params = reactive<Record<string, string>>({})

const form = reactive({
  name: '',
  partition: '',
  nodes: 1,
  ntasks: 1,
  cpus_per_task: 1,
  gpus: 0,
  memory_gb: 32,
  walltime: '02:00:00',
  array: '' as string,
})

const options = ref<JobOptions>({ partitions: [], accounts: [], qos: [], gpu_partitions: null })
const home = ref('')
const subPath = ref('')

onMounted(async () => {
  try {
    apps.value = await batchAppApi.list()
  } catch (e) {
    error.value = e
  }
})

watch(
  () => clusters.selectedId,
  async (cid) => {
    if (!cid) return
    const [h, o] = await Promise.allSettled([fileApi.browse(cid), jobApi.options(cid)])
    home.value = h.status === 'fulfilled' ? h.value.home : ''
    options.value =
      o.status === 'fulfilled'
        ? o.value
        : { partitions: [], accounts: [], qos: [], gpu_partitions: null }
    if (!form.partition && options.value.partitions.length) {
      form.partition = options.value.partitions[0]
    }
  },
  { immediate: true },
)

function choose(app: BatchApp) {
  if (!app.ready) return
  selected.value = app
  submitted.value = null
  for (const key of Object.keys(params)) delete params[key]
  for (const p of app.params) params[p.key] = p.default ?? ''
  if (!form.name) form.name = app.id
}

/** GPU 없는 파티션이면 잠근다 — 넣어봐야 Slurm이 거부한다(Job 제출과 같은 규칙). */
const gpuAvailable = computed(() => {
  const list = options.value.gpu_partitions
  if (list === null) return true
  return list.includes(form.partition)
})
watch(gpuAvailable, (ok) => {
  if (!ok) form.gpus = 0
})

const workDir = computed(() => {
  if (!home.value) return null
  const v = subPath.value.trim().replace(/^\/+|\/+$/g, '')
  return v ? `${home.value}/${v}` : home.value
})

/** 서버도 검사하지만, 제출 전에 알려 주는 편이 낫다. */
const missing = computed(() =>
  (selected.value?.params ?? [])
    .filter((p) => p.required && !(params[p.key] ?? '').trim() && !p.default)
    .map((p) => p.label),
)

async function submit() {
  const cid = clusters.selectedId
  const app = selected.value
  if (!cid || !app) return
  busy.value = true
  error.value = null
  try {
    const res = await batchAppApi.submit(cid, app.id, {
      name: form.name || app.id,
      partition: form.partition || null,
      nodes: form.nodes,
      ntasks: form.ntasks,
      cpus_per_task: form.cpus_per_task,
      gpus: form.gpus || null,
      memory_gb: form.memory_gb,
      walltime: form.walltime,
      work_dir: workDir.value,
      array: form.array.trim() || null,
      params: { ...params },
    })
    submitted.value = res.job_id
  } catch (e) {
    error.value = e
  } finally {
    busy.value = false
  }
}

const inputClass =
  'w-full px-3 py-2 rounded-lg border border-line-dark text-[14.5px] outline-none focus:border-brand-500'
</script>

<template>
  <PageHead
    title="Batch 앱"
    :crumbs="['HPC Portal', '작업 환경', 'Batch 앱']"
    :sub="`해석 s/w를 배치 Job으로 제출 · ${clusters.selectedName}`"
  >
    <template #actions>
      <RouterLink to="/jobs"><Btn>Job 목록</Btn></RouterLink>
    </template>
  </PageHead>

  <ErrorNote :error="error" />

  <div v-if="submitted" class="px-4 py-3 rounded-lg bg-ok-bg text-ok text-[14.5px] mb-4">
    Job <b class="mono">{{ submitted }}</b> 제출 완료.
    <RouterLink :to="`/jobs/${submitted}`" class="underline font-semibold">상세 보기</RouterLink>
    — 결과는 작업 디렉터리에 떨어집니다.
  </div>

  <div class="grid lg:grid-cols-[1fr_420px] gap-5 items-start">
    <div class="space-y-5">
      <Card title="해석 s/w">
        <template #title-extra><Fid id="U-JB-13" /></template>
        <Empty v-if="!apps.length" text="등록된 앱이 없습니다." />
        <div v-else class="grid sm:grid-cols-2 gap-4">
          <!-- 준비 전 앱도 보여준다. 숨기면 "언젠가 되나?"를 물을 데가 없다. -->
          <button
            v-for="a in apps"
            :key="a.id"
            class="text-left border rounded-lg p-4 transition-colors"
            :class="[
              selected?.id === a.id ? 'border-brand-500 bg-brand-50' : 'border-line',
              a.ready ? 'hover:border-brand-500' : 'opacity-60 cursor-not-allowed',
            ]"
            @click="choose(a)"
          >
            <div class="flex items-start gap-2 mb-1.5">
              <b class="flex-1 text-[15.5px] text-ink">{{ a.name }}</b>
              <Badge :state="a.ready ? 'idle' : 'down'">{{ a.ready ? '사용 가능' : '준비 중' }}</Badge>
            </div>
            <p class="text-[13.5px] text-ink-2">{{ a.description }}</p>
            <p v-if="a.needs_gpu" class="mt-1.5 text-[12.5px] text-ink-3">GPU 필요</p>
          </button>
        </div>
        <template #foot>
          이미지는 클러스터의 <b>이미지 저장소</b>에서 가져옵니다. 준비 중인 앱은
          이미지가 아직 등록되지 않은 것입니다.
        </template>
      </Card>

      <!-- 파라미터는 앱이 정한다. 화면은 스키마대로 그린다. -->
      <Card v-if="selected" :title="`${selected.name} 입력값`">
        <div class="grid sm:grid-cols-2 gap-4">
          <Field
            v-for="p in selected.params"
            :key="p.key"
            :label="p.label"
            :required="p.required"
            :hint="p.hint"
            :full="p.type === 'path'"
          >
            <!-- 체크박스는 단계를 켜고 끈다(예: decomposePar) -->
            <label v-if="p.type === 'bool'" class="flex items-center gap-2 h-[42px] text-[14.5px]">
              <input
                type="checkbox"
                :checked="params[p.key] !== '0'"
                class="w-4 h-4"
                @change="params[p.key] = ($event.target as HTMLInputElement).checked ? '1' : '0'"
              />
              <span class="text-ink-2">사용</span>
            </label>
            <select v-else-if="p.options.length" v-model="params[p.key]" :class="inputClass">
              <option v-for="o in p.options" :key="o" :value="o">{{ o }}</option>
            </select>
            <input
              v-else
              v-model="params[p.key]"
              :type="p.type === 'number' ? 'number' : 'text'"
              :class="[inputClass, p.type === 'path' || p.type === 'number' ? 'mono' : '']"
              :placeholder="p.type === 'path' ? (home ? `${home}/입력파일` : '/home/…') : ''"
            />
          </Field>
        </div>
      </Card>
    </div>

    <Card v-if="selected" title="자원">
      <div class="grid sm:grid-cols-2 gap-4">
        <Field label="Job 이름" required full>
          <input v-model="form.name" :class="inputClass" />
        </Field>
        <Field label="파티션" full>
          <select v-if="options.partitions.length" v-model="form.partition" :class="[inputClass, 'mono']">
            <option v-for="p in options.partitions" :key="p" :value="p">{{ p }}</option>
          </select>
          <input v-else v-model="form.partition" :class="[inputClass, 'mono']" placeholder="cpu" />
        </Field>
        <Field label="노드 수"><input v-model.number="form.nodes" type="number" min="1" :class="[inputClass, 'mono']" /></Field>
        <!--
          MPI는 **랭크 수가 정본**이다. OpenFOAM은 이 값이 케이스의
          decomposeParDict(numberOfSubdomains)와 같아야 하는데, 그 값은 파일 안에 있어
          화면에서 보이지 않는다 — 그래서 스크립트가 세어 보고 다르면 사유를 적고 멈춘다.
        -->
        <Field label="MPI 랭크 (--ntasks)" hint="병렬 solver의 프로세스 수">
          <input v-model.number="form.ntasks" type="number" min="1" :class="[inputClass, 'mono']" />
        </Field>
        <Field label="CPU / rank"><input v-model.number="form.cpus_per_task" type="number" min="1" :class="[inputClass, 'mono']" /></Field>
        <Field
          label="GPU 수"
          :hint="gpuAvailable ? '' : `'${form.partition}' 파티션에는 GPU 노드가 없습니다`"
        >
          <input
            v-model.number="form.gpus" type="number" min="0" :disabled="!gpuAvailable"
            :class="[inputClass, 'mono', gpuAvailable ? '' : 'bg-bg text-ink-3']"
          />
        </Field>
        <Field label="메모리 (GB)"><input v-model.number="form.memory_gb" type="number" min="1" :class="[inputClass, 'mono']" /></Field>
        <Field label="Walltime" hint="D-HH:MM:SS 또는 HH:MM:SS">
          <input v-model="form.walltime" :class="[inputClass, 'mono']" />
        </Field>
        <Field label="배열 인덱스" hint="예: 1-240 — 비우면 단일 Job">
          <input v-model="form.array" :class="[inputClass, 'mono']" placeholder="비우면 단일" />
        </Field>
        <Field
          label="작업 디렉터리"
          full
          :hint="home ? `결과가 여기에 떨어집니다 · 현재: ${workDir}` : '홈 경로를 불러오지 못했습니다.'"
        >
          <div class="flex items-stretch">
            <span class="px-3 py-2 rounded-l-lg border border-r-0 border-line bg-bg text-ink-3 mono text-[14px] whitespace-nowrap">
              {{ home || '/home/…' }}/
            </span>
            <input v-model="subPath" :disabled="!home" :class="[inputClass, 'mono rounded-l-none']" placeholder="work (비우면 홈)" />
          </div>
        </Field>
      </div>

      <template #foot>
        <p v-if="missing.length" class="text-[13px] text-err mb-2">
          입력이 필요합니다: {{ missing.join(', ') }}
        </p>
        <Btn
          variant="primary" class="w-full"
          :disabled="busy || !form.name || missing.length > 0"
          @click="submit"
        >{{ busy ? '제출 중…' : '제출 (sbatch)' }}</Btn>
      </template>
    </Card>

    <Card v-else title="해석 s/w를 고르세요">
      <p class="text-[14px] text-ink-3">
        왼쪽에서 앱을 고르면 그 앱이 요구하는 입력값과 자원 설정이 나타납니다.
        제출하면 배치 Job으로 들어가고, 진행 상황은 <b>Job 목록</b>에서 봅니다.
      </p>
    </Card>
  </div>
</template>
