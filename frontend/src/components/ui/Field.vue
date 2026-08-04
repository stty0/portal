<script setup lang="ts">
defineProps<{ label: string; hint?: string; required?: boolean; full?: boolean }>()
</script>

<template>
  <div :class="full ? 'sm:col-span-2' : ''">
    <label class="block text-[13px] font-semibold text-ink-2 mb-1.5">
      {{ label }}<span v-if="required" class="text-err ml-0.5">*</span>
    </label>
    <slot />
    <p v-if="hint" class="mt-1 text-[12.5px] text-ink-3">{{ hint }}</p>
  </div>
</template>
