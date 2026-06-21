<template>
  <div
    class="overflow-x-auto rounded-lg border border-outline-gray-2 bg-surface-white p-2"
  >
    <ListView :columns="columns" :rows="peers" row-key="name" :options="options">
      <template #cell="{ column, row }">
        <span
          v-if="column.key === 'peer_name'"
          class="truncate font-medium text-ink-gray-9"
          >{{ row.peer_name }}</span
        >
        <span
          v-else-if="column.key === 'owner_user'"
          class="truncate text-ink-gray-6"
          >{{ row.owner_user }}</span
        >
        <span
          v-else-if="column.key === 'server'"
          class="truncate font-mono text-ink-gray-7"
          >{{ row.server }}</span
        >
        <span
          v-else-if="column.key === 'assigned_ip'"
          class="font-mono text-ink-gray-7"
          >{{ row.assigned_ip || "—" }}</span
        >
        <StatusBadge v-else-if="column.key === 'status'" :status="row.status" />
        <PresenceDot
          v-else-if="column.key === 'presence'"
          :last-handshake="row.last_handshake"
        />
        <ThroughputBadge
          v-else-if="column.key === 'transfer'"
          :rx-bytes="row.rx_bytes"
          :tx-bytes="row.tx_bytes"
        />
        <!-- Stop row-click propagation so the action button doesn't also open the drawer. -->
        <div
          v-else-if="column.key === 'actions'"
          class="flex justify-end"
          @click.stop
        >
          <PeerActions
            v-if="showActions"
            :peer="row"
            @show-qr="(peer) => emit('show-qr', peer)"
          />
          <PeerAdminActions
            v-else-if="showAdminActions"
            :peer="row"
            @done="emit('peer-changed')"
          />
        </div>
      </template>
    </ListView>
  </div>
</template>

<script setup>
import { ListView } from "frappe-ui";
import { computed } from "vue";
import PeerActions from "@/components/PeerActions.vue";
import PeerAdminActions from "@/components/PeerAdminActions.vue";
import PresenceDot from "@/components/PresenceDot.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import ThroughputBadge from "@/components/ThroughputBadge.vue";

const props = defineProps({
  peers: { type: Array, default: () => [] },
  showOwner: { type: Boolean, default: false },
  showActions: { type: Boolean, default: false },
  showAdminActions: { type: Boolean, default: false },
});
const emit = defineEmits(["show-qr", "peer-changed", "row-click"]);

const options = {
  selectable: false,
  showTooltip: false,
  rowHeight: 48,
  onRowClick: (row) => emit("row-click", row),
};

const columns = computed(() => {
  const cols = [{ label: "Peer", key: "peer_name", width: 1.4 }];
  if (props.showOwner)
    cols.push({ label: "Owner", key: "owner_user", width: 1.4 });
  cols.push(
    { label: "Server", key: "server", width: 1 },
    { label: "Address", key: "assigned_ip", width: 1 },
    { label: "Status", key: "status", width: 0.8 },
    { label: "Presence", key: "presence", width: 0.9 },
    { label: "Transfer", key: "transfer", width: 1.1 }
  );
  // .conf/QR buttons need room; the admin ⋮ menu is narrow.
  if (props.showActions)
    cols.push({ label: "", key: "actions", width: "15rem", align: "right" });
  else if (props.showAdminActions)
    cols.push({ label: "", key: "actions", width: "3rem", align: "right" });
  return cols;
});
</script>
