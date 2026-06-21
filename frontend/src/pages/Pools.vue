<template>
  <AppShell>
    <div class="mb-5 flex items-center justify-between gap-4">
      <div>
        <h1 class="text-lg font-semibold text-ink-gray-9">Network Pools</h1>
        <p class="text-sm text-ink-gray-5">
          Address pools materialized into the IP allocation map.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <Button
          label="Refresh"
          icon-left="lucide-refresh-cw"
          :loading="pools.loading"
          @click="pools.reload()"
        />
        <Button
          variant="solid"
          theme="gray"
          label="New Pool"
          icon-left="lucide-plus"
          @click="create"
        />
      </div>
    </div>

    <div v-if="pools.loading && !rows.length" class="flex justify-center py-16">
      <LoadingIndicator class="size-6 text-ink-gray-5" />
    </div>
    <EmptyState
      v-else-if="!rows.length"
      icon="lucide-network"
      title="No pools yet"
      description="Create a pool to materialize a server's address space."
    />
    <div
      v-else
      class="overflow-x-auto rounded-lg border border-outline-gray-2 bg-surface-white p-2"
    >
      <ListView :columns="columns" :rows="rows" row-key="name" :options="options">
        <template #cell="{ column, row }">
          <span
            v-if="column.key === 'pool_name'"
            class="truncate font-medium text-ink-gray-9"
            >{{ row.pool_name }}</span
          >
          <span
            v-else-if="column.key === 'server'"
            class="truncate font-mono text-ink-gray-7"
            >{{ row.server }}</span
          >
          <span v-else-if="column.key === 'cidr'" class="font-mono text-ink-gray-7">{{
            row.cidr
          }}</span>
          <span
            v-else-if="column.key === 'gateway_ip'"
            class="font-mono text-ink-gray-6"
            >{{ row.gateway_ip || "—" }}</span
          >
          <span v-else-if="column.key === 'total_addresses'" class="text-ink-gray-7">{{
            row.total_addresses ?? "—"
          }}</span>
          <span
            v-else-if="column.key === 'last_materialized'"
            class="truncate text-ink-gray-6"
            >{{ relativeTime(row.last_materialized) }}</span
          >
          <div v-else-if="column.key === 'actions'" class="flex justify-end">
            <Button
              variant="ghost"
              icon="lucide-pencil"
              aria-label="Edit pool"
              @click.stop="edit(row)"
            />
          </div>
        </template>
      </ListView>
    </div>

    <PoolForm v-model:open="showForm" :pool-name="editing" @saved="pools.reload()" />
  </AppShell>
</template>

<script setup>
import { Button, ListView, LoadingIndicator, createResource } from "frappe-ui";
import { computed, ref } from "vue";
import AppShell from "@/components/AppShell.vue";
import EmptyState from "@/components/EmptyState.vue";
import PoolForm from "@/components/PoolForm.vue";
import { relativeTime } from "@/utils/format";

const pools = createResource({
  url: "vpn_management.api.list_pools",
  method: "GET",
  auto: true,
});
const rows = computed(() => pools.data || []);

const options = { selectable: false, showTooltip: false, rowHeight: 48 };
const columns = [
  { label: "Pool", key: "pool_name", width: 1.4 },
  { label: "Server", key: "server", width: 1 },
  { label: "CIDR", key: "cidr", width: 1.2 },
  { label: "Gateway", key: "gateway_ip", width: 1 },
  { label: "Addresses", key: "total_addresses", width: 0.8 },
  { label: "Last materialized", key: "last_materialized", width: 1.1 },
  { label: "", key: "actions", width: "3rem", align: "right" },
];

const showForm = ref(false);
const editing = ref(null);

function create() {
  editing.value = null;
  showForm.value = true;
}

function edit(pool) {
  editing.value = pool.name;
  showForm.value = true;
}
</script>
