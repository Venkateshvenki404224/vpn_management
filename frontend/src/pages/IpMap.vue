<template>
  <AppShell>
    <div class="mb-5 flex items-center justify-between gap-4">
      <div class="flex items-center gap-3">
        <Button
          variant="ghost"
          icon="lucide-arrow-left"
          aria-label="Back to servers"
          route="/admin/servers"
        />
        <div>
          <h1 class="text-lg font-semibold text-ink-gray-9">
            IP allocation · <span class="font-mono">{{ server }}</span>
          </h1>
          <p class="text-sm text-ink-gray-5">
            Allocated, reserved, and free addresses across the server's pools.
          </p>
        </div>
      </div>
      <Button
        label="Refresh"
        icon-left="lucide-refresh-cw"
        :loading="allocations.loading"
        @click="allocations.reload()"
      />
    </div>

    <ErrorState
      v-if="allocations.error"
      :message="errorMessage(allocations.error)"
      @retry="allocations.reload()"
    />
    <div v-else-if="allocations.loading && !data" class="flex justify-center py-16">
      <LoadingIndicator class="size-6 text-ink-gray-5" />
    </div>
    <EmptyState
      v-else-if="!data || !data.summary.total"
      icon="lucide-network"
      title="No addresses materialized"
      description="Provision the server or create a pool to materialize its address space."
    />
    <section v-else class="grid items-start gap-4 lg:grid-cols-3">
      <!-- Capacity ring — the signature gauge, scoped to this one server's pools. -->
      <ChartCard
        title="IP capacity"
        subtitle="Addresses used across this server's pools"
        body-height="18rem"
        class="lg:col-span-1"
      >
        <CapacityGauge :pool="data.summary" />
      </ChartCard>

      <!-- The allocation map itself: one cell per address, natural height so the
           grid wraps freely instead of clipping inside a fixed-height card. -->
      <div
        class="rounded-lg border border-outline-gray-2 bg-surface-white lg:col-span-2"
      >
        <div class="border-b border-outline-gray-1 px-4 py-3">
          <h3 class="text-base font-semibold text-ink-gray-8">Allocation map</h3>
          <p class="mt-0.5 text-xs text-ink-gray-5">
            Each cell is one address — hover for its peer or reservation.
          </p>
        </div>
        <div class="p-4">
          <IpAllocationGrid :rows="data.rows" :summary="data.summary" />
        </div>
      </div>
    </section>
  </AppShell>
</template>

<script setup>
import { Button, LoadingIndicator, createResource } from "frappe-ui";
import { computed, watch } from "vue";
import AppShell from "@/components/AppShell.vue";
import CapacityGauge from "@/components/CapacityGauge.vue";
import ChartCard from "@/components/ChartCard.vue";
import EmptyState from "@/components/EmptyState.vue";
import ErrorState from "@/components/ErrorState.vue";
import IpAllocationGrid from "@/components/IpAllocationGrid.vue";
import { errorMessage } from "@/utils/format";

const props = defineProps({
  // Supplied by the router from /admin/servers/:server/ip-map.
  server: { type: String, required: true },
});

const allocations = createResource({
  url: "vpn_management.api.list_ip_allocations",
  method: "GET",
  // makeParams re-reads the current server on every fetch, so a same-component
  // navigation between two servers' maps (vue-router reuses the instance) loads
  // the new server's rows instead of leaving the previous server's grid stale.
  makeParams: () => ({ server: props.server, limit: 512 }),
  auto: true,
});
watch(
  () => props.server,
  () => allocations.reload(),
);
const data = computed(() => allocations.data);
</script>
