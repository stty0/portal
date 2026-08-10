<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
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
const loading = ref(false)
const uploadingIcon = ref(false)
const saving = ref(false)

/** 모달 상태. `null`이면 닫힘. */
const editing = ref<AppCatalog | null>(null)
const creating = ref(false)
const open = computed(() => creating.value || editing.value !== null)

const emptyApp = (): Partial<AppCatalog> => ({
  kind: 'interactive', app_id: '', name: '', vendor: '', version: '',
  image_file: '', icon_file: '', description: '',
})
const form = ref<Partial<AppCatalog>>(emptyApp())

async function load() {
  loading.value = true
  try {
    const [list, icons, images] = await Promise.all([
      opsApi.apps(), opsApi.appIcons(), opsApi.appImages(),
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
        { key: 'act', label: '', width: '150px' },
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
        <td class="px-3.5 py-2.5 mono text-[13px] break-all">{{ a.image_file || '—' }}</td>
        <td class="px-3.5 py-2.5 flex gap-2">
          <Btn size="sm" @click="openEdit(a)">{{ a.id === null ? '정보 입력' : '수정' }}</Btn>
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
        hint="서버의 공용 이미지 디렉터리에 있는 SIF 파일. 비우면 코드 카탈로그의 기본 이미지를 씁니다."
      >
        <select v-model="form.image_file" :class="[inputClass, 'mono']">
          <option value="">(코드 기본값 사용)</option>
          <option v-for="f in imageFiles" :key="f" :value="f">{{ f }}</option>
        </select>
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
</template>
