<script setup lang="ts">
import { reactive, ref } from 'vue'
import { jobApi } from '@/api/jobs'
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
  script: 'srun python train.py',
  template_id: null,
  template_params: null,
})

/** 모드별로 백엔드에 보낼 페이로드를 다르게 만든다 (U-JB-01/02/03). */
function payload(): JobSubmitRequest {
  const base = { ...form }
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
  'w-full px-3 py-2 rounded-lg border border-line-dark text-[13.5px] outline-none focus:border-brand-500'
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

  <div v-if="submitted" class="px-4 py-3 rounded-lg bg-ok-bg text-ok text-[13.5px] mb-4">
    Job <b class="mono">{{ submitted }}</b> 제출 완료.
    <RouterLink :to="`/jobs/${submitted}`" class="underline font-semibold">상세 보기</RouterLink>
  </div>

  <div class="grid lg:grid-cols-[1fr_420px] gap-5 items-start">
    <Card>
      <template #head>
        <div class="flex rounded-lg border border-line overflow-hidden text-[13px]">
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
        <Field label="파티션"><input v-model="form.partition" :class="[inputClass, 'mono']" /></Field>
        <Field label="계정 (account)">
          <input v-model="form.account" :class="[inputClass, 'mono']" placeholder="acct-llm" />
        </Field>
        <Field label="QOS" hint="미선택 시 계정 기본 QOS 상속">
          <input v-model="form.qos" :class="[inputClass, 'mono']" placeholder="normal" />
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

        <Field label="작업 디렉토리" full>
          <input v-model="form.work_dir" :class="[inputClass, 'mono']" placeholder="/home/{user}/work" />
        </Field>

        <Field
          v-if="mode !== 'template'" label="실행 스크립트" full
          hint="폼 모드에서도 실행할 본문이 필요합니다. #SBATCH 지시자는 서버가 붙입니다."
        >
          <textarea
            v-model="form.script" rows="8"
            :class="[inputClass, 'mono resize-y']"
            placeholder="srun python train.py"
          />
        </Field>
      </div>

      <template #foot>
        <div class="flex justify-end gap-2">
          <Btn :disabled="busy" @click="doPreview">스크립트 미리보기</Btn>
          <Btn variant="primary" :disabled="busy || !form.name" @click="submit">
            {{ busy ? '제출 중…' : '제출 (sbatch)' }}
          </Btn>
        </div>
      </template>
    </Card>

    <Card title="생성될 배치 스크립트" sub="서버가 만드는 실제 내용">
      <pre
        v-if="preview"
        class="mono text-[12px] leading-relaxed bg-side-bg text-side-act rounded-lg p-4 overflow-x-auto whitespace-pre-wrap"
      >{{ preview }}</pre>
      <p v-else class="text-[13px] text-ink-3">
        “스크립트 미리보기”를 누르면 백엔드가 생성한 <span class="mono">#SBATCH</span> 지시자
        포함 전체 스크립트를 보여줍니다. 제출 전 확인용입니다.
      </p>
      <template #foot>
        제출 대상 사용자는 <b>서버가 인증된 본인으로 강제</b>합니다 — 요청으로 지정할 수 없습니다.
      </template>
    </Card>
  </div>
</template>
