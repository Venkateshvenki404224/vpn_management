<template>
  <Dialog v-model:open="open" bare position="right" size="md">
    <template #default="{ close }">
      <div v-if="peer" class="flex min-h-screen w-full flex-col bg-surface-modal">
        <!-- Header: identity + close -->
        <header
          class="flex items-start justify-between gap-3 border-b border-outline-gray-1 px-5 py-4"
        >
          <div class="min-w-0">
            <h2 class="truncate text-base font-semibold text-ink-gray-9">
              {{ view.peer_name }}
            </h2>
            <p class="truncate text-sm text-ink-gray-5">
              {{ view.owner_user || "—" }}
            </p>
          </div>
          <Button variant="ghost" icon="lucide-x" aria-label="Close" @click="close" />
        </header>

        <!-- Body -->
        <div class="flex-1 space-y-6 overflow-y-auto px-5 py-5">
          <!-- Live status + throughput -->
          <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
            <StatusBadge :status="view.status" />
            <PresenceDot :last-handshake="view.last_handshake" />
            <ThroughputBadge :rx-bytes="view.rx_bytes" :tx-bytes="view.tx_bytes" />
          </div>

          <!-- Identity / config facts -->
          <dl class="space-y-2.5 text-sm">
            <div
              v-for="row in rows"
              :key="row.label"
              class="flex items-start justify-between gap-3"
            >
              <dt class="shrink-0 text-ink-gray-5">{{ row.label }}</dt>
              <dd
                class="min-w-0 break-all text-right text-ink-gray-8"
                :class="{ 'font-mono': row.mono }"
                :title="row.title || undefined"
              >
                {{ row.value || "—" }}
              </dd>
            </div>
          </dl>

          <!-- Client config delivery -->
          <div class="space-y-3 border-t border-outline-gray-1 pt-5">
            <h3 class="text-xs font-semibold uppercase tracking-wide text-ink-gray-5">
              Client configuration
            </h3>
            <EndpointWarning />
            <div v-if="session.endpointReady" class="flex flex-col items-center gap-3">
              <img
                :src="qrUrl"
                :alt="`QR code for ${view.peer_name}`"
                class="size-48 rounded-md border border-outline-gray-2 bg-surface-white p-2"
              />
              <Button
                class="w-full"
                label="Download .conf"
                icon-left="lucide-download"
                @click="downloadConf"
              />
            </div>
          </div>
        </div>

        <!-- Admin actions -->
        <footer
          v-if="isAdmin"
          class="flex flex-wrap gap-2 border-t border-outline-gray-1 px-5 py-4"
        >
          <Button
            label="Regenerate keys"
            icon-left="lucide-key-round"
            :loading="regenerate.loading"
            @click="confirmRegenerate"
          />
          <Button
            label="Reconcile"
            icon-left="lucide-refresh-cw"
            :loading="reconcile.loading"
            @click="confirmReconcile"
          />
          <Button
            theme="red"
            variant="subtle"
            label="Revoke"
            icon-left="lucide-ban"
            :loading="revoke.loading"
            :disabled="view.status === 'Revoked'"
            @click="confirmRevoke"
          />
        </footer>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import { Button, Dialog, createResource, dialog, toast } from "frappe-ui";
import { computed, watch } from "vue";
import EndpointWarning from "@/components/EndpointWarning.vue";
import PresenceDot from "@/components/PresenceDot.vue";
import StatusBadge from "@/components/StatusBadge.vue";
import ThroughputBadge from "@/components/ThroughputBadge.vue";
import { isAdmin, session } from "@/data/session";
import { absoluteTime, relativeTime } from "@/utils/format";

const open = defineModel("open", { type: Boolean, default: false });
const props = defineProps({
  peer: { type: Object, default: null },
});
const emit = defineEmits(["changed"]);

// Refresh from the owner-scoped endpoint on open so presence/throughput/status
// are live; the passed-in row renders instantly while this resolves.
const detail = createResource({
  url: "vpn_management.api.get_peer",
  method: "GET",
  makeParams: () => ({ name: props.peer?.name }),
});

watch(
  [open, () => props.peer?.name],
  ([isOpen, name]) => {
    if (isOpen && name) detail.reload();
  },
  { immediate: true }
);

const view = computed(() => ({ ...(props.peer || {}), ...(detail.data || {}) }));

const rows = computed(() => [
  { label: "Status", value: view.value.status },
  { label: "Assigned IP", value: view.value.assigned_ip, mono: true },
  { label: "Endpoint", value: view.value.endpoint, mono: true },
  { label: "Server", value: view.value.server, mono: true },
  { label: "Allowed IPs", value: view.value.client_allowed_ips, mono: true },
  {
    label: "Keepalive",
    value: view.value.persistent_keepalive
      ? `${view.value.persistent_keepalive}s`
      : "Off",
  },
  {
    label: "Last handshake",
    value: relativeTime(view.value.last_handshake),
    title: absoluteTime(view.value.last_handshake),
  },
]);

// Same-origin GET downloads; the session cookie authenticates the stream. Admins
// are exempt from the owner check on these endpoints (api._own_peer).
const qrUrl = computed(() =>
  props.peer
    ? `/api/method/vpn_management.api.my_config_qr?name=${encodeURIComponent(props.peer.name)}`
    : ""
);
function downloadConf() {
  window.location = `/api/method/vpn_management.api.my_config_download?name=${encodeURIComponent(
    props.peer.name
  )}`;
}

// --- admin lifecycle actions (reuse the existing whitelisted endpoints) ------
const revoke = createResource({ url: "vpn_management.api.revoke_peer", method: "POST" });
const regenerate = createResource({
  url: "vpn_management.api.regenerate_keys",
  method: "POST",
});
const reconcile = createResource({
  url: "vpn_management.api.reconcile_interface",
  method: "POST",
});

function afterAction(message) {
  toast.success(message);
  detail.reload();
  emit("changed");
}

function confirmRevoke() {
  dialog.confirm({
    title: "Revoke this peer?",
    message: `"${view.value.peer_name}" will be disabled, its address freed, and it will drop from the live interface.`,
    theme: "red",
    confirmLabel: "Revoke peer",
    onConfirm: async () => {
      await revoke.submit({ name: props.peer.name });
      afterAction(`Revoked ${view.value.peer_name}`);
    },
  });
}

function confirmRegenerate() {
  dialog.confirm({
    title: "Regenerate keys?",
    message: `A new keypair is generated for "${view.value.peer_name}". Existing client configs stop working until re-downloaded.`,
    confirmLabel: "Regenerate keys",
    onConfirm: async () => {
      await regenerate.submit({ name: props.peer.name });
      afterAction(`Regenerated keys for ${view.value.peer_name}`);
    },
  });
}

function confirmReconcile() {
  const iface = view.value.server;
  dialog.confirm({
    title: `Reconcile ${iface}?`,
    message:
      "Re-converge the live interface from the database. A background job applies the change.",
    confirmLabel: "Reconcile",
    onConfirm: async () => {
      await reconcile.submit({ interface_name: iface });
      afterAction(`Reconcile queued for ${iface}`);
    },
  });
}
</script>
