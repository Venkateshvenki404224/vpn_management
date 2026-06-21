<template>
  <AppShell>
    <div class="mb-5 flex items-center justify-between gap-4">
      <div>
        <h1 class="text-lg font-semibold text-ink-gray-9">Dashboard</h1>
        <p class="text-sm text-ink-gray-5">
          Interface health, peer counts, and recent activity.
        </p>
      </div>
      <Button
        label="Refresh"
        icon-left="lucide-refresh-cw"
        :loading="loading"
        @click="refresh"
      />
    </div>

    <!-- Peer counts -->
    <section class="mb-6">
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCounter label="Total peers" :value="counts.total" />
        <StatCounter label="Active" :value="counts.active" tone="green" />
        <StatCounter label="Stale" :value="counts.stale" tone="amber" />
        <StatCounter label="Revoked" :value="counts.revoked" tone="red" />
      </div>
    </section>

    <!-- Interface status -->
    <section class="mb-6">
      <h2 class="mb-2 text-sm font-semibold text-ink-gray-7">Interfaces</h2>
      <ErrorState
        v-if="servers.error"
        :message="errorMessage(servers.error)"
        @retry="servers.reload()"
      />
      <div
        v-else-if="servers.loading && !serverRows.length"
        class="flex justify-center py-12"
      >
        <LoadingIndicator class="size-6 text-ink-gray-5" />
      </div>
      <EmptyState
        v-else-if="!serverRows.length"
        icon="lucide-server-off"
        title="No servers configured"
        description="Add a WireGuard Server to start provisioning interfaces."
      />
      <div v-else class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <ServerStatusCard
          v-for="server in serverRows"
          :key="server.name"
          :server="server"
          actions
          @done="refresh"
        />
      </div>
    </section>

    <!-- Recent activity -->
    <section>
      <h2 class="mb-2 text-sm font-semibold text-ink-gray-7">Recent activity</h2>
      <ErrorState
        v-if="audit.error"
        :message="errorMessage(audit.error)"
        @retry="audit.reload()"
      />
      <div
        v-else-if="audit.loading && !auditRows.length"
        class="flex justify-center py-12"
      >
        <LoadingIndicator class="size-6 text-ink-gray-5" />
      </div>
      <EmptyState
        v-else-if="!auditRows.length"
        icon="lucide-scroll-text"
        title="No activity yet"
        description="Privileged actions — reconciles, revokes, key rotations — appear here."
      />
      <RecentActivity v-else :rows="auditRows" />
    </section>
  </AppShell>
</template>

<script setup>
import { Button, LoadingIndicator, createResource } from "frappe-ui";
import { computed, onUnmounted } from "vue";
import AppShell from "@/components/AppShell.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import RecentActivity from "@/components/RecentActivity.vue";
import ServerStatusCard from "@/components/ServerStatusCard.vue";
import StatCounter from "@/components/StatCounter.vue";
import { errorMessage } from "@/utils/format";

const servers = createResource({
  url: "vpn_management.api.list_servers",
  method: "GET", // whitelisted GET-only; createResource defaults to POST
  auto: true,
});
// A generous limit so counts are accurate without a dedicated aggregate endpoint.
const peers = createResource({
  url: "vpn_management.api.list_peers",
  method: "GET",
  params: { limit: 500 },
  auto: true,
});
// VPN Admin has read perm on VPN Audit Log, so the core list endpoint suffices —
// no bespoke backend endpoint needed (the doctype stays append-only/read-only).
const audit = createResource({
  url: "frappe.client.get_list",
  params: {
    doctype: "VPN Audit Log",
    fields: ["name", "action", "target", "result", "actor", "creation"],
    order_by: "creation desc",
    limit_page_length: 8,
  },
  auto: true,
});

const serverRows = computed(() => servers.data || []);
const peerRows = computed(() => peers.data || []);
const auditRows = computed(() => audit.data || []);
const loading = computed(() => servers.loading || peers.loading || audit.loading);

const counts = computed(() => {
  const rows = peerRows.value;
  const countBy = (status) => rows.filter((peer) => peer.status === status).length;
  return {
    total: rows.length,
    active: countBy("Active"),
    stale: countBy("Stale"),
    revoked: countBy("Revoked"),
  };
});

function refresh() {
  servers.reload();
  peers.reload();
  audit.reload();
}

// Poll so interface health / counts / activity stay fresh; cleared on unmount.
const interval = setInterval(refresh, 30000);
onUnmounted(() => clearInterval(interval));
</script>
