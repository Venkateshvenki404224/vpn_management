<template>
  <div
    class="flex flex-col rounded-lg border border-outline-gray-2 bg-surface-white transition-shadow hover:shadow-sm"
  >
    <!-- Header: interface name + status badge, framed like the chart cards. -->
    <div
      class="flex items-center justify-between gap-2 border-b border-outline-gray-1 px-4 py-3"
    >
      <div class="flex items-center gap-2">
        <span
          class="size-2 shrink-0 rounded-full"
          :class="server.interface_up ? 'bg-surface-green-3' : 'bg-surface-gray-4'"
          aria-hidden="true"
        />
        <span class="font-mono text-sm font-medium text-ink-gray-9">{{
          server.interface_name
        }}</span>
      </div>
      <StatusBadge :status="server.status" />
    </div>

    <dl class="flex-1 space-y-2 px-4 py-3 text-sm text-ink-gray-6">
      <div class="flex justify-between gap-2">
        <dt>Address</dt>
        <dd class="font-mono text-ink-gray-7">{{ server.address_cidr || "—" }}</dd>
      </div>
      <div class="flex justify-between gap-2">
        <dt>Port</dt>
        <dd>{{ server.listen_port || "—" }}</dd>
      </div>
      <div class="flex justify-between gap-2">
        <dt>Interface</dt>
        <dd>{{ server.interface_up ? "Up" : "Down" }}</dd>
      </div>
      <div class="flex justify-between gap-2">
        <dt>Last reconcile</dt>
        <dd :title="absoluteTime(server.last_reconcile)">
          {{ relativeTime(server.last_reconcile) }}
        </dd>
      </div>
    </dl>

    <div
      v-if="actions"
      class="flex items-center gap-2 border-t border-outline-gray-1 px-4 py-3"
    >
      <Button
        label="Reconcile"
        icon-left="lucide-refresh-cw"
        :loading="reconcile.loading"
        @click="confirmReconcile"
      />
      <Button
        label="Provision"
        icon-left="lucide-rocket"
        :loading="provision.loading"
        @click="confirmProvision"
      />
    </div>
  </div>
</template>

<script setup>
import { Button, createResource, dialog, toast } from "frappe-ui";
import StatusBadge from "@/components/StatusBadge.vue";
import { absoluteTime, relativeTime } from "@/utils/format";

const props = defineProps({
  server: { type: Object, required: true },
  // Show the Reconcile/Provision lifecycle actions (admin-only screens).
  actions: { type: Boolean, default: false },
});
const emit = defineEmits(["done"]);

const reconcile = createResource({
  url: "vpn_management.api.reconcile_interface",
  method: "POST",
});
const provision = createResource({
  url: "vpn_management.api.provision_server",
  method: "POST",
});

function confirmReconcile() {
  const iface = props.server.name;
  dialog.confirm({
    title: `Reconcile ${iface}?`,
    message:
      "Re-converge the live interface from the database. A background job applies the change.",
    confirmLabel: "Reconcile",
    onConfirm: async () => {
      await reconcile.submit({ interface_name: iface });
      toast.success(`Reconcile queued for ${iface}`);
      emit("done");
    },
  });
}

function confirmProvision() {
  const iface = props.server.name;
  dialog.confirm({
    title: `Provision ${iface}?`,
    message:
      "Materialize the server's address pools, then bring the interface up. Safe to re-run.",
    confirmLabel: "Provision",
    onConfirm: async () => {
      await provision.submit({ interface_name: iface });
      toast.success(`Provision queued for ${iface}`);
      emit("done");
    },
  });
}
</script>
