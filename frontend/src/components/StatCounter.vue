<template>
  <div class="rounded-lg border border-outline-gray-2 bg-surface-white px-4 py-3">
    <div class="text-2xl font-semibold tabular-nums" :class="toneClass">
      {{ value }}
    </div>
    <div class="mt-0.5 text-sm text-ink-gray-5">{{ label }}</div>
  </div>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: 0 },
  // Color encodes peer state; "neutral" for plain totals (color = state only).
  tone: { type: String, default: "neutral" },
});

const TONES = {
  neutral: "text-ink-gray-9",
  green: "text-ink-green-3",
  amber: "text-ink-amber-3",
  red: "text-ink-red-3",
  blue: "text-ink-blue-3",
};

const toneClass = computed(() => TONES[props.tone] || TONES.neutral);
</script>
