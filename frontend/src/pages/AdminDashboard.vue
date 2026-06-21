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

    <!-- Peer counts + status breakdown (single dashboard_summary aggregation) -->
    <section class="mb-6">
      <ErrorState
        v-if="summary.error"
        :message="errorMessage(summary.error)"
        @retry="summary.reload()"
      />
      <template v-else>
        <div class="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div
            v-for="tile in statTiles"
            :key="tile.title"
            class="overflow-hidden rounded-lg border border-outline-gray-2"
          >
            <NumberChart :config="tile" />
          </div>
        </div>
        <div class="lg:max-w-lg">
          <ChartCard
            title="Peer status"
            subtitle="Distribution across lifecycle states"
            empty-icon="lucide-chart-pie"
            empty-title="No peers yet"
            empty-description="Status breakdown appears once peers are provisioned."
            :loading="summary.loading && !summary.data"
            :empty="!totalPeers"
          >
            <DonutChart :config="donutConfig" />
          </ChartCard>
        </div>
      </template>
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
import {
  Button,
  DonutChart,
  LoadingIndicator,
  NumberChart,
  createResource,
} from "frappe-ui";
import { computed, onUnmounted } from "vue";
import AppShell from "@/components/AppShell.vue";
import ChartCard from "@/components/ChartCard.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import RecentActivity from "@/components/RecentActivity.vue";
import ServerStatusCard from "@/components/ServerStatusCard.vue";
import { errorMessage } from "@/utils/format";

const servers = createResource({
  url: "vpn_management.api.list_servers",
  method: "GET", // whitelisted GET-only; createResource defaults to POST
  auto: true,
});
// One server-side aggregation replaces the old fetch-500-peers-and-count-in-JS
// loop: counts by status + a 30-day trend, computed in a single grouped query.
const summary = createResource({
  url: "vpn_management.api.dashboard_summary",
  method: "GET",
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
const auditRows = computed(() => audit.data || []);
const counts = computed(() => summary.data?.counts || {});
const totalPeers = computed(() => counts.value.total || 0);
const loading = computed(
  () => servers.loading || summary.loading || audit.loading,
);

// NumberChart config objects (title + numeric value) for the headline row.
const statTiles = computed(() => [
  { title: "Total peers", value: counts.value.total || 0 },
  { title: "Active", value: counts.value.active || 0 },
  { title: "Stale", value: counts.value.stale || 0 },
  { title: "Revoked", value: counts.value.revoked || 0 },
]);

// Donut rows: one slice per non-empty lifecycle state (zero-count states are
// dropped so the chart isn't cluttered with empty slices).
const STATUS_ORDER = ["Active", "Stale", "Pending", "Disabled", "Revoked"];
const donutConfig = computed(() => ({
  title: "",
  data: STATUS_ORDER.map((status) => ({
    status,
    count: counts.value[status.toLowerCase()] || 0,
  })).filter((row) => row.count > 0),
  categoryColumn: "status",
  valueColumn: "count",
}));

function refresh() {
  servers.reload();
  summary.reload();
  audit.reload();
}

// Poll so interface health / counts / activity stay fresh; cleared on unmount.
const interval = setInterval(refresh, 30000);
onUnmounted(() => clearInterval(interval));
</script>
