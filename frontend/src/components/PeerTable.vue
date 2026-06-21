<template>
	<div class="overflow-x-auto rounded-lg border border-outline-gray-2 bg-surface-white">
		<table class="w-full text-left text-sm">
			<thead class="border-b border-outline-gray-2 text-ink-gray-5">
				<tr>
					<th class="whitespace-nowrap px-4 py-2.5 font-medium">Peer</th>
					<th v-if="showOwner" class="px-4 py-2.5 font-medium">Owner</th>
					<th class="px-4 py-2.5 font-medium">Server</th>
					<th class="px-4 py-2.5 font-medium">Address</th>
					<th class="px-4 py-2.5 font-medium">Status</th>
					<th class="whitespace-nowrap px-4 py-2.5 font-medium">Last handshake</th>
					<th class="px-4 py-2.5 font-medium">Transfer</th>
					<th v-if="showActions" class="px-4 py-2.5"></th>
				</tr>
			</thead>
			<tbody class="divide-y divide-outline-gray-2 text-ink-gray-8">
				<tr v-for="peer in peers" :key="peer.name">
					<td class="whitespace-nowrap px-4 py-3 font-medium text-ink-gray-9">
						{{ peer.peer_name }}
					</td>
					<td v-if="showOwner" class="whitespace-nowrap px-4 py-3 text-ink-gray-6">
						{{ peer.owner_user }}
					</td>
					<td class="whitespace-nowrap px-4 py-3 font-mono text-ink-gray-7">
						{{ peer.server }}
					</td>
					<td class="whitespace-nowrap px-4 py-3 font-mono text-ink-gray-7">
						{{ peer.assigned_ip || "—" }}
					</td>
					<td class="px-4 py-3"><StatusBadge :status="peer.status" /></td>
					<td class="whitespace-nowrap px-4 py-3 text-ink-gray-6">
						{{ relativeTime(peer.last_handshake) }}
					</td>
					<td class="whitespace-nowrap px-4 py-3 text-ink-gray-6">
						↓ {{ humanBytes(peer.rx_bytes) }} · ↑ {{ humanBytes(peer.tx_bytes) }}
					</td>
					<td v-if="showActions" class="px-4 py-3">
						<PeerActions :peer="peer" @show-qr="(p) => emit('show-qr', p)" />
					</td>
				</tr>
			</tbody>
		</table>
	</div>
</template>

<script setup>
import PeerActions from "@/components/PeerActions.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { humanBytes, relativeTime } from "@/utils/format";

defineProps({
	peers: { type: Array, default: () => [] },
	showOwner: { type: Boolean, default: false },
	showActions: { type: Boolean, default: false },
});
const emit = defineEmits(["show-qr"]);
</script>
