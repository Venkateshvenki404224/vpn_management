<template>
  <div
    class="overflow-x-auto rounded-lg border border-outline-gray-2 bg-surface-white"
  >
    <table class="w-full text-left text-sm">
      <thead class="border-b border-outline-gray-2 text-ink-gray-5">
        <tr>
          <th class="px-4 py-2.5 font-medium">Action</th>
          <th class="px-4 py-2.5 font-medium">Target</th>
          <th class="px-4 py-2.5 font-medium">Result</th>
          <th class="px-4 py-2.5 font-medium">By</th>
          <th class="whitespace-nowrap px-4 py-2.5 font-medium">When</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-outline-gray-2 text-ink-gray-8">
        <tr v-for="row in rows" :key="row.name">
          <td class="whitespace-nowrap px-4 py-3 font-medium text-ink-gray-9">
            {{ row.action }}
          </td>
          <td class="whitespace-nowrap px-4 py-3 font-mono text-ink-gray-7">
            {{ row.target }}
          </td>
          <td class="px-4 py-3">
            <Badge
              :theme="resultTheme(row.result)"
              :label="row.result"
              variant="subtle"
            />
          </td>
          <td class="whitespace-nowrap px-4 py-3 text-ink-gray-6">
            {{ row.actor }}
          </td>
          <td class="whitespace-nowrap px-4 py-3 text-ink-gray-6">
            {{ relativeTime(row.creation) }}
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup>
import { Badge } from "frappe-ui";
import { relativeTime } from "@/utils/format";

defineProps({
  rows: { type: Array, default: () => [] },
});

const RESULT_THEMES = {
  success: "green",
  failure: "red",
  error: "red",
  skipped: "gray",
};

function resultTheme(result) {
  return RESULT_THEMES[result] || "gray";
}
</script>
