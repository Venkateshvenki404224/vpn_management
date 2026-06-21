<template>
  <Tooltip :text="tooltip">
    <span class="inline-flex items-center gap-1.5">
      <span class="relative flex size-2 shrink-0">
        <span
          v-if="online"
          class="absolute inline-flex h-full w-full animate-ping rounded-full bg-surface-green-3 opacity-75"
          aria-hidden="true"
        />
        <span
          class="relative inline-flex size-2 rounded-full"
          :class="online ? 'bg-surface-green-3' : 'bg-surface-gray-4'"
          aria-hidden="true"
        />
      </span>
      <span
        class="text-xs font-medium"
        :class="online ? 'text-ink-green-3' : 'text-ink-gray-5'"
        >{{ online ? "Online" : "Offline" }}</span
      >
    </span>
  </Tooltip>
</template>

<script setup>
import { Tooltip } from "frappe-ui";
import { computed } from "vue";
import { relativeTime } from "@/utils/format";

const props = defineProps({
  lastHandshake: { type: String, default: null },
  // A peer is "Online" while its handshake is fresher than this. The default
  // mirrors VPN Settings `status_poll_interval_min` (5 min), so the dot agrees
  // with the Active/Stale status the backend poll computes from the same window.
  staleSeconds: { type: Number, default: 300 },
});

const online = computed(() => {
  if (!props.lastHandshake) return false;
  const then = new Date(String(props.lastHandshake).replace(" ", "T"));
  if (Number.isNaN(then.getTime())) return false;
  return (Date.now() - then.getTime()) / 1000 <= props.staleSeconds;
});

const tooltip = computed(() => {
  if (!props.lastHandshake) return "No handshake yet";
  const ago = relativeTime(props.lastHandshake);
  return online.value ? `Online · handshake ${ago}` : `Offline · last seen ${ago}`;
});
</script>
