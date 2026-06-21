<template>
  <div class="rounded-lg border border-outline-gray-2 bg-surface-white p-4">
    <div class="flex items-center justify-between gap-2">
      <span class="font-mono text-sm font-medium text-ink-gray-9">{{
        server.interface_name
      }}</span>
      <StatusBadge :status="server.status" />
    </div>

    <dl class="mt-3 space-y-1 text-sm text-ink-gray-6">
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
        <dd>{{ relativeTime(server.last_reconcile) }}</dd>
      </div>
    </dl>

    <div v-if="actions" class="mt-4 flex items-center gap-2">
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
import { relativeTime } from "@/utils/format";

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
