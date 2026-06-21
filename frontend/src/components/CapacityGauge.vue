<template>
  <div
    class="gauge flex h-full flex-col items-center justify-center gap-4 px-4 py-2"
  >
    <CircularProgressBar
      :step="gaugeStep"
      :total-steps="GAUGE_STEPS"
      :theme="band"
      size="xl"
      show-percentage
    />
    <div class="flex flex-col items-center gap-1.5 text-center">
      <Badge
        v-if="nearCapacity"
        theme="red"
        variant="subtle"
        label="Near capacity"
      />
      <p class="text-sm font-medium text-ink-gray-7">
        {{ used }} of {{ pool.total }} addresses used
      </p>
      <p class="text-xs text-ink-gray-5">
        {{ pool.allocated }} allocated · {{ pool.reserved }} reserved ·
        {{ pool.free }} free
      </p>
    </div>
  </div>
</template>

<script setup>
import { Badge, CircularProgressBar } from "frappe-ui";
import { computed } from "vue";

// Aggregate IP-pool capacity gauge. The wrapper is token-only; the radial widget
// keeps its own palette (green/amber/red band) per the color thresholds below.
const props = defineProps({
  // { total, allocated, reserved, free } from dashboard_summary.ip_pool.
  pool: { type: Object, required: true },
});

// Band thresholds: green below AMBER_AT% used, amber below RED_AT%, red at/above.
const AMBER_AT = 70;
const RED_AT = 90;

// Used = everything not free (allocated + reserved), matching the backend's
// free = total − allocated − reserved so the two never disagree.
const used = computed(() => Math.max(props.pool.total - props.pool.free, 0));
const percent = computed(() =>
  props.pool.total ? (used.value / props.pool.total) * 100 : 0,
);

const band = computed(() => {
  if (percent.value >= RED_AT) return "red";
  if (percent.value >= AMBER_AT) return "orange";
  return "green";
});
const nearCapacity = computed(() => percent.value >= RED_AT);

// CircularProgressBar renders a green "complete" check + lightgreen fill when
// step === totalSteps — which would misread a *full* pool (the worst case) as
// "all good". Scale to 1000 and cap one short of full so a 100%-used pool still
// shows a full red ring labelled "100%", never the green check.
const GAUGE_STEPS = 1000;
const gaugeStep = computed(() =>
  Math.min(Math.round((percent.value / 100) * GAUGE_STEPS), GAUGE_STEPS - 1),
);
</script>

<style scoped>
/* CircularProgressBar hard-codes a white center disc and inherits its label
   color, so in dark mode the (now light) "NN%" text sits on white and vanishes.
   Pin the disc to the card surface token and the label to a strong ink token so
   both flip with the theme and stay legible. (Tokens are "R G B" triples.) */
.gauge :deep(.progressbar::after) {
  background: rgb(var(--surface-white));
}
.gauge :deep(.progressbar p) {
  color: rgb(var(--text-ink-gray-9));
}
</style>
