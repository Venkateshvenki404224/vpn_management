<template>
  <div
    class="overflow-x-auto rounded-lg border border-outline-gray-2 bg-surface-white p-2"
  >
    <ListView :columns="columns" :rows="rows" row-key="name" :options="options">
      <template #cell="{ column, row }">
        <span
          v-if="column.key === 'action'"
          class="truncate font-medium text-ink-gray-9"
          >{{ humanize(row.action) }}</span
        >
        <span
          v-else-if="column.key === 'target'"
          class="truncate font-mono text-ink-gray-7"
          >{{ row.target || "—" }}</span
        >
        <Badge
          v-else-if="column.key === 'result'"
          :theme="resultTheme(row.result)"
          :label="row.result"
          variant="subtle"
        />
        <span
          v-else-if="column.key === 'actor'"
          class="truncate text-ink-gray-6"
          >{{ row.actor }}</span
        >
        <span
          v-else-if="column.key === 'creation'"
          class="truncate text-ink-gray-6"
          :title="absoluteTime(row.creation)"
          >{{ relativeTime(row.creation) }}</span
        >
      </template>
    </ListView>
  </div>
</template>

<script setup>
import { Badge, ListView } from "frappe-ui";
import { absoluteTime, relativeTime } from "@/utils/format";

defineProps({
  rows: { type: Array, default: () => [] },
});

const options = { selectable: false, showTooltip: false, rowHeight: 44 };

const columns = [
  { label: "Action", key: "action", width: 1.2 },
  { label: "Target", key: "target", width: 1 },
  { label: "Result", key: "result", width: 0.7 },
  { label: "By", key: "actor", width: 1.2 },
  { label: "When", key: "creation", width: 0.9 },
];

const RESULT_THEMES = {
  success: "green",
  failure: "red",
  error: "red",
  skipped: "gray",
};

function resultTheme(result) {
  return RESULT_THEMES[result] || "gray";
}

// "key_rotation" → "Key rotation" so the audit verbs read as plain English.
function humanize(action) {
  if (!action) return "";
  const spaced = action.replaceAll("_", " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}
</script>
