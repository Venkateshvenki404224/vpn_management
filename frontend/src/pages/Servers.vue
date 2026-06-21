<template>
  <AppShell>
    <div class="mb-5 flex items-center justify-between gap-4">
      <div>
        <h1 class="text-lg font-semibold text-ink-gray-9">Servers</h1>
        <p class="text-sm text-ink-gray-5">
          WireGuard interfaces and their firewall configuration.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <Button
          label="Refresh"
          icon-left="lucide-refresh-cw"
          :loading="servers.loading"
          @click="servers.reload()"
        />
        <Button
          variant="solid"
          theme="gray"
          label="New Server"
          icon-left="lucide-plus"
          @click="create"
        />
      </div>
    </div>

    <div v-if="servers.loading && !rows.length" class="flex justify-center py-16">
      <LoadingIndicator class="size-6 text-ink-gray-5" />
    </div>
    <EmptyState
      v-else-if="!rows.length"
      icon="lucide-server"
      title="No servers yet"
      description="Create a WireGuard server to start provisioning peers."
    />
    <ServerTable
      v-else
      :servers="rows"
      manage
      @edit="edit"
      @done="servers.reload()"
    />

    <ServerForm
      v-model:open="showForm"
      :interface-name="editing"
      @saved="servers.reload()"
    />
  </AppShell>
</template>

<script setup>
import { Button, LoadingIndicator, createResource } from "frappe-ui";
import { computed, ref } from "vue";
import AppShell from "@/components/AppShell.vue";
import EmptyState from "@/components/EmptyState.vue";
import ServerForm from "@/components/ServerForm.vue";
import ServerTable from "@/components/ServerTable.vue";

const servers = createResource({
  url: "vpn_management.api.list_servers",
  method: "GET",
  auto: true,
});
const rows = computed(() => servers.data || []);

const showForm = ref(false);
const editing = ref(null);

function create() {
  editing.value = null;
  showForm.value = true;
}

function edit(server) {
  editing.value = server.name;
  showForm.value = true;
}
</script>
