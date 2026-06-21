<template>
  <div
    class="flex w-full min-w-0 items-center gap-3 rounded px-2 py-2 text-base font-medium text-ink-gray-8"
    :class="{ 'bg-surface-gray-2': active }"
  >
    <span
      v-if="item.icon"
      :class="item.icon"
      class="size-4 shrink-0 text-ink-gray-6"
      aria-hidden="true"
    />
    <span class="overflow-hidden text-ellipsis whitespace-nowrap">{{ item.title }}</span>
    <span
      v-if="item.description"
      class="ml-auto shrink-0 whitespace-nowrap pl-2 text-sm text-ink-gray-5"
    >
      {{ item.description }}
    </span>
  </div>
</template>

<script setup>
// Item renderer for the frappe-ui CommandPalette. The packaged CommandPaletteItem
// renders icons as Vue components; this app's icons are lucide CSS mask classes, so
// we render them as a <span :class> instead — keeping palette icons consistent with
// the sidebar and the rest of the console.
defineProps({
  item: { type: Object, required: true },
  active: { type: Boolean, default: false },
});
</script>
