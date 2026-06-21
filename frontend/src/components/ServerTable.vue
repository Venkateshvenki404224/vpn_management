<template>
  <div
    class="overflow-x-auto rounded-lg border border-outline-gray-2 bg-surface-white p-2"
  >
    <ListView :columns="columns" :rows="servers" row-key="name" :options="options">
      <template #cell="{ column, row }">
        <span
          v-if="column.key === 'interface_name'"
          class="truncate font-mono font-medium text-ink-gray-9"
          >{{ row.interface_name }}</span
        >
        <span
          v-else-if="column.key === 'address_cidr'"
          class="truncate font-mono text-ink-gray-7"
          >{{ row.address_cidr || "—" }}</span
        >
        <span v-else-if="column.key === 'listen_port'" class="text-ink-gray-7">{{
          row.listen_port || "—"
        }}</span>
        <StatusBadge v-else-if="column.key === 'status'" :status="row.status" />
        <span v-else-if="column.key === 'interface_up'" class="text-ink-gray-6">{{
          row.interface_up ? "Up" : "Down"
        }}</span>
        <span
          v-else-if="column.key === 'last_reconcile'"
          class="truncate text-ink-gray-6"
          >{{ relativeTime(row.last_reconcile) }}</span
        >
        <div
          v-else-if="column.key === 'actions'"
          class="flex items-center justify-end gap-1"
        >
          <template v-if="manage">
            <Button
              variant="ghost"
              icon="lucide-pencil"
              aria-label="Edit server"
              @click.stop="emit('edit', row)"
            />
            <Button
              variant="ghost"
              icon="lucide-network"
              aria-label="IP allocation map"
              :route="`/admin/servers/${row.name}/ip-map`"
            />
          </template>
          <ServerAdminActions :server="row" @done="emit('done')" />
        </div>
      </template>
    </ListView>
  </div>
</template>

<script setup>
import { Button, ListView } from "frappe-ui";
import { computed } from "vue";
import ServerAdminActions from "@/components/ServerAdminActions.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import { relativeTime } from "@/utils/format";

const props = defineProps({
  servers: { type: Array, default: () => [] },
  // Show the Reconcile/Provision lifecycle actions (admin-only screens).
  actions: { type: Boolean, default: false },
  // Management screen: also show Edit + IP-map actions.
  manage: { type: Boolean, default: false },
});
const emit = defineEmits(["done", "edit"]);

const options = { selectable: false, showTooltip: false, rowHeight: 48 };

const columns = computed(() => {
  const cols = [
    { label: "Interface", key: "interface_name", width: 1.2 },
    { label: "Address", key: "address_cidr", width: 1.2 },
    { label: "Port", key: "listen_port", width: 0.8 },
    { label: "Status", key: "status", width: 0.9 },
    { label: "Live", key: "interface_up", width: 0.7 },
    { label: "Last reconcile", key: "last_reconcile", width: 1.1 },
  ];
  if (props.actions || props.manage)
    cols.push({ label: "", key: "actions", width: props.manage ? "8rem" : "3rem", align: "right" });
  return cols;
});
</script>
