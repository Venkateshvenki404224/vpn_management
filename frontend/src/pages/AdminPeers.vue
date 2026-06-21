<template>
  <AppShell>
    <div class="mb-5 flex items-center justify-between gap-4">
      <div>
        <h1 class="text-lg font-semibold text-ink-gray-9">Servers &amp; Peers</h1>
        <p class="text-sm text-ink-gray-5">Interface status and peer provisioning.</p>
      </div>
      <div class="flex items-center gap-2">
        <Button
          label="Refresh"
          icon-left="lucide-refresh-cw"
          :loading="peers.loading || servers.loading"
          @click="refresh"
        />
        <Button
          variant="solid"
          theme="gray"
          label="Create Peer"
          icon-left="lucide-plus"
          @click="showCreate = true"
        />
      </div>
    </div>

    <div
      v-if="serverRows.length"
      class="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3"
    >
      <ServerStatusCard
        v-for="server in serverRows"
        :key="server.name"
        :server="server"
        actions
        @done="refresh"
      />
    </div>

    <h2 class="mb-2 text-sm font-semibold text-ink-gray-7">Peers</h2>
    <div v-if="peers.loading && !peerRows.length" class="flex justify-center py-16">
      <LoadingIndicator class="size-6 text-ink-gray-5" />
    </div>
    <EmptyState
      v-else-if="!peerRows.length"
      icon="lucide-users"
      title="No peers yet"
      description="Create the first peer to allocate an address and converge the interface."
    />
    <PeerTable
      v-else
      :peers="peerRows"
      show-owner
      show-admin-actions
      @peer-changed="refresh"
    />

    <Dialog v-model:open="showCreate" :options="{ title: 'Create Peer' }">
      <template #body-content>
        <div class="space-y-4">
          <FormControl
            v-model="form.peer_name"
            label="Peer name"
            placeholder="alice-laptop"
            required
          />
          <FormControl
            type="select"
            v-model="form.server"
            label="Server"
            :options="serverOptions"
            :placeholder="serverOptions.length ? 'Select a server' : 'No servers available'"
            required
          />
          <FormControl
            v-model="form.owner_user"
            type="email"
            label="Owner email"
            description="The VPN User who owns this peer. Defaults to you."
          />
          <ErrorMessage :message="createError" />
        </div>
      </template>
      <template #actions="{ close }">
        <div class="flex justify-end gap-2">
          <Button label="Cancel" @click="close" />
          <Button
            variant="solid"
            theme="gray"
            label="Create peer"
            :loading="createPeer.loading"
            :disabled="!form.peer_name || !form.server"
            @click="submitCreate(close)"
          />
        </div>
      </template>
    </Dialog>
  </AppShell>
</template>

<script setup>
import {
  Button,
  Dialog,
  ErrorMessage,
  FormControl,
  LoadingIndicator,
  createResource,
} from "frappe-ui";
import { computed, reactive, ref } from "vue";
import AppShell from "@/components/AppShell.vue";
import EmptyState from "@/components/EmptyState.vue";
import PeerTable from "@/components/PeerTable.vue";
import ServerStatusCard from "@/components/ServerStatusCard.vue";

const peers = createResource({
  url: "vpn_management.api.list_peers",
  method: "GET", // GET-only whitelisted endpoint; createResource defaults to POST
  params: { limit: 100 },
  auto: true,
});
const servers = createResource({
  url: "vpn_management.api.list_servers",
  method: "GET",
  auto: true,
});
const peerRows = computed(() => peers.data || []);
const serverRows = computed(() => servers.data || []);
const serverOptions = computed(() =>
  serverRows.value.map((server) => ({
    label: server.interface_name,
    value: server.name,
  }))
);

function refresh() {
  peers.reload();
  servers.reload();
}

const showCreate = ref(false);
const form = reactive({ peer_name: "", server: "", owner_user: "" });

const createPeer = createResource({
  url: "vpn_management.api.create_peer",
  method: "POST",
});
const createError = computed(() => {
  const error = createPeer.error;
  if (!error) return "";
  return error.messages?.join(", ") || error.message || String(error);
});

async function submitCreate(close) {
  await createPeer
    .submit({
      peer_name: form.peer_name,
      server: form.server,
      owner_user: form.owner_user || undefined,
    })
    .catch(() => {});
  if (createPeer.error) return; // keep the dialog open; error shows inline
  Object.assign(form, { peer_name: "", server: "", owner_user: "" });
  close();
  refresh();
}
</script>
