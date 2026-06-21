<template>
	<div
		class="flex flex-col items-center justify-center gap-1.5 rounded-lg border border-dashed border-outline-gray-2 bg-surface-white px-6 py-16 text-center"
	>
		<span class="lucide-circle-alert size-7 text-ink-red-4" aria-hidden="true" />
		<p class="text-base font-medium text-ink-gray-7">{{ title }}</p>
		<p v-if="message" class="max-w-md text-sm text-ink-gray-5">{{ message }}</p>
		<Button
			v-if="retryable"
			class="mt-3"
			label="Try again"
			icon-left="lucide-refresh-cw"
			@click="emit('retry')"
		/>
	</div>
</template>

<script setup>
import { Button } from "frappe-ui";

// Mirrors EmptyState's framing so loading → empty → error read as one family.
defineProps({
	title: { type: String, default: "Couldn’t load this" },
	message: { type: String, default: "" },
	retryable: { type: Boolean, default: true },
});
const emit = defineEmits(["retry"]);
</script>
