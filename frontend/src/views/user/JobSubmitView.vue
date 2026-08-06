<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import { fileApi } from '@/api/files'
import { jobApi, type JobOptions } from '@/api/jobs'
import { useClusterStore } from '@/stores/cluster'
import type { JobSubmitRequest } from '@/types/api'
import Btn from '@/components/ui/Btn.vue'
import Card from '@/components/ui/Card.vue'
import ErrorNote from '@/components/ui/ErrorNote.vue'
import Field from '@/components/ui/Field.vue'
import Fid from '@/components/ui/Fid.vue'
import PageHead from '@/components/ui/PageHead.vue'

const clusters = useClusterStore()

type Mode = 'form' | 'script' | 'template'
const mode = ref<Mode>('form')
const busy = ref(false)
const error = ref<unknown>(null)
const preview = ref('')
const submitted = ref<string | null>(null)

const form = reactive<JobSubmitRequest>({
  name: '',
  partition: 'gpu',
  account: null,
  qos: null,
  nodes: 1,
  cpus_per_task: 8,
  gpus: 1,
  memory_gb: 32,
  walltime: '02:00:00',
  work_dir: null,
  script: '',
  template_id: null,
  template_params: null,
})

/**
 * 작업 디렉토리는 **본인 홈 하위로만** 지정할 수 있다.
 * 홈 경로는 손으로 받지 않고 서버가 NSS에서 읽어 준 값을 쓴다(정의서 §4.1 경로 인식) —
 * `/home/{user}` 같은 추정은 사이트마다 틀린다.
 */
/**
 * 파티션·계정·QOS는 클러스터에서 받아 고르게 한다 (U-JB-01).
 * 손으로 치면 오타 하나로 제출이 거부되고, 어떤 값이 유효한지 알 방법도 없다.
 * 다만 slurmdbd가 끊기면 계정·QOS가 비어 오므로, 그때는 직접 입력으로 되돌린다.
 */
const options = ref<JobOptions>({ partitions: [], accounts: [], qos: [] })

const home = ref('')
const subPath = ref('')

watch(
  () => clusters.selectedId,
  async (cid) => {
    if (!cid) return
    const [h, o] = await Promise.allSettled([fileApi.browse(cid), jobApi.options(cid)])
    // 홈을 못 읽으면 입력칸을 잠근다 — 틀린 경로로 제출해 실패하는 것보다 낫다.
    home.value = h.status === 'fulfilled' ? h.value.home : ''
    options.value =
      o.status === 'fulfilled' ? o.value : { partitions: [], accounts: [], qos: [] }
    // 목록에 없는 기본값은 지운다 — 화면에 빈 선택으로 남으면 혼란스럽다.
    if (options.value.partitions.length && !options.value.partitions.includes(form.partition ?? '')) {
      form.partition = options.value.partitions[0]
    }
  },
  { immediate: true },
)

/** 상위로 벗어나는 표기는 애초에 막는다. */
const subPathError = computed(() => {
  const v = subPath.value.trim()
  if (!v) return ''
  if (v.startsWith('/')) return '홈 아래 상대 경로만 입력하세요 (앞의 / 제외).'
  if (v.split('/').includes('..')) return '상위 경로(..)는 사용할 수 없습니다.'
  return ''
})

const workDir = computed(() => {
  if (!home.value) return null
  const v = subPath.value.trim().replace(/^\/+|\/+$/g, '')
  return v ? `${home.value}/${v}` : home.value
})

/** 모드별로 백엔드에 보낼 페이로드를 다르게 만든다 (U-JB-01/02/03). */
function payload(): JobSubmitRequest {
  // 서버가 모드를 알아야 #SBATCH 지시자를 만들지 말지 정할 수 있다.
  const base = { ...form, work_dir: workDir.value, mode: mode.value }
  if (mode.value === 'template') {
    base.script = null
  }
  return base
}

async function doPreview() {
  if (!clusters.selectedId) return
  busy.value = true
  error.value = null
  try {
    const res = await jobApi.previewScript(clusters.selectedId, payload())
    preview.value = res.script
  } catch (e) {
    error.value = e
    preview.value = ''
  } finally {
    busy.value = false
  }
}

async function submit() {
  if (!clusters.selectedId) return
  busy.value = true
  error.value = null
  try {
    const res = await jobApi.submit(clusters.selectedId, payload())
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
    title="Job 제출"
    :crumbs="['HPC Portal', 'Job', '제출']"
    :sub="`${clusters.selectedName} · 폼 / 스크립트 / 템플릿`"
  >
    <template #actions>
      <RouterLink to="/jobs"><Btn>목록으로</Btn></RouterLink>
    </template>
  </PageHead>

  <ErrorNote :error="error" />

  <div v-if="submitted" class="px-4 py-3 rounded-lg bg-ok-bg text-ok text-[14.5px] mb-4">
    Job <b class="mono">{{ submitted }}</b> 제출 완료.
    <RouterLink :to="`/jobs/${submitted}`" class="underline font-semibold">상세 보기</RouterLink>
  </div>

  <div class="grid lg:grid-cols-[1fr_420px] gap-5 items-start">
    <Card>
      <template #head>
        <div class="flex rounded-lg border border-line overflow-hidden text-[14px]">
          <button
            v-for="m in (['form', 'script', 'template'] as const)"
            :key="m"
            class="px-3 py-1.5"
            :class="mode === m ? 'bg-brand-700 text-white font-semibold' : 'bg-surface text-ink-2'"
            @click="mode = m"
          >{{ m === 'form' ? '폼' : m === 'script' ? '스크립트' : '템플릿' }}</button>
        </div>
        <Fid :id="mode === 'form' ? 'U-JB-01' : mode === 'script' ? 'U-JB-02' : 'U-JB-03'" />
      </template>

      <div class="grid sm:grid-cols-2 gap-4">
        <Field label="Job 이름" required full>
          <input v-model="form.name" :class="inputClass" placeholder="예: llm-finetune-r3" />
        </Field>
        <!-- 목록을 받아오지 못한 항목만 직접 입력으로 되돌린다(slurmdbd 미연결 등) -->
        <Field label="파티션" :hint="options.partitions.length ? '' : '목록을 불러오지 못해 직접 입력합니다.'">
          <select v-if="options.partitions.length" v-model="form.partition" :class="[inputClass, 'mono']">
            <option v-for="p in options.partitions" :key="p" :value="p">{{ p }}</option>
          </select>
          <input v-else v-model="form.partition" :class="[inputClass, 'mono']" placeholder="cpu" />
        </Field>
        <Field
          label="계정 (account)"
          :hint="options.accounts.length
            ? '내가 소속된 계정만 표시됩니다.'
            : '소속된 계정이 없습니다 — 기본 계정으로 제출됩니다. 계정이 필요하면 관리자에게 요청하세요.'"
        >
          <select v-if="options.accounts.length" v-model="form.account" :class="[inputClass, 'mono']">
            <option :value="null">(기본 계정)</option>
            <option v-for="a in options.accounts" :key="a" :value="a">{{ a }}</option>
          </select>
          <!-- 소속이 없으면 직접 입력을 열지 않는다 — 아무 값이나 넣어도 Slurm이 거부한다 -->
          <input v-else disabled :class="[inputClass, 'mono bg-bg']" placeholder="(기본 계정)" />
        </Field>
        <Field
          label="QOS"
          :hint="options.qos.length ? '미선택 시 계정 기본 QOS 상속' : 'QOS 목록을 불러오지 못했습니다(slurmdbd 확인).'"
        >
          <select v-if="options.qos.length" v-model="form.qos" :class="[inputClass, 'mono']">
            <option :value="null">(기본 QOS)</option>
            <option v-for="q in options.qos" :key="q" :value="q">{{ q }}</option>
          </select>
          <input v-else v-model="form.qos" :class="[inputClass, 'mono']" placeholder="비우면 기본 QOS" />
        </Field>
        <Field label="Walltime" hint="D-HH:MM:SS 또는 HH:MM:SS">
          <input v-model="form.walltime" :class="[inputClass, 'mono']" />
        </Field>

        <template v-if="mode !== 'template'">
          <Field label="노드 수"><input v-model.number="form.nodes" type="number" min="1" :class="[inputClass, 'mono']" /></Field>
          <Field label="CPU / task"><input v-model.number="form.cpus_per_task" type="number" min="1" :class="[inputClass, 'mono']" /></Field>
          <Field label="GPU 수"><input v-model.number="form.gpus" type="number" min="0" :class="[inputClass, 'mono']" /></Field>
          <Field label="메모리 (GB)"><input v-model.number="form.memory_gb" type="number" min="1" :class="[inputClass, 'mono']" /></Field>
        </template>

        <Field v-if="mode === 'template'" label="템플릿 ID" full hint="관리자가 등록한 템플릿 (A-OP-02)">
          <input v-model.number="form.template_id" type="number" :class="[inputClass, 'mono']" />
        </Field>

        <Field
          label="작업 디렉토리"
          full
          :hint="home ? `본인 홈 하위만 지정할 수 있습니다 · 현재: ${workDir}` : '홈 경로를 불러오지 못했습니다 — 클러스터 SSH 설정을 확인하세요.'"
        >
          <div class="flex items-stretch">
            <span
              class="px-3 py-2 rounded-l-lg border border-r-0 border-line bg-bg text-ink-3 mono text-[14px] whitespace-nowrap"
            >{{ home || '/home/…' }}/</span>
            <input
              v-model="subPath"
              :disabled="!home"
              :class="[inputClass, 'mono rounded-l-none']"
              placeholder="work (비우면 홈)"
            />
          </div>
          <p v-if="subPathError" class="mt-1 text-[13px] text-err">{{ subPathError }}</p>
        </Field>

        <Field
          v-if="mode !== 'template'" label="실행 스크립트" full
          :hint="mode === 'form'
            ? '실행할 명령만 쓰세요. 위 폼 값이 #SBATCH 지시자로 자동 생성됩니다.'
            : '#SBATCH 지시자를 포함한 전체 스크립트를 직접 작성합니다. 서버는 손대지 않습니다.'"
        >
          <textarea v-model="form.script" rows="8" :class="[inputClass, 'mono resize-y']" />
        </Field>
      </div>

      <template #foot>
        <div class="flex justify-end gap-2">
          <Btn :disabled="busy || !form.name || !!subPathError" @click="doPreview">스크립트 미리보기</Btn>
          <Btn variant="primary" :disabled="busy || !form.name || !!subPathError" @click="submit">
            {{ busy ? '제출 중…' : '제출 (sbatch)' }}
          </Btn>
        </div>
      </template>
    </Card>

    <Card title="생성될 배치 스크립트" sub="서버가 만드는 실제 내용">
      <pre
        v-if="preview"
        class="mono text-[13px] leading-relaxed bg-side-bg text-side-act rounded-lg p-4 overflow-x-auto whitespace-pre-wrap"
      >{{ preview }}</pre>
      <p v-else class="text-[14px] text-ink-3">
        “스크립트 미리보기”를 누르면 백엔드가 생성한 <span class="mono">#SBATCH</span> 지시자
        포함 전체 스크립트를 보여줍니다. 제출 전 확인용입니다.
        <br /><br />
        자원 값은 REST로도 함께 전달되며 <b>실제 적용은 REST 값</b>이 담당합니다.
        스크립트의 지시자는 같은 폼 값에서 나온 기록이라 내용이 어긋나지 않으며,
        이 스크립트를 그대로 <span class="mono">sbatch</span>로 재실행할 수 있습니다.
      </p>
      <template #foot>
        제출 대상 사용자는 <b>서버가 인증된 본인으로 강제</b>합니다 — 요청으로 지정할 수 없습니다.
      </template>
    </Card>
  </div>
</template>
