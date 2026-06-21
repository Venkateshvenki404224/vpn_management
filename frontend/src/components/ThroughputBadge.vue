<template>
  <span
    class="inline-flex items-center gap-2 whitespace-nowrap text-xs text-ink-gray-6"
  >
    <Tooltip text="Received (download)">
      <span class="inline-flex items-center gap-1">
        <span class="lucide-arrow-down size-3 text-ink-green-3" aria-hidden="true" />
        <span class="font-mono tabular-nums">{{ humanBytes(rxBytes) }}</span>
      </span>
    </Tooltip>
    <Tooltip text="Sent (upload)">
      <span class="inline-flex items-center gap-1">
        <span class="lucide-arrow-up size-3 text-ink-blue-3" aria-hidden="true" />
        <span class="font-mono tabular-nums">{{ humanBytes(txBytes) }}</span>
      </span>
    </Tooltip>
  </span>
</template>

<script setup>
import { Tooltip } from "frappe-ui";
import { humanBytes } from "@/utils/format";

defineProps({
  rxBytes: { type: [Number, String], default: 0 },
  txBytes: { type: [Number, String], default: 0 },
});
</script>
