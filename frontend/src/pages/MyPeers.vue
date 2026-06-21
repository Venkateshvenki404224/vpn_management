<template>
	<AppShell>
		<div class="mb-5 flex items-center justify-between gap-4">
			<div>
				<h1 class="text-lg font-semibold text-ink-gray-9">My Peers</h1>
				<p class="text-sm text-ink-gray-5">
					Download a config or scan the QR to connect a device.
				</p>
			</div>
			<Button
				label="Refresh"
				icon-left="lucide-refresh-cw"
				:loading="peers.loading"
				@click="peers.reload()"
			/>
		</div>

		<EndpointWarning />

		<div v-if="peers.loading && !rows.length" class="flex justify-center py-16">
			<LoadingIndicator class="size-6 text-ink-gray-5" />
		</div>
		<EmptyState
			v-else-if="!rows.length"
			icon="lucide-inbox"
			title="No VPN configurations yet"
			description="Once an administrator provisions a peer for you, it will appear here."
		/>
		<PeerTable v-else :peers="rows" show-actions @show-qr="openQr" />

		<QrDialog v-model:open="qrOpen" :peer="qrPeer" />
	</AppShell>
</template>

<script setup>
import { Button, LoadingIndicator, createResource } from "frappe-ui";
import { computed, onUnmounted, ref } from "vue";
import AppShell from "@/components/AppShell.vue";
import EmptyState from "@/components/EmptyState.vue";
import EndpointWarning from "@/components/EndpointWarning.vue";
import PeerTable from "@/components/PeerTable.vue";
import QrDialog from "@/components/QrDialog.vue";

const peers = createResource({
	url: "vpn_management.api.list_peers",
	method: "GET", // the endpoint is whitelisted GET-only; createResource defaults to POST
	params: { limit: 100 },
	auto: true,
});
const rows = computed(() => peers.data || []);

const qrOpen = ref(false);
const qrPeer = ref(null);
function openQr(peer) {
	qrPeer.value = peer;
	qrOpen.value = true;
}

// Poll so live handshake/transfer stays fresh; cleared on unmount.
const interval = setInterval(() => peers.reload(), 30000);
onUnmounted(() => clearInterval(interval));
</script>
