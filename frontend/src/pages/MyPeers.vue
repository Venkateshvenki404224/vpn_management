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

    <ErrorState
      v-if="peers.error"
      :message="errorMessage(peers.error)"
      @retry="peers.reload()"
    />
    <div
      v-else-if="peers.loading && !rows.length"
      class="flex justify-center py-16"
    >
      <LoadingIndicator class="size-6 text-ink-gray-5" />
    </div>
    <EmptyState
      v-else-if="!rows.length"
      icon="lucide-inbox"
      title="No VPN configurations yet"
      description="Once an administrator provisions a peer for you, it will appear here."
    />
    <div v-else class="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <div
        v-for="peer in rows"
        :key="peer.name"
        class="flex flex-col rounded-lg border border-outline-gray-2 bg-surface-white transition-shadow hover:shadow-sm"
      >
        <!-- Header: name + assigned address + status -->
        <div
          class="flex items-start justify-between gap-2 border-b border-outline-gray-1 px-4 py-3"
        >
          <div class="min-w-0">
            <p class="truncate font-medium text-ink-gray-9">
              {{ peer.peer_name }}
            </p>
            <p class="truncate font-mono text-xs text-ink-gray-5">
              {{ peer.assigned_ip || "—" }}
            </p>
          </div>
          <StatusBadge :status="peer.status" />
        </div>

        <!-- Live presence + throughput + server -->
        <dl class="flex-1 space-y-2.5 px-4 py-3 text-sm">
          <div class="flex items-center justify-between gap-2">
            <dt class="text-ink-gray-5">Presence</dt>
            <dd><PresenceDot :last-handshake="peer.last_handshake" /></dd>
          </div>
          <div class="flex items-center justify-between gap-2">
            <dt class="text-ink-gray-5">Transfer</dt>
            <dd>
              <ThroughputBadge :rx-bytes="peer.rx_bytes" :tx-bytes="peer.tx_bytes" />
            </dd>
          </div>
          <div class="flex items-center justify-between gap-2">
            <dt class="text-ink-gray-5">Server</dt>
            <dd class="font-mono text-ink-gray-7">{{ peer.server }}</dd>
          </div>
        </dl>

        <!-- Prominent download / QR (reuses the shared action wiring) -->
        <div class="border-t border-outline-gray-1 px-4 py-3">
          <PeerActions :peer="peer" @show-qr="openQr" />
        </div>
      </div>
    </div>

    <QrDialog v-model:open="qrOpen" :peer="qrPeer" />
  </AppShell>
</template>

<script setup>
import { Button, LoadingIndicator, createResource } from "frappe-ui";
import { computed, onUnmounted, ref } from "vue";
import AppShell from "@/components/AppShell.vue";
import EmptyState from "@/components/EmptyState.vue";
import EndpointWarning from "@/components/EndpointWarning.vue";
import ErrorState from "@/components/ErrorState.vue";
import PeerActions from "@/components/PeerActions.vue";
import PresenceDot from "@/components/PresenceDot.vue";
import QrDialog from "@/components/QrDialog.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import ThroughputBadge from "@/components/ThroughputBadge.vue";
import { errorMessage } from "@/utils/format";

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
