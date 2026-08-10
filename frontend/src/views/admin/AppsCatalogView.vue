<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { clusterApi } from '@/api/clusters'
import { opsApi, type AppCatalog } from '@/api/ops'
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
 * SCR-22 앱 관리 (A-OP-02) — 포탈 설정 콘솔.
 *
 * 여기서 다루는 것은 앱의 **정보**뿐이다. 기동 스크립트·파라미터 스키마 같은 **실행
 * 방식은 코드 카탈로그가 정본**이라 화면에 나오지 않는다(`session_apps.py`·`batch_apps.py`).
 * `종류 + 앱 ID`가 코드의 앱과 이어지는 연결 키다.
 *
 * 목록에는 **코드 카탈로그의 앱이 모두** 나온다. "정보 미등록"인 앱도 이미 동작 중이고,
 * 여기서 정보를 채우면 사용자 런처 카드에 아이콘·벤더·버전이 붙는다.
 */
const apps = ref<AppCatalog[]>([])
//: 아이콘·이미지 모두 **서버 디렉터리에 실제로 있는 파일만** 고르게 한다. 임의 URL은 받지 않는다.
const iconFiles = ref<string[]>([])
const imageFiles = ref<string[]>([])
const error = ref<unknown>(null)
const notice = ref('')
const loading = ref(false)
/** 변환 대상 앱. `null`이면 모달이 닫혀 있다. */
const converting = ref<AppCatalog | null>(null)
const convertCluster = ref<number | null>(null)
const convertBusy = ref(false)
const clusters = ref<{ id: number; name: string | null; alias: string | null }[]>([])
const uploadingIcon = ref(false)
const saving = ref(false)

/** 모달 상태. `null`이면 닫힘. */
const editing = ref<AppCatalog | null>(null)
const creating = ref(false)
const open = computed(() => creating.value || editing.value !== null)

const emptyApp = (): Partial<AppCatalog> => ({
  kind: 'interactive', app_id: '', name: '', vendor: '', version: '',
  image_file: '', image_ref: '', icon_file: '', description: '',
})
const form = ref<Partial<AppCatalog>>(emptyApp())

/**
 * 이미지 파일 목록. **클러스터마다 경로가 다르므로** 전 클러스터에 물어 합집합을 만든다.
 *
 * 이 화면은 포탈 스코프라 클러스터 선택기가 없다. 선택기의 목적은 *유효한 파일명을
 * 고르게 돕는 것*이고, 저장되는 값은 파일명 하나다 — 어느 클러스터에 실제로 있는지는
 * 사용자 앱 목록이 `installed`로 답한다. 한 클러스터가 죽어도 나머지는 나와야 하므로
 * 실패는 빈 목록으로 흡수한다(서버도 같은 규칙이다).
 */
async function loadImageFiles(): Promise<string[]> {
  clusters.value = await clusterApi.list()
  const lists = await Promise.all(
    clusters.value.map((c) => clusterApi.appImages(c.id).catch(() => [] as string[])),
  )
  return [...new Set(lists.flat())].sort()
}

/**
 * OCI 참조에서 SIF 파일명을 만든다 — `docker://stty0/rocky9-mate:1.5` → `rocky9-mate-1.5.sif`.
 *
 * **제안일 뿐 강제가 아니다.** 이미 디렉터리에 있는 파일들은 손으로 붙인 이름을 갖고 있고,
 * 레지스트리에서 오지 않는 이미지도 있다. 다만 출처를 바꿔 놓고 파일명을 그대로 두면
 * **이름이 거짓말을 하므로**(`:2606`을 받아 `…-2512.sif`로 저장) 비어 있을 때 채워 준다.
 */
function suggestFileName(ref: string): string {
  const path = ref.replace(/^[A-Za-z][A-Za-z0-9+.-]*:\/\//, '').split('@')[0]
  const last = path.split('/').pop() ?? ''
  const [name, tag] = last.split(':')
  if (!name) return ''
  return `${tag ? `${name}-${tag}` : name}.sif`
}

/** 출처를 입력하면 파일명을 채워 준다 — **비어 있을 때만**. 손으로 넣은 값을 덮지 않는다. */
function onRefInput() {
  if (!form.value.image_file && form.value.image_ref) {
    form.value.image_file = suggestFileName(form.value.image_ref)
  }
}

const clusterLabel = (c: { name: string | null; alias: string | null }) =>
  c.alias || c.name || '이름 미확인 클러스터'

function openConvert(a: AppCatalog) {
  converting.value = a
  convertCluster.value = clusters.value[0]?.id ?? null
  notice.value = ''
  error.value = null
}

/**
 * 빌드와 배치를 **두 걸음으로 나눈 이유**: 포털에 백그라운드 워커가 없다. 잡이 끝났는지는
 * Job 화면이 말해 주고, 관리자가 그때 [배치]를 누른다. 폴링을 흉내 내느니 정직하다.
 */
async function runBuild() {
  const app = converting.value
  const cid = convertCluster.value
  if (!app || cid === null) return
  convertBusy.value = true
  error.value = null
  try {
    const res = await clusterApi.buildAppImage(cid, app.kind, app.app_id)
    notice.value =
      `변환 Job을 제출했습니다 (Job ${res.job_id}). 끝나면 [배치]를 누르세요 — ` +
      'SIF는 내 홈의 .portal/build 아래에 만들어집니다.'
  } catch (e) {
    error.value = e
  } finally {
    convertBusy.value = false
  }
}

async function runInstall() {
  const app = converting.value
  const cid = convertCluster.value
  if (!app || cid === null) return
  convertBusy.value = true
  error.value = null
  try {
    const res = await clusterApi.installAppImage(cid, app.kind, app.app_id)
    notice.value = res.message || '이미지를 배치했습니다.'
    await load()
  } catch (e) {
    error.value = e
  } finally {
    convertBusy.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const [list, icons, images] = await Promise.all([
      opsApi.apps(), opsApi.appIcons(), loadImageFiles(),
    ])
    apps.value = list
    iconFiles.value = icons
    imageFiles.value = images
    error.value = null
  } catch (e) {
    error.value = e
  } finally {
    loading.value = false
  }
}
onMounted(load)

function openCreate() {
  creating.value = true
  editing.value = null
  form.value = emptyApp()
  error.value = null
}

function openEdit(a: AppCatalog) {
  editing.value = a
  creating.value = false
  error.value = null
  // 미등록 코드 앱이면 이름·설명은 코드 값이 이미 들어 있고 나머지는 빈 칸으로 연다.
  form.value = {
    ...a,
    vendor: a.vendor ?? '',
    version: a.version ?? '',
    image_file: a.image_file ?? '',
    image_ref: a.image_ref ?? '',
    icon_file: a.icon_file ?? '',
    description: a.description ?? '',
  }
}

function close() {
  creating.value = false
  editing.value = null
  form.value = emptyApp()
}

const canSave = computed(() => !!form.value.app_id?.trim() && !!form.value.name?.trim())

async function save() {
  if (!canSave.value) return
  saving.value = true
  try {
    // 등록 행이 있으면 수정, 없으면(코드 앱을 처음 채우는 경우 포함) 새로 등록한다.
    const pk = editing.value?.id ?? null
    if (pk !== null) {
      // kind·app_id는 코드 카탈로그로 가는 연결 키라 수정 대상이 아니다.
      const { kind: _k, app_id: _a, id: _i, in_code: _c, icon_url: _iu, updated_at: _u,
        ...patch } = form.value
      await opsApi.updateApp(pk, patch)
    } else {
      const { id: _i, in_code: _c, icon_url: _iu, updated_at: _u, ...body } = form.value
      await opsApi.createApp(body)
    }
    close()
    await load()
  } catch (e) {
    error.value = e
  } finally {
    saving.value = false
  }
}

/** 아이콘 업로드. 이름은 서버가 정하고, 방금 올린 파일을 폼에 바로 물린다. */
async function uploadIcon(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  uploadingIcon.value = true
  error.value = null
  try {
    const before = new Set(iconFiles.value)
    iconFiles.value = await opsApi.uploadAppIcon(file)
    const added = iconFiles.value.find((f) => !before.has(f))
    if (added) form.value.icon_file = added
  } catch (e) {
    error.value = e
  } finally {
    uploadingIcon.value = false
    input.value = '' // 같은 파일을 다시 골라도 change가 나게 비운다
  }
}

async function remove(a: AppCatalog) {
  if (a.id === null) return
  const tail = a.in_code
    ? '앱은 코드 카탈로그에 있어 계속 표시되고, 이름·설명이 코드 값으로 돌아갑니다.'
    : '이 앱은 코드에 없어 목록에서 사라집니다.'
  if (!confirm(`${a.name} 등록 정보를 삭제할까요?\n${tail}`)) return
  try {
    await opsApi.removeApp(a.id)
    if (editing.value?.id === a.id) close()
    await load()
  } catch (e) {
    error.value = e
  }
}

</script>

<template>
  <PageHead
    title="앱 관리"
    :crumbs="['HPC Portal Admin', '운영', '앱 관리']"
    sub="인터랙티브 앱·해석 solver의 아이콘·벤더·버전·이미지 정보"
  >
    <template #actions>
      <Btn variant="primary" @click="openCreate">＋ 앱 등록</Btn>
    </template>
  </PageHead>

  <ErrorNote :error="error" />
  <div v-if="notice" class="px-3.5 py-2.5 rounded-lg bg-ok-bg text-ok text-[14px] mb-4">{{ notice }}</div>

  <Card title="등록된 앱" flush>
    <template #title-extra><Fid id="A-OP-02" /></template>
    <p class="px-4 pt-4 text-[13px] text-ink-3">
      앱의 <b>정보</b>를 관리합니다 — 아이콘·벤더·버전·이미지 위치·설명.
      기동 스크립트·파라미터 스키마 같은 <b>실행 방식은 코드 카탈로그가 정본</b>이라 여기서 바꾸지 않습니다.
      <code class="mono">종류 + 앱 ID</code>로 코드의 앱과 이어집니다.
      아래 목록에는 <b>코드 카탈로그의 앱이 모두 나옵니다</b> — <b>정보 미등록</b>인 앱도 이미 동작 중이고,
      여기서 정보를 채우면 사용자 런처 카드에 아이콘·벤더·버전이 붙습니다.
    </p>

    <Empty v-if="!apps.length" :text="loading ? '불러오는 중…' : '앱이 없습니다.'" />
    <Table
      v-else
      :columns="[
        { key: 'icon', label: '아이콘', width: '80px' },
        { key: 'app', label: '앱' },
        { key: 'vendor', label: '벤더' },
        { key: 'ver', label: '버전', width: '90px' },
        { key: 'img', label: '이미지 파일' },
        { key: 'act', label: '', width: '210px' },
      ]"
    >
      <!-- 미등록 앱은 id가 없다 — 업무 키인 종류+앱 ID를 키로 쓴다 -->
      <tr v-for="a in apps" :key="`${a.kind}/${a.app_id}`" class="border-b border-line last:border-0">
        <td class="px-3.5 py-2.5">
          <img v-if="a.icon_url" :src="a.icon_url" :alt="a.name" class="w-8 h-8 rounded object-contain" />
          <span v-else class="text-ink-3 text-[13px]">—</span>
        </td>
        <td class="px-3.5 py-2.5">
          <b>{{ a.name }}</b>
          <Chip class="ml-1.5">{{ a.kind }}</Chip>
          <!-- 등록 여부를 한눈에 — 미등록 앱도 코드 카탈로그로 이미 동작 중이다 -->
          <Chip v-if="a.id === null" tone="gray" class="ml-1">정보 미등록</Chip>
          <Chip v-else-if="!a.in_code" tone="gray" class="ml-1">코드에 없음</Chip>
          <p class="mono text-[12.5px] text-ink-3">{{ a.app_id }}</p>
          <p v-if="a.description" class="text-[13px] text-ink-3">{{ a.description }}</p>
        </td>
        <td class="px-3.5 py-2.5">{{ a.vendor || '—' }}</td>
        <td class="px-3.5 py-2.5 mono text-[13.5px]">{{ a.version || '—' }}</td>
        <td class="px-3.5 py-2.5 mono text-[13px] break-all">
          {{ a.image_file || '—' }}
          <!-- 출처는 파일명보다 길다 — 아래 줄에 흐리게 붙인다 -->
          <p v-if="a.image_ref" class="text-[12px] text-ink-3">{{ a.image_ref }}</p>
        </td>
        <td class="px-3.5 py-2.5 flex gap-2">
          <Btn size="sm" @click="openEdit(a)">{{ a.id === null ? '정보 입력' : '수정' }}</Btn>
          <!-- 출처를 아는 앱만 변환할 수 있다 — 없으면 무엇을 받아올지 모른다 -->
          <Btn v-if="a.image_ref" size="sm" @click="openConvert(a)">변환</Btn>
          <Btn v-if="a.id !== null" size="sm" variant="danger" @click="remove(a)">삭제</Btn>
        </td>
      </tr>
    </Table>
    <template #foot>
      실행 방식은 <span class="mono">session_apps.py</span>·<span class="mono">batch_apps.py</span>가
      정본입니다. 앱을 새로 <b>동작</b>하게 하려면 코드 배포가 따라옵니다.
    </template>
  </Card>

  <!-- 추가·수정은 같은 모달을 쓴다. 다른 점은 연결 키(종류·앱 ID)를 잠그는지 뿐이다. -->
  <Modal
    v-if="open"
    :title="editing ? (editing.id === null ? `정보 입력 — ${editing.name}` : `앱 수정 — ${editing.name}`) : '앱 등록'"
    wide
    @close="close"
  >
    <template #title-extra><Fid id="A-OP-02" /></template>

    <ErrorNote :error="error" class="mb-4" />

    <div class="grid sm:grid-cols-2 gap-4">
      <!-- 연결 키는 수정할 수 없다 — 바꾸면 코드의 앱과 이어지던 줄이 끊긴다 -->
      <Field
        label="종류" required
        :hint="editing ? '연결 키라 수정할 수 없습니다.' : '코드 카탈로그의 어느 목록과 이어질지 정합니다.'"
      >
        <select
          v-model="form.kind" :disabled="!!editing"
          :class="[inputClass, editing ? 'bg-bg text-ink-3' : '']"
        >
          <option value="interactive">interactive — 인터랙티브 앱</option>
          <option value="batch">batch — 해석 solver</option>
        </select>
      </Field>
      <Field
        label="앱 ID" required
        :hint="editing ? '연결 키라 수정할 수 없습니다.' : '코드 카탈로그의 id와 같아야 이어집니다.'"
      >
        <input
          v-model="form.app_id" :disabled="!!editing"
          :class="[inputClass, 'mono', editing ? 'bg-bg text-ink-3' : '']" placeholder="jupyter"
        />
      </Field>

      <Field label="앱 이름" required>
        <input v-model="form.name" :class="inputClass" placeholder="JupyterLab" />
      </Field>
      <Field label="벤더">
        <input v-model="form.vendor" :class="inputClass" placeholder="Project Jupyter" />
      </Field>
      <Field label="버전">
        <input v-model="form.version" :class="[inputClass, 'mono']" placeholder="4.2" />
      </Field>

      <Field
        label="컨테이너 이미지 파일" full
        hint="변환 결과가 저장될 이름. 목록은 클러스터에 이미 있는 SIF(전 클러스터 합집합)이고, 새 이름을 직접 써도 됩니다. 비우면 코드 카탈로그의 기본 이미지를 씁니다."
      >
        <!--
          **드롭다운이면 안 된다.** 새 버전의 첫 빌드는 아직 없는 파일명을 적어야 하는데,
          고르기만 가능하면 그 이름을 넣을 방법이 없어 변환 경로가 막힌다.
        -->
        <input
          v-model="form.image_file"
          list="app-image-files"
          :class="[inputClass, 'mono']"
          placeholder="예: rocky9-mate-1.5.sif"
        />
        <datalist id="app-image-files">
          <option v-for="f in imageFiles" :key="f" :value="f" />
        </datalist>
      </Field>

      <Field
        label="이미지 출처 (OCI 참조)" full
        hint="예: docker://opencfd/openfoam-default:2512 — 이 SIF를 무엇으로 만들었는지. 스킴(docker:// 등)이 필요합니다."
      >
        <input
          v-model="form.image_ref"
          :class="[inputClass, 'mono']"
          placeholder="docker://…"
          @blur="onRefInput"
        />
      </Field>

      <Field
        label="아이콘 파일" full
        hint="SVG·PNG·JPEG·WEBP, 512KB 이하. 파일명은 서버가 정하고 같은 이름이 있으면 뒤에 번호를 붙입니다."
      >
        <div class="flex items-center gap-2">
          <select v-model="form.icon_file" :class="[inputClass, 'mono']">
            <option value="">(없음)</option>
            <option v-for="f in iconFiles" :key="f" :value="f">{{ f }}</option>
          </select>
          <!-- input[type=file]은 스타일을 못 입혀서 label로 감싸 버튼처럼 보이게 한다 -->
          <label
            class="shrink-0 inline-flex items-center px-3.5 py-2 rounded-lg border border-line-dark
                   bg-surface text-ink-2 text-[14.5px] font-semibold cursor-pointer hover:bg-bg
                   whitespace-nowrap"
            :class="uploadingIcon ? 'opacity-45 cursor-not-allowed' : ''"
          >
            {{ uploadingIcon ? '올리는 중…' : '＋ 업로드' }}
            <input
              type="file" class="hidden" accept="image/svg+xml,image/png,image/jpeg,image/webp"
              :disabled="uploadingIcon" @change="uploadIcon"
            />
          </label>
          <img
            v-if="form.icon_file" :src="`/api/v1/app-icons/${form.icon_file}`" alt=""
            class="w-8 h-8 rounded object-contain shrink-0"
          />
        </div>
      </Field>

      <Field label="설명" full>
        <input v-model="form.description" :class="inputClass" />
      </Field>
    </div>

    <template #foot>
      <Btn @click="close">취소</Btn>
      <Btn variant="primary" :disabled="!canSave || saving" @click="save">
        {{ saving ? '저장 중…' : editing ? (editing.id === null ? '정보 등록' : '수정 저장') : '등록' }}
      </Btn>
    </template>
  </Modal>

  <!--
    변환 모달. **두 걸음**이다 — 빌드(Slurm 잡)와 배치(포털이 sudo로 하는 mv).
    목적지가 root 소유인 이유는 컨테이너 이미지가 **모든 사용자가 실행하는 코드**여서다:
    디렉터리를 사용자 그룹에 열면 아무나 남이 실행할 이미지를 바꿔 놓을 수 있다.
  -->
  <Modal
    v-if="converting"
    :title="`이미지 변환 — ${converting.name}`"
    @close="converting = null"
  >
    <div class="space-y-4">
      <p class="text-[13.5px] text-ink-2 leading-relaxed">
        <b class="mono break-all">{{ converting.image_ref }}</b> 를 받아
        <b class="mono">{{ converting.image_file || '(파일명 미지정)' }}</b> 로 만듭니다.
      </p>
      <Field label="대상 클러스터" full hint="이미지는 클러스터마다 따로 있어야 합니다.">
        <select v-model.number="convertCluster" :class="inputClass">
          <option v-for="c in clusters" :key="c.id" :value="c.id">{{ clusterLabel(c) }}</option>
        </select>
      </Field>
      <div class="px-3.5 py-2.5 rounded-lg bg-info-bg text-[13px] text-ink-2 leading-relaxed">
        <b>① 빌드</b>는 Slurm 잡으로 돌고 결과가 <b>내 홈</b>에 떨어집니다 — 진행 상황은
        Job 화면에서 봅니다. 큰 이미지는 몇 분에서 수십 분 걸립니다.<br />
        <b>② 배치</b>는 잡이 <b>끝난 뒤에</b> 누르세요. 그때 포털이 이미지 디렉터리로 옮깁니다.
      </div>
    </div>
    <template #foot>
      <Btn @click="converting = null">닫기</Btn>
      <Btn :disabled="convertBusy || convertCluster === null" @click="runBuild">① 빌드</Btn>
      <Btn
        variant="primary"
        :disabled="convertBusy || convertCluster === null"
        @click="runInstall"
      >
        ② 배치
      </Btn>
    </template>
  </Modal>
</template>
