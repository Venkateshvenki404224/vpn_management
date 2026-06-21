<template>
	<div
		class="flex flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-outline-gray-2 bg-surface-white px-6 py-16 text-center"
	>
		<span v-if="icon" :class="[icon, 'size-7 text-ink-gray-4']" aria-hidden="true" />
		<p class="text-base font-medium text-ink-gray-7">{{ title }}</p>
		<p v-if="description" class="max-w-sm text-sm text-ink-gray-5">
			{{ description }}
		</p>
		<div v-if="$slots.default" class="mt-3"><slot /></div>
	</div>
</template>

<script setup>
defineProps({
	title: { type: String, required: true },
	description: { type: String, default: "" },
	icon: { type: String, default: "" },
});
</script>
