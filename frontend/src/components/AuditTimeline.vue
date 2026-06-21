<template>
  <div
    class="overflow-hidden rounded-lg border border-outline-gray-2 bg-surface-white"
  >
    <ul class="divide-y divide-outline-gray-2">
      <li v-for="row in rows" :key="row.name" class="flex gap-3 px-4 py-3">
        <!-- Headline + meta + (when present) the already-redacted detail block. -->
        <div class="min-w-0 flex-1">
          <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span class="font-medium text-ink-gray-9">{{ actionLabel(row.action) }}</span>
            <span
              v-if="row.target"
              class="truncate font-mono text-xs text-ink-gray-6"
              >{{ row.target }}</span
            >
            <Badge
              :theme="resultTheme(row.result)"
              :label="row.result"
              variant="subtle"
            />
            <span
              class="ml-auto whitespace-nowrap text-xs text-ink-gray-5"
              :title="absoluteTime(row.creation)"
              >{{ relativeTime(row.creation) }}</span
            >
          </div>

          <div
            class="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-ink-gray-5"
          >
            <span class="flex items-center gap-1">
              <span class="lucide-user size-3" aria-hidden="true" />
              {{ row.actor || "system" }}
            </span>
            <span v-if="row.source_ip" class="font-mono">{{ row.source_ip }}</span>
            <span v-if="row.in_use_count_at_run != null"
              >{{ row.in_use_count_at_run }} in use</span
            >
          </div>

          <div
            v-if="row.argv_redacted || row.detail"
            class="mt-2 space-y-1 rounded-md bg-surface-gray-2 px-2.5 py-2 font-mono text-xs text-ink-gray-7"
          >
            <p v-if="row.argv_redacted" class="whitespace-pre-wrap break-all">
              {{ row.argv_redacted }}
            </p>
            <p
              v-if="row.detail"
              class="whitespace-pre-wrap break-all text-ink-gray-6"
            >
              {{ row.detail }}
            </p>
          </div>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { Badge } from "frappe-ui";
import { absoluteTime, relativeTime } from "@/utils/format";

defineProps({
  rows: { type: Array, default: () => [] },
});

const RESULT_THEMES = { success: "green", failure: "red", skipped: "gray" };

function resultTheme(result) {
  return RESULT_THEMES[result] || "gray";
}

// The stored action codes (peer_apply, interface_up, …) read fine to operators;
// just swap underscores for spaces so they sit naturally next to the target.
function actionLabel(action) {
  return (action || "—").replaceAll("_", " ");
}
</script>
