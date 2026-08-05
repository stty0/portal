<script setup lang="ts">
defineProps<{ columns: { key: string; label: string; num?: boolean; width?: string }[] }>()
</script>

<template>
  <div class="overflow-x-auto">
    <table class="w-full border-collapse text-[14.5px]">
      <thead>
        <tr class="bg-bg">
          <th
            v-for="c in columns"
            :key="c.key"
            class="px-3.5 py-2.5 font-semibold text-ink-3 text-[13px] border-b border-line whitespace-nowrap"
            :class="c.num ? 'text-right' : 'text-left'"
            :style="c.width ? { width: c.width } : undefined"
          >{{ c.label }}</th>
        </tr>
      </thead>
      <tbody><slot /></tbody>
    </table>
  </div>
</template>
