<template>
  <div class="space-y-4">
    <!-- Legend doubles as the summary: each swatch matches a cell colour. -->
    <div class="flex flex-wrap items-center gap-4 text-sm text-ink-gray-7">
      <span class="flex items-center gap-1.5">
        <span class="size-3 rounded-sm border border-outline-green-2 bg-surface-green-2" />
        Free · {{ summary.free }}
      </span>
      <span class="flex items-center gap-1.5">
        <span class="size-3 rounded-sm border border-outline-blue-2 bg-surface-blue-2" />
        Allocated · {{ summary.allocated }}
      </span>
      <span class="flex items-center gap-1.5">
        <span class="size-3 rounded-sm border border-outline-amber-2 bg-surface-amber-2" />
        Reserved · {{ summary.reserved }}
      </span>
      <span class="text-ink-gray-5">Total · {{ summary.total }}</span>
    </div>

    <div class="flex flex-wrap gap-1">
      <div
        v-for="row in rows"
        :key="row.name"
        :title="cellTip(row)"
        class="size-5 rounded-sm border"
        :class="cellClass(row)"
      />
    </div>

    <p v-if="truncated" class="text-xs text-ink-gray-5">
      Showing the first {{ rows.length }} of {{ summary.total }} addresses.
    </p>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  rows: { type: Array, default: () => [] },
  summary: {
    type: Object,
    default: () => ({ total: 0, allocated: 0, reserved: 0, free: 0 }),
  },
});

const truncated = computed(() => props.summary.total > props.rows.length);

function cellClass(row) {
  if (row.allocated) return "border-outline-blue-2 bg-surface-blue-2";
  if (row.reserved) return "border-outline-amber-2 bg-surface-amber-2";
  return "border-outline-green-2 bg-surface-green-2";
}

function cellTip(row) {
  if (row.allocated) return `${row.ip_address} · ${row.peer || "allocated"}`;
  if (row.reserved) return `${row.ip_address} · reserved`;
  return `${row.ip_address} · free`;
}
</script>
