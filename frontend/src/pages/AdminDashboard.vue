<template>
  <AppShell>
    <div class="mb-5 flex items-center justify-between gap-4">
      <div>
        <h1 class="text-lg font-semibold text-ink-gray-9">Dashboard</h1>
        <p class="text-sm text-ink-gray-5">
          Peer counts, IP capacity, trends, and recent activity.
        </p>
      </div>
      <Button
        label="Refresh"
        icon-left="lucide-refresh-cw"
        :loading="loading"
        @click="refresh"
      />
    </div>

    <!-- Everything driven by the single dashboard_summary aggregation. -->
    <ErrorState
      v-if="summary.error"
      class="mb-6"
      :message="errorMessage(summary.error)"
      @retry="summary.reload()"
    />
    <template v-else>
      <!-- Stat row with Δ-vs-prior-7-days trend arrows -->
      <section class="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div
          v-for="tile in statTiles"
          :key="tile.title"
          class="overflow-hidden rounded-lg border border-outline-gray-2"
        >
          <NumberChart :config="tile" />
        </div>
      </section>

      <!-- Peer-status donut + IP-capacity gauge + peers/day trend -->
      <section class="mb-4 grid gap-4 lg:grid-cols-3">
        <ChartCard
          title="Peer status"
          subtitle="Distribution across lifecycle states"
          empty-icon="lucide-chart-pie"
          empty-title="No peers yet"
          empty-description="Status breakdown appears once peers are provisioned."
          :loading="chartsLoading"
          :empty="!totalPeers"
        >
          <DonutChart :config="donutConfig" />
        </ChartCard>

        <ChartCard
          title="IP capacity"
          subtitle="Addresses used across all pools"
          empty-icon="lucide-gauge"
          empty-title="No addresses yet"
          empty-description="Materialize a Network Pool to track allocation capacity."
          :loading="chartsLoading"
          :empty="!ipPool.total"
        >
          <CapacityGauge :pool="ipPool" />
        </ChartCard>

        <ChartCard
          title="Peers per day"
          subtitle="New peers over the last 30 days"
          empty-icon="lucide-trending-up"
          empty-title="No provisioning yet"
          empty-description="A daily trend appears once peers are created."
          :loading="chartsLoading"
          :empty="!peersPerDay.length"
        >
          <AxisChart :config="peersChart" />
        </ChartCard>
      </section>

      <!-- Audit actions per day (stacked by result) -->
      <section class="mb-6">
        <ChartCard
          title="Audit actions per day"
          subtitle="Privileged actions over the last 30 days, by result"
          empty-icon="lucide-bar-chart-3"
          empty-title="No audited actions yet"
          empty-description="Reconciles, key rotations, and syncs appear here once they run."
          body-height="22rem"
          :loading="chartsLoading"
          :empty="!auditPerDay.length"
        >
          <AxisChart :config="auditChart" />
        </ChartCard>
      </section>
    </template>

    <!-- Interface status -->
    <section class="mb-6">
      <div class="mb-2 flex items-baseline gap-3">
        <h2 class="text-sm font-semibold text-ink-gray-7">Interfaces</h2>
        <span v-if="serverCounts.total" class="text-xs text-ink-gray-5">
          {{ serverCounts.up }} up · {{ serverCounts.down }} down<template
            v-if="serverCounts.error"
          >
            · {{ serverCounts.error }} error</template
          >
        </span>
      </div>
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
  AxisChart,
  Button,
  DonutChart,
  LoadingIndicator,
  NumberChart,
  createResource,
} from "frappe-ui";
import { computed, onUnmounted } from "vue";
import AppShell from "@/components/AppShell.vue";
import CapacityGauge from "@/components/CapacityGauge.vue";
import ChartCard from "@/components/ChartCard.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import RecentActivity from "@/components/RecentActivity.vue";
import ServerStatusCard from "@/components/ServerStatusCard.vue";
import { theme } from "@/data/theme";
import { errorMessage } from "@/utils/format";

const servers = createResource({
  url: "vpn_management.api.list_servers",
  method: "GET", // whitelisted GET-only; createResource defaults to POST
  auto: true,
});
// One server-side aggregation powers the whole command center: counts + deltas,
// server status, aggregate IP capacity, and the peers/day + audit/day trends.
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
    limit_page_length: 10,
  },
  auto: true,
});

const serverRows = computed(() => servers.data || []);
const auditRows = computed(() => audit.data || []);
const counts = computed(() => summary.data?.counts || {});
const deltas = computed(() => summary.data?.deltas || {});
const serverCounts = computed(() => summary.data?.servers || {});
const ipPool = computed(
  () => summary.data?.ip_pool || { total: 0, allocated: 0, reserved: 0, free: 0 },
);
const peersPerDay = computed(() => summary.data?.peers_per_day || []);
const auditPerDay = computed(() => summary.data?.audit_per_day || []);
const totalPeers = computed(() => counts.value.total || 0);
const chartsLoading = computed(() => summary.loading && !summary.data);
const loading = computed(
  () => servers.loading || summary.loading || audit.loading,
);

// NumberChart configs: value + a 7-day Δ. Stale/Revoked are "negative is better"
// so a rise renders red (↑) and a fall renders green (↓); the inverse for growth
// metrics. NumberChart hides the Δ row entirely when the delta is 0.
const statTiles = computed(() => [
  { title: "Total peers", value: counts.value.total || 0, ...delta("total") },
  { title: "Active", value: counts.value.active || 0, ...delta("active") },
  {
    title: "Stale",
    value: counts.value.stale || 0,
    ...delta("stale", true),
  },
  {
    title: "Revoked",
    value: counts.value.revoked || 0,
    ...delta("revoked", true),
  },
]);

function delta(key, negativeIsBetter = false) {
  return {
    delta: deltas.value[key] || 0,
    deltaSuffix: " (7d)",
    negativeIsBetter,
  };
}

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

// ECharts renders to canvas and can't read CSS custom properties, so resolve the
// espresso tokens (stored as "R G B" triples) to concrete rgb() strings. Keyed on
// theme.dark so series colors re-resolve to the dark/light values on toggle.
function resolveColor(varName, fallback) {
  if (typeof window === "undefined") return fallback;
  const triple = getComputedStyle(document.documentElement)
    .getPropertyValue(varName)
    .trim();
  return triple ? `rgb(${triple})` : fallback;
}
const colors = computed(() => {
  void theme.dark;
  return {
    blue: resolveColor("--text-ink-blue-3", "rgb(36 118 245)"),
    green: resolveColor("--text-ink-green-2", "rgb(48 166 109)"),
    red: resolveColor("--text-ink-red-3", "rgb(229 62 62)"),
    gray: resolveColor("--text-ink-gray-4", "rgb(160 160 160)"),
  };
});

// Peers/day: an area trend over real dates (time axis spaces by actual day).
const peersChart = computed(() => ({
  title: "",
  data: peersPerDay.value.map((row) => ({ day: row.day, "New peers": row.count })),
  xAxis: { key: "day", type: "time" },
  yAxis: { title: "Peers" },
  series: [{ name: "New peers", type: "area", color: colors.value.blue }],
}));

// Audit/day: a stacked bar per day, segmented by result. axisChartOptions only
// applies `stacked` to bar series (not areas), so bars it is — and they read well
// for daily counts. Pivot the long {day, result, count} rows into one row per day.
const RESULT_SERIES = [
  { name: "Success", result: "success", key: "green" },
  { name: "Failure", result: "failure", key: "red" },
  { name: "Skipped", result: "skipped", key: "gray" },
];
const auditChart = computed(() => {
  const byDay = {};
  for (const row of auditPerDay.value) {
    byDay[row.day] ||= { day: row.day, Success: 0, Failure: 0, Skipped: 0 };
    const series = RESULT_SERIES.find((s) => s.result === row.result);
    if (series) byDay[row.day][series.name] = row.count;
  }
  return {
    title: "",
    data: Object.values(byDay).sort((a, b) => a.day.localeCompare(b.day)),
    xAxis: { key: "day", type: "category" },
    yAxis: { title: "Actions" },
    stacked: true,
    series: RESULT_SERIES.map((s) => ({
      name: s.name,
      type: "bar",
      color: colors.value[s.key],
    })),
  };
});

function refresh() {
  servers.reload();
  summary.reload();
  audit.reload();
}

// Poll so interface health / counts / activity stay fresh; cleared on unmount.
const interval = setInterval(refresh, 30000);
onUnmounted(() => clearInterval(interval));
</script>
