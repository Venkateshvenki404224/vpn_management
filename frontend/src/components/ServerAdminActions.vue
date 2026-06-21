<template>
  <Dropdown :options="options" placement="right">
    <Button
      variant="ghost"
      icon="lucide-ellipsis-vertical"
      aria-label="Server actions"
    />
  </Dropdown>
</template>

<script setup>
import { Button, Dropdown, createResource, dialog, toast } from "frappe-ui";

const props = defineProps({
  server: { type: Object, required: true },
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

const options = [
  { label: "Reconcile", icon: "lucide-refresh-cw", onClick: confirmReconcile },
  { label: "Provision", icon: "lucide-rocket", onClick: confirmProvision },
];
</script>
