<template>
  <Dialog v-model:open="open" bare size="4xl">
    <template #default>
      <div class="flex h-[34rem] max-h-[calc(100vh-8rem)] overflow-hidden">
        <!-- Left nav rail (Help Desk / CRM settings-modal style) -->
        <div class="flex w-52 shrink-0 flex-col gap-1 rounded-l-lg bg-surface-menu-bar p-2">
          <h1 class="px-2 py-1.5 text-xs font-medium text-ink-gray-5">VPN Settings</h1>
          <button
            v-for="section in sections"
            :key="section.key"
            class="flex h-7.5 w-full items-center gap-2 rounded px-2 text-p-sm"
            :class="
              active === section.key
                ? 'bg-surface-selected text-ink-gray-8 shadow-sm'
                : 'text-ink-gray-7 hover:bg-surface-gray-2'
            "
            @click="active = section.key"
          >
            <span :class="section.icon" class="size-4 shrink-0 text-ink-gray-6" aria-hidden="true" />
            <span class="truncate">{{ section.label }}</span>
          </button>
        </div>

        <!-- Right content pane -->
        <div class="flex flex-1 flex-col overflow-hidden bg-surface-modal">
          <header class="flex items-center justify-between gap-3 border-b border-outline-gray-1 px-6 py-3.5">
            <div>
              <h2 class="text-base font-semibold text-ink-gray-9">{{ current.label }}</h2>
              <p class="text-xs text-ink-gray-5">{{ current.description }}</p>
            </div>
            <div class="flex items-center gap-2">
              <Button
                variant="solid"
                theme="gray"
                label="Save"
                :loading="save.loading"
                :disabled="!loaded"
                @click="submit"
              />
              <Button variant="ghost" icon="lucide-x" @click="open = false" />
            </div>
          </header>

          <div class="flex-1 overflow-y-auto px-6 py-5">
            <ErrorState
              v-if="settings.error"
              :message="errorMessage(settings.error)"
              @retry="settings.reload()"
            />
            <div v-else-if="!loaded" class="flex justify-center py-16">
              <LoadingIndicator class="size-6 text-ink-gray-5" />
            </div>
            <div v-else class="max-w-xl space-y-5">
              <!-- General -->
              <template v-if="active === 'general'">
                <FormControl
                  v-model="form.environment"
                  type="select"
                  label="Environment"
                  :options="ENVIRONMENTS"
                />
                <FormControl
                  v-model="form.vpn_endpoint_host"
                  label="VPN endpoint host"
                  placeholder="vpn.example.com"
                  description="Public host clients dial. Falls back to the site_config vpn_endpoint_host when blank."
                />
                <div class="grid grid-cols-1 gap-5 sm:grid-cols-2">
                  <FormControl
                    v-model="form.egress_interface"
                    label="Egress interface"
                    placeholder="eth0"
                  />
                  <FormControl
                    v-model.number="form.default_listen_port"
                    type="number"
                    label="Default listen port"
                    placeholder="44556"
                  />
                </div>
                <FormControl
                  v-model="form.wg_dir"
                  label="WireGuard config directory"
                  placeholder="/etc/wireguard"
                  description="Shared render directory; must match the wg-agent mount."
                />
                <Switch
                  v-model="form.allow_server_keygen"
                  label="Allow server key generation"
                  description="Generate a peer keypair in-app when a peer is created without a public key."
                />
              </template>

              <!-- Firewall & status -->
              <template v-else-if="active === 'firewall'">
                <FormControl
                  v-model="form.multiport_redirect_ports"
                  type="textarea"
                  label="Multiport redirect ports"
                  placeholder="333,666,999,3333,4444"
                  description="Comma-separated UDP ports redirected to the WireGuard listen port."
                />
                <div class="grid grid-cols-1 gap-5 sm:grid-cols-2">
                  <FormControl
                    v-model.number="form.redirect_target_port"
                    type="number"
                    label="Redirect target port"
                    placeholder="44556"
                  />
                  <FormControl
                    v-model="form.dns_servers"
                    label="DNS servers"
                    placeholder="1.1.1.1, 8.8.8.8"
                    description="Offered to clients in their rendered config."
                  />
                  <FormControl
                    v-model.number="form.default_keepalive"
                    type="number"
                    label="Default keepalive (s)"
                    placeholder="25"
                  />
                  <FormControl
                    v-model.number="form.status_poll_interval_min"
                    type="number"
                    label="Status poll interval (min)"
                    description="A peer with no handshake within this window is marked Stale."
                  />
                </div>
              </template>

              <!-- Sync & security -->
              <template v-else>
                <Switch
                  v-model="form.sync_enabled"
                  label="Sync enabled"
                  description="Master kill-switch. While off, sync_network no-ops with an audited skipped result."
                />
                <Switch
                  v-model="form.sync_requires_local"
                  label="Sync requires local"
                  description="Require sync_network to originate from loopback (frappe.local.request_ip)."
                />
                <div class="flex gap-3 rounded-md border border-outline-gray-2 bg-surface-gray-1 px-4 py-3">
                  <span
                    class="lucide-shield-check mt-0.5 size-4 shrink-0 text-ink-gray-6"
                    aria-hidden="true"
                  />
                  <p class="text-p-sm text-ink-gray-6">
                    The sync token is a secret stored in <code>site_config</code>
                    (<code>bench set-config vpn_sync_token</code>) and is never shown
                    or editable here.
                  </p>
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </template>
  </Dialog>
</template>

<script setup>
import {
  Button,
  Dialog,
  FormControl,
  LoadingIndicator,
  Switch,
  createResource,
  toast,
} from "frappe-ui";
import { computed, reactive, ref, watch } from "vue";
import ErrorState from "@/components/ErrorState.vue";
import { ui } from "@/data/ui";
import { errorMessage } from "@/utils/format";

const ENVIRONMENTS = ["dev", "prod"];
const sections = [
  { key: "general", label: "General", icon: "lucide-sliders-horizontal", description: "Environment-wide WireGuard defaults." },
  { key: "firewall", label: "Firewall & status", icon: "lucide-shield", description: "NAT/redirect ports, DNS, and presence polling." },
  { key: "sync", label: "Sync & security", icon: "lucide-refresh-cw", description: "Network sync kill-switches." },
];
// Check fields stored as 0/1 on the backend but bound to boolean Switches.
const SWITCH_FIELDS = ["allow_server_keygen", "sync_enabled", "sync_requires_local"];

const open = computed({
  get: () => ui.settingsOpen,
  set: (value) => (ui.settingsOpen = value),
});
const active = ref("general");
const loaded = ref(false);
const form = reactive({});
const current = computed(() => sections.find((section) => section.key === active.value));

const settings = createResource({
  url: "vpn_management.api.get_vpn_settings",
  method: "GET",
  onSuccess: (data) => {
    Object.assign(form, data);
    for (const field of SWITCH_FIELDS) form[field] = Boolean(data[field]);
    loaded.value = true;
  },
});
const save = createResource({ url: "vpn_management.api.upsert_vpn_settings", method: "POST" });

// Load fresh each time the modal opens; reset to the General section.
watch(open, (isOpen) => {
  if (!isOpen) return;
  active.value = "general";
  settings.fetch();
});

async function submit() {
  const params = { ...form };
  // Send every Switch as an explicit 0/1 so turning one off actually persists.
  for (const field of SWITCH_FIELDS) params[field] = form[field] ? 1 : 0;
  await save.submit(params).catch(() => {});
  if (save.error) {
    toast.error(errorMessage(save.error) || "Couldn’t save settings");
    return;
  }
  toast.success("Settings saved");
}
</script>
