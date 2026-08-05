<script lang="ts">
// 모달이 겹쳐 열릴 수 있으므로(예: 클러스터 폼 위의 자격증명 모달) 열린 순서를 추적한다.
// 인스턴스가 아니라 모듈 스코프여야 모든 모달이 같은 스택을 공유한다.
const stack: symbol[] = []
</script>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

const props = defineProps<{ title: string; wide?: boolean }>()
const emit = defineEmits<{ close: [] }>()

const token = Symbol('modal')

// ESC 닫기 — 정적 프로토타입의 모달 규약과 동일하게 유지하되, 최상단 모달만 닫는다.
function onKey(e: KeyboardEvent) {
  if (e.key === 'Escape' && stack[stack.length - 1] === token) emit('close')
}
onMounted(() => {
  stack.push(token)
  document.addEventListener('keydown', onKey)
})
onUnmounted(() => {
  stack.splice(stack.indexOf(token), 1)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div
    class="fixed inset-0 z-50 bg-black/35 flex items-start justify-center p-6 overflow-y-auto"
    @click.self="emit('close')"
  >
    <div
      class="bg-surface rounded-card shadow-pop w-full mt-[6vh]"
      :class="props.wide ? 'max-w-4xl' : 'max-w-xl'"
      role="dialog"
      aria-modal="true"
    >
      <header class="flex items-center gap-2 px-5 py-3.5 border-b border-line">
        <h3 class="flex-1 text-[16px] font-semibold text-ink flex items-center gap-2">
          {{ title }}<slot name="title-extra" />
        </h3>
        <button
          class="w-7 h-7 rounded-md text-ink-3 hover:bg-bg text-[19px] leading-none"
          aria-label="닫기"
          @click="emit('close')"
        >✕</button>
      </header>
      <div class="p-5 max-h-[70vh] overflow-y-auto"><slot /></div>
      <footer v-if="$slots.foot" class="flex justify-end gap-2 px-5 py-3.5 border-t border-line">
        <slot name="foot" />
      </footer>
    </div>
  </div>
</template>
