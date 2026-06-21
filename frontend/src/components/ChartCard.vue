<template>
  <div class="flex flex-col rounded-lg border border-outline-gray-2 bg-surface-white">
    <!-- Header: title + optional subtitle, with an action slot on the right. -->
    <div
      class="flex items-start justify-between gap-3 border-b border-outline-gray-1 px-4 py-3"
    >
      <div>
        <h3 class="text-base font-semibold text-ink-gray-8">{{ title }}</h3>
        <p v-if="subtitle" class="mt-0.5 text-xs text-ink-gray-5">{{ subtitle }}</p>
      </div>
      <slot name="action" />
    </div>

    <!-- Body keeps a fixed height so the card never collapses or jumps between
         loading, empty, and charted states (the chart fills it via h-full). -->
    <div class="flex-1" :style="{ height: bodyHeight }">
      <div v-if="loading" class="flex h-full items-center justify-center">
        <LoadingIndicator class="size-6 text-ink-gray-4" />
      </div>
      <div v-else-if="empty" class="flex h-full items-center justify-center">
        <slot name="empty">
          <div class="flex flex-col items-center gap-2 px-6 py-8 text-center">
            <div
              class="flex size-12 items-center justify-center rounded-full bg-surface-gray-2 text-ink-gray-4"
            >
              <span :class="[emptyIcon, 'size-6']" aria-hidden="true" />
            </div>
            <p class="text-sm font-medium text-ink-gray-6">{{ emptyTitle }}</p>
            <p v-if="emptyDescription" class="max-w-xs text-xs text-ink-gray-5">
              {{ emptyDescription }}
            </p>
          </div>
        </slot>
      </div>
      <div v-else class="h-full">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup>
import { LoadingIndicator } from "frappe-ui";

// A titled card that wraps a chart and shows a styled placeholder (not a blank
// box) when there's no data. Colors come from espresso tokens only so it flips
// cleanly between light and dark.
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: "" },
  // Show the placeholder instead of the chart slot (e.g. no rows to plot).
  empty: { type: Boolean, default: false },
  loading: { type: Boolean, default: false },
  emptyIcon: { type: String, default: "lucide-chart-pie" },
  emptyTitle: { type: String, default: "No data yet" },
  emptyDescription: { type: String, default: "" },
  // Charts (ECharts) need a definite height to render; default fits a donut.
  bodyHeight: { type: String, default: "20rem" },
});
</script>
