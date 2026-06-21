<template>
	<Dialog v-model:open="open" :options="{ title: 'Scan to connect' }">
		<template #body-content>
			<div class="flex flex-col items-center gap-3">
				<img
					v-if="peer"
					:src="qrUrl"
					:alt="`QR code for ${peer.peer_name}`"
					class="size-64 rounded-md border border-outline-gray-2 bg-surface-white p-2"
				/>
				<p class="text-center text-sm text-ink-gray-6">
					Open WireGuard on your device and scan this code to import
					<span class="font-medium text-ink-gray-8">{{ peer?.peer_name }}</span
					>.
				</p>
			</div>
		</template>
	</Dialog>
</template>

<script setup>
import { Dialog } from "frappe-ui";
import { computed } from "vue";

const open = defineModel("open", { type: Boolean, default: false });
const props = defineProps({
	peer: { type: Object, default: null },
});

// Same-origin GET: the session cookie authenticates the inline image request,
// so no fetch + blob is needed.
const qrUrl = computed(() =>
	props.peer
		? `/api/method/vpn_management.api.my_config_qr?name=${encodeURIComponent(props.peer.name)}`
		: ""
);
</script>
