<template>
  <Dropdown :options="options" placement="right">
    <Button
      variant="ghost"
      icon="lucide-ellipsis-vertical"
      aria-label="Peer actions"
    />
  </Dropdown>
</template>

<script setup>
import { Button, Dropdown, createResource, dialog, toast } from "frappe-ui";
import { computed } from "vue";

const props = defineProps({
  peer: { type: Object, required: true },
});
const emit = defineEmits(["done"]);

const revoke = createResource({
  url: "vpn_management.api.revoke_peer",
  method: "POST",
});
const regenerate = createResource({
  url: "vpn_management.api.regenerate_keys",
  method: "POST",
});

function confirmRevoke() {
  dialog.confirm({
    title: "Revoke this peer?",
    message: `"${props.peer.peer_name}" will be disabled, its address freed, and it will drop from the live interface.`,
    theme: "red",
    confirmLabel: "Revoke peer",
    onConfirm: async () => {
      await revoke.submit({ name: props.peer.name });
      toast.success(`Revoked ${props.peer.peer_name}`);
      emit("done");
    },
  });
}

function confirmRegenerate() {
  dialog.confirm({
    title: "Regenerate keys?",
    message: `A new keypair is generated for "${props.peer.peer_name}". Existing client configs stop working until re-downloaded.`,
    confirmLabel: "Regenerate keys",
    onConfirm: async () => {
      await regenerate.submit({ name: props.peer.name });
      toast.success(`Regenerated keys for ${props.peer.peer_name}`);
      emit("done");
    },
  });
}

const options = computed(() => [
  {
    label: "Regenerate keys",
    icon: "lucide-key-round",
    onClick: confirmRegenerate,
  },
  {
    label: "Revoke",
    icon: "lucide-ban",
    theme: "red",
    onClick: confirmRevoke,
    condition: () => props.peer.status !== "Revoked",
  },
]);
</script>
