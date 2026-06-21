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
    <div
      v-else-if="allocations.loading && !data"
      class="flex justify-center py-16"
    >
      <LoadingIndicator class="size-6 text-ink-gray-5" />
    </div>
    <EmptyState
      v-else-if="!data || !data.summary.total"
      icon="lucide-network"
      title="No addresses materialized"
      description="Provision the server or create a pool to materialize its address space."
    />
    <div
      v-else
      class="rounded-lg border border-outline-gray-2 bg-surface-white p-4"
    >
      <IpAllocationGrid :rows="data.rows" :summary="data.summary" />
    </div>
  </AppShell>
</template>

<script setup>
import { Button, LoadingIndicator, createResource } from "frappe-ui";
import { computed } from "vue";
import AppShell from "@/components/AppShell.vue";
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
  params: { server: props.server, limit: 512 },
  auto: true,
});
const data = computed(() => allocations.data);
</script>
